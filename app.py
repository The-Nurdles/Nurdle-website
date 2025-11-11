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
# Database viewer
# ---------------------------------------------------------
@app.route('/database')
def view_database():
    import base64
    import sqlite3

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, filename, image, total_count, nurdles_count, beads_count, latitude, longitude, timestamp FROM processed_images')
    rows = c.fetchall()
    conn.close()

    # Start building HTML
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
            body.modal-open { overflow: hidden; backdrop-filter: blur(4px); }
        </style>
    </head>
    <body class="bg-gray-100 text-gray-800">
        <div class="max-w-7xl mx-auto px-6 py-8">
            <h1 class="text-3xl font-bold mb-8 text-center text-green-700">Image Database</h1>
            <div class="overflow-x-auto bg-white shadow-md rounded-lg">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-green-600 text-white">
                        <tr>
                            <th class="px-4 py-3 text-left text-sm font-semibold">ID</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold">Image</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold">Total</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold">Nurdles</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold">Beads</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold">Timestamp</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold">Location</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">
    """

    # Add rows
    for row in rows:
        _id, filename, img_blob, total, nurdle, bead, lat, lon, timestamp = row
        if img_blob:
            img_base64 = base64.b64encode(img_blob).decode('utf-8')
            img_html = f'''
                <img src="data:image/jpeg;base64,{img_base64}" alt="{filename}" class="w-32 h-32 object-cover rounded-md shadow-sm mx-auto cursor-pointer hover:scale-105 transition" onclick="openModal('data:image/jpeg;base64,{img_base64}')">
            '''
        else:
            img_html = '<div class="w-32 h-32 bg-gray-300 flex items-center justify-center rounded-md">No Image</div>'

        filename_html = f'<div class="text-xs text-gray-600 mt-1 text-center">{filename}</div>'
        if lat and lon:
            location_html = f'<a href="https://www.google.com/maps?q={lat},{lon}" target="_blank" class="text-green-600 hover:underline">🌍 {lat:.5f}, {lon:.5f}</a>'
        else:
            location_html = '<span class="text-gray-400">N/A</span>'

        html += f"""
            <tr class="hover:bg-gray-50 transition">
                <td class="px-4 py-3 text-sm">{_id}</td>
                <td class="px-4 py-3 text-center">{img_html}{filename_html}</td>
                <td class="px-4 py-3 text-sm font-semibold text-gray-900">{total}</td>
                <td class="px-4 py-3 text-sm text-green-700">{nurdle}</td>
                <td class="px-4 py-3 text-sm text-blue-700">{bead}</td>
                <td class="px-4 py-3 text-sm text-gray-600">{timestamp}</td>
                <td class="px-4 py-3 text-sm">{location_html}</td>
            </tr>
        """

    # Close HTML
    html += """
                    </tbody>
                </table>
            </div>
            <div class="mt-8 text-center">
                <a href="/" class="bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-4 rounded-lg shadow-md transition">← Back to Upload</a>
            </div>
        </div>

        <!-- Image Zoom Modal -->
        <div id="imageModal" class="fixed inset-0 bg-black bg-opacity-70 hidden z-50 flex items-center justify-center backdrop-blur-sm">
            <div class="relative fade-in flex justify-center items-center">
                <img id="modalImg" src="" class="rounded-lg shadow-2xl w-auto max-w-[90vw] max-h-[85vh] object-contain">
                <button onclick="closeModal()" class="absolute top-2 right-2 bg-white bg-opacity-90 text-gray-800 rounded-full px-3 py-1 text-xl font-bold hover:bg-gray-200 hover:scale-105 transition">&times;</button>
            </div>
        </div>

        <script>
        function openModal(imgSrc) {
            const modal = document.getElementById('imageModal');
            const modalImg = document.getElementById('modalImg');
            modalImg.src = imgSrc;
            modal.classList.remove('hidden');
            document.body.classList.add('overflow-hidden');
        }
        function closeModal() {
            const modal = document.getElementById('imageModal');
            modal.classList.add('hidden');
            document.body.classList.remove('overflow-hidden');
        }
        document.getElementById('imageModal').addEventListener('click', (e) => {
            if (e.target.id === 'imageModal') { closeModal(); }
        });
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
