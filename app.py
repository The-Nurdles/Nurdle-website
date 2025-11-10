from flask import Flask, request, render_template, jsonify
import os, uuid, sqlite3, base64, datetime
from ultralytics import YOLO
from PIL import Image
import cv2
from PIL.ExifTags import TAGS, GPSTAGS
from collections import Counter

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
RESULT_FOLDER = 'static/results'
DB_NAME = 'yolo.db'

# Load YOLOv8 model
model = YOLO('2nd.pt')  # Replace with your model

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Initialize database with image and GPS columns
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS processed_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            image BLOB,
            total_count INTEGER,
            nurdles_count INTEGER,
            beads_count INTEGER,
            latitude REAL,
            longitude REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Extract EXIF metadata
def get_exif_data(image_path):
    image = Image.open(image_path)
    exif_data = image._getexif()
    if not exif_data:
        return {}
    exif = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}
    return exif

# Extract GPS coordinates
def get_gps_info(exif):
    gps_info = exif.get('GPSInfo')
    if not gps_info:
        return None, None
    gps_data = {GPSTAGS.get(key, key): value for key, value in gps_info.items()}

    def convert_to_degrees(value):
        d, m, s = value
        return d[0]/d[1] + (m[0]/m[1])/60 + (s[0]/s[1])/3600

    lat = convert_to_degrees(gps_data['GPSLatitude'])
    if gps_data['GPSLatitudeRef'] != 'N':
        lat = -lat

    lon = convert_to_degrees(gps_data['GPSLongitude'])
    if gps_data['GPSLongitudeRef'] != 'E':
        lon = -lon

    return lat, lon

# Save results to DB
def save_results_to_db(filename ,img_path, total, nurdles, beads, lat, lon):
    with open(img_path, 'rb') as f:
        img_blob = f.read()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    current_time = datetime.datetime.now().strftime('%H:%M:%S')
    c.execute('''
        INSERT INTO processed_images 
        (filename, image, total_count, nurdles_count, beads_count, latitude, longitude, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (filename ,img_blob, total, nurdles, beads, lat, lon, current_time))
    conn.commit()
    conn.close()

# Main page
@app.route('/')
def index():
    return render_template('index.html')

# Upload and detect
@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return "No image uploaded", 400

    file = request.files['image']
    if file.filename == '':
        return "Empty filename", 400

    # Save uploaded image
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    # Run YOLOv8 inference
    results = model(filepath, max_det=1500)
    boxes = results[0].boxes
    class_ids = boxes.cls.tolist()
    labels = [results[0].names[int(i)] for i in class_ids]
    detected_count = len(labels)

    label_counts = Counter(labels)
    nurdle_count = label_counts.get('nurdle', 0)
    bead_count = label_counts.get('bead', 0)

    # Annotated image (no labels)
    result_img_path = os.path.join(RESULT_FOLDER, filename)
    plot_img = results[0].plot(boxes=True, labels=False, conf=False)
    plot_img_rgb = cv2.cvtColor(plot_img, cv2.COLOR_BGR2RGB)
    Image.fromarray(plot_img_rgb).save(result_img_path)

    # Extract GPS
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')

    # Save results to DB
    save_results_to_db( filename ,result_img_path, detected_count, nurdle_count, bead_count, lat, lon)

    # Convert to base64 for frontend
    with open(result_img_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

    return jsonify({
        "image_data": encoded_image,
        "total": detected_count,
        "nurdles": nurdle_count,
        "beads": bead_count,
        "latitude": lat,
        "longitude": lon
    })

# View database
@app.route('/database')
def view_database():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, filename, image, total_count, nurdles_count, beads_count, latitude, longitude, timestamp FROM processed_images')
    rows = c.fetchall()
    conn.close()

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Processed Images Database</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            /* Simple fade-in animation for modal */
            .fade-in {
                animation: fadeIn 0.25s ease-in-out;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: scale(0.95); }
                to { opacity: 1; transform: scale(1); }
            }
            /* Blur background when modal is open */
            body.modal-open {
                overflow: hidden;
                backdrop-filter: blur(4px);
            }
        </style>
    </head>
    <body class="bg-gray-100 text-gray-800">
        <div class="max-w-7xl mx-auto px-6 py-8">
            <h1 class="text-3xl font-bold mb-8 text-center text-green-700"> Image Database</h1>

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

    for row in rows:
        _id, filename, img_blob, total, nurdle, bead, lat, lon, timestamp = row

        if img_blob:
            import base64
            img_base64 = base64.b64encode(img_blob).decode('utf-8')
            img_html = f'''
                <img 
                    src="data:image/jpeg;base64,{img_base64}" 
                    alt="{filename}" 
                    class="w-32 h-32 object-cover rounded-md shadow-sm mx-auto cursor-pointer hover:scale-105 transition"
                    onclick="openModal('data:image/jpeg;base64,{img_base64}')"
                >
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

    html += """
                    </tbody>
                </table>
            </div>

            <div class="mt-8 text-center">
                <a href="/" class="bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-4 rounded-lg shadow-md transition">← Back to Upload</a>
            </div>
        </div>

        <!-- Image Zoom Modal -->
        <div 
  id="imageModal" 
  class="fixed inset-0 bg-black bg-opacity-70 hidden z-50 flex items-center justify-center backdrop-blur-sm"
>
  <div class="relative fade-in flex justify-center items-center">
    <img 
      id="modalImg" 
      src="" 
      class="rounded-lg shadow-2xl w-auto max-w-[90vw] max-h-[85vh] object-contain"
    >
    <button 
      onclick="closeModal()" 
      class="absolute top-2 right-2 bg-white bg-opacity-90 text-gray-800 rounded-full px-3 py-1 text-xl font-bold hover:bg-gray-200 hover:scale-105 transition"
    >&times;</button>
  </div>
</div>

<script>
  function openModal(imgSrc) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImg');
    modalImg.src = imgSrc;
    modal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden'); // prevent background scroll
  }

  function closeModal() {
    const modal = document.getElementById('imageModal');
    modal.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
  }

  // Close modal when clicking outside image
  document.getElementById('imageModal').addEventListener('click', (e) => {
    if (e.target.id === 'imageModal') {
      closeModal();
    }
  });
</script>
    </body>
    </html>
    """

    return html


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
