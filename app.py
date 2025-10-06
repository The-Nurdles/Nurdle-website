from flask import Flask, request, render_template, jsonify, send_file
import os, uuid, sqlite3, base64
from ultralytics import YOLO
from PIL import Image
import cv2  # Needed for BGR to RGB conversion

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
RESULT_FOLDER = 'static/results'
DB_NAME = 'yolo.db'

# Load YOLOv8 model
model = YOLO('best1.pt')  # Replace with your custom model path

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Initialize the SQLite database
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS processed_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            detected_count INTEGER,
            labels TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Save detection info to the database
def save_results_to_db(filename, labels):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        'INSERT INTO processed_images (filename, detected_count, labels) VALUES (?, ?, ?)',
        (filename, len(labels), ', '.join(labels))
    )
    conn.commit()
    conn.close()

# Main page
@app.route('/')
def index():
    return render_template('index.html')

# Handle image upload and detection
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
    file.save(filepath)

    # Run YOLOv8 inference
    results = model(filepath)
    boxes = results[0].boxes
    class_ids = boxes.cls.tolist()
    labels = [results[0].names[int(i)] for i in class_ids]
    detected_count = len(labels)

    # Generate annotated image with bounding boxes only (no labels/confidence)
    result_img_path = os.path.join(RESULT_FOLDER, filename)
    plot_img = results[0].plot(boxes=True, labels=False, conf=False)

    # Convert BGR to RGB for correct color
    plot_img_rgb = cv2.cvtColor(plot_img, cv2.COLOR_BGR2RGB)
    Image.fromarray(plot_img_rgb).save(result_img_path)

    # Save results to database
    save_results_to_db(filename, labels)

    # Convert result image to base64 for frontend
    with open(result_img_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

    return jsonify({
        "image_data": encoded_image,
        "count": detected_count,
        "labels": labels
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

