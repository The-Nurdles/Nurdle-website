from flask import Flask, request, render_template, jsonify, url_for, send_from_directory
import os, base64, uuid, datetime, sqlite3
from utils.db_utils import init_db, save_results_to_db, get_all_rows, DB_NAME
from utils.gps_utils import get_exif_data, get_gps_info
from utils.yolo_utils import run_yolo

# -------------------------------------------------------------------
# Flask app configuration
# -------------------------------------------------------------------
app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
RESULT_FOLDER = 'static/results'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Initialize database
init_db()

# -------------------------------------------------------------------
# Register Jinja2 filter for Base64 encoding (used in database.html)
# -------------------------------------------------------------------
@app.template_filter('b64encode')
def b64encode_filter(data):
    return base64.b64encode(data).decode('utf-8')

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.route('/')
def index():
    """Main upload page."""
    return render_template('index.html')

# ---------------------------------------------------------
# Upload + YOLO detection
# ---------------------------------------------------------
@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return "No image uploaded", 400

    file = request.files['image']
    if file.filename == '':
        return "Empty filename", 400

    # Save uploaded file
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # Run YOLO detection
    total, nurdles, beads, result_path = run_yolo(filepath, filename)

    # Retrieve geolocation
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')

    # Fallback to EXIF GPS if not provided by browser
    if not lat or not lon:
        exif = get_exif_data(filepath)
        exif_lat, exif_lon = get_gps_info(exif)
        if exif_lat and exif_lon:
            lat, lon = exif_lat, exif_lon

    # Save to database
    save_results_to_db(filename, result_path, total, nurdles, beads, lat, lon)

    # Convert annotated image to base64
    with open(result_path, "rb") as img_file:
        encoded_img = base64.b64encode(img_file.read()).decode('utf-8')

    return jsonify({
        "image_data": encoded_img,
        "total": total,
        "nurdles": nurdles,
        "beads": beads,
        "latitude": lat,
        "longitude": lon
    })

# ---------------------------------------------------------
# Map Page
# ---------------------------------------------------------
@app.route('/map')
def map_page():
    return render_template('map.html')

@app.route('/api/locations')
def api_locations():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, filename, latitude, longitude FROM processed_images')
    rows = c.fetchall()
    conn.close()

    data = []
    for row in rows:
        _id, filename, lat, lon = row
        if lat and lon:
            data.append({
                "id": _id,
                "filename": filename,
                "lat": lat,
                "lon": lon
            })

    return jsonify(data)

# ---------------------------------------------------------
# Database viewer
# ---------------------------------------------------------
@app.route('/database')
def view_database():
    import base64
    import sqlite3

    ITEMS_PER_PAGE = 10
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Count total rows
    c.execute("SELECT COUNT(*) FROM processed_images")
    total_rows = c.fetchone()[0]

    # Fetch only 10 rows for this page
    c.execute("""
        SELECT id, filename, image, total_count, nurdles_count, beads_count,
               latitude, longitude, timestamp
        FROM processed_images
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """, (ITEMS_PER_PAGE, offset))
    rows = c.fetchall()
    conn.close()

    # Pagination info
    total_pages = max((total_rows + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE, 1)
    has_prev = page > 1
    has_next = page < total_pages

    prev_page = page - 1
    next_page = page + 1

    # Start HTML
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Database</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .fade-in { animation: fadeIn 0.25s ease-in-out; }
        @keyframes fadeIn { from {opacity:0; transform:scale(0.95);} to {opacity:1; transform:scale(1);} }
    </style>
</head>
<body class="bg-gray-100 text-gray-800">
    <div class="max-w-7xl mx-auto px-6 py-8">
        <h1 class="text-3xl font-bold mb-8 text-center text-green-700">Image Database</h1>

        <div class="overflow-x-auto bg-white shadow-md rounded-lg">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-green-600 text-white">
                    <tr>
                        <th class="px-4 py-3">ID</th>
                        <th class="px-4 py-3">Image</th>
                        <th class="px-4 py-3">Total</th>
                        <th class="px-4 py-3">Nurdles</th>
                        <th class="px-4 py-3">Beads</th>
                        <th class="px-4 py-3">Timestamp</th>
                        <th class="px-4 py-3">Location</th>
                    </tr>
                </thead>
                <tbody>
"""

    # rows
    for row in rows:
        _id, filename, img_blob, total, nurdles, beads, lat, lon, timestamp = row

        if img_blob:
            img_b64 = base64.b64encode(img_blob).decode("utf-8")
            img_html = f"<img src='data:image/jpeg;base64,{img_b64}' class='w-32 h-32 object-cover rounded-md cursor-pointer hover:scale-105 transition' onclick=\"openModal('data:image/jpeg;base64,{img_b64}')\">"
        else:
            img_html = "<div class='w-32 h-32 bg-gray-300 rounded-md'></div>"

        filename_html = f"<div class='text-xs text-gray-600 text-center'>{filename}</div>"

        if lat and lon:
            loc_html = f"<a href='https://www.google.com/maps?q={lat},{lon}' target='_blank' class='text-green-700'>📍 {lat:.5f}, {lon:.5f}</a>"
        else:
            loc_html = "<span class='text-gray-400'>N/A</span>"

        html += f"""
<tr class='hover:bg-gray-50'>
    <td class='px-4 py-3'>{_id}</td>
    <td class='px-4 py-3 text-center'>{img_html}{filename_html}</td>
    <td class='px-4 py-3 font-semibold'>{total}</td>
    <td class='px-4 py-3 text-green-700'>{nurdles}</td>
    <td class='px-4 py-3 text-blue-700'>{beads}</td>
    <td class='px-4 py-3 text-gray-600'>{timestamp}</td>
    <td class='px-4 py-3'>{loc_html}</td>
</tr>
"""

    # Pagination footer
    html += f"""
                </tbody>
            </table>
        </div>

        <div class="flex justify-center items-center mt-6 space-x-4">
    """

    if has_prev:
        html += f"<a href='?page={prev_page}' class='px-4 py-2 bg-green-600 text-white rounded-lg'>← Previous</a>"

    html += f"<span class='font-semibold text-gray-700'>Page {page} of {total_pages}</span>"

    if has_next:
        html += f"<a href='?page={next_page}' class='px-4 py-2 bg-green-600 text-white rounded-lg'>Next →</a>"

    html += """
        </div>

        <div class="mt-8 text-center">
            <a href="/" class="px-4 py-2 bg-green-600 text-white rounded-lg">← Back to Upload</a>
        </div>
    </div>

    <!-- modal -->
    <div id="imageModal" class="fixed inset-0 bg-black bg-opacity-70 hidden flex items-center justify-center">
        <div class="relative">
            <img id="modalImg" class="max-w-[90vw] max-h-[85vh] rounded-lg shadow-xl">
            <button onclick="closeModal()" class="absolute top-2 right-2 bg-white px-3 py-1 rounded-full text-xl">&times;</button>
        </div>
    </div>

    <script>
    function openModal(src) {
        const m = document.getElementById('imageModal');
        document.getElementById('modalImg').src = src;
        m.classList.remove('hidden');
    }
    function closeModal() {
        document.getElementById('imageModal').classList.add('hidden');
    }
    </script>

</body>
</html>
"""

    return html


# ---------------------------------------------------------
# Run app
# ---------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
