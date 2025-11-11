import sqlite3, datetime, os

DB_NAME = "database\yolo.db"

# -------------------------------------------------------------------
# Initialize the database
# -------------------------------------------------------------------
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

# -------------------------------------------------------------------
# Save YOLO results to the database
# -------------------------------------------------------------------
def save_results_to_db(filename, img_path, total, nurdles, beads, lat, lon):
    with open(img_path, 'rb') as f:
        img_blob = f.read()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    c.execute('''
        INSERT INTO processed_images
        (filename, image, total_count, nurdles_count, beads_count, latitude, longitude, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (filename, img_blob, total, nurdles, beads, lat, lon, timestamp))

    conn.commit()
    conn.close()

# -------------------------------------------------------------------
# Fetch all database rows for /database route
# -------------------------------------------------------------------
def get_all_rows():
    """
    Returns all rows from the processed_images table
    as a list of tuples for Jinja rendering.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT id, filename, image, total_count, nurdles_count, beads_count,
               latitude, longitude, timestamp
        FROM processed_images
        ORDER BY id DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return rows
