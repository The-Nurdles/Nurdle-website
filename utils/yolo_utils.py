from ultralytics import YOLO
from collections import Counter
import os, cv2
from PIL import Image

model = YOLO('models/2nd.pt')

RESULT_FOLDER = 'static/results'
os.makedirs(RESULT_FOLDER, exist_ok=True)

def run_yolo(filepath, filename):
    results = model(filepath, max_det=1500)
    boxes = results[0].boxes
    class_ids = boxes.cls.tolist()
    labels = [results[0].names[int(i)] for i in class_ids]
    total = len(labels)

    counts = Counter(labels)
    nurdles = counts.get('nurdle', 0)
    beads = counts.get('bead', 0)

    result_path = os.path.join(RESULT_FOLDER, filename)
    plot_img = results[0].plot(boxes=True, labels=False, conf=False)
    plot_img_rgb = cv2.cvtColor(plot_img, cv2.COLOR_BGR2RGB)
    Image.fromarray(plot_img_rgb).save(result_path)

    return total, nurdles, beads, result_path
