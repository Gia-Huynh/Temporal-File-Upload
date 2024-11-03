from flask import Flask, request, redirect, url_for, render_template, send_from_directory
import os
import time
import sqlite3
from werkzeug.utils import secure_filename
from threading import Thread

app = Flask(__name__)
PERSISTENT_FOLDER = 'persistent'
UPLOAD_FOLDER = 'uploads'
MAX_UPLOAD_SIZE = 10 * 1024 * 1024 * 1024  # 10GB limit
EXPIRATION_TIME = 7 * 24 * 3600  # 1 week in seconds

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PERSISTENT_FOLDER'] = PERSISTENT_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PERSISTENT_FOLDER, exist_ok=True)

# Initialize SQLite database
def init_db():
    with sqlite3.connect('filedata.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS files
                        (id INTEGER PRIMARY KEY, filename TEXT, timestamp INTEGER)''')
init_db()

# Auto-delete old files and enforce size limit
def manage_uploads():
    while True:
        time.sleep(60)
        with sqlite3.connect('filedata.db') as conn:
            cursor = conn.cursor()
            # Delete files older than a week
            now = int(time.time())
            cursor.execute("SELECT filename FROM files WHERE timestamp < ?", (now - EXPIRATION_TIME,))
            for (filename,) in cursor.fetchall():
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            cursor.execute("DELETE FROM files WHERE timestamp < ?", (now - EXPIRATION_TIME,))
            
            # Enforce 10GB size limit by deleting oldest files
            cursor.execute("SELECT filename, timestamp FROM files ORDER BY timestamp")
            files = cursor.fetchall()
            total_size = sum(os.path.getsize(os.path.join(UPLOAD_FOLDER, f[0])) for f in files if os.path.exists(os.path.join(UPLOAD_FOLDER, f[0])))
            while total_size > MAX_UPLOAD_SIZE and files:
                oldest_file, _ = files.pop(0)
                os.remove(os.path.join(UPLOAD_FOLDER, oldest_file))
                cursor.execute("DELETE FROM files WHERE filename = ?", (oldest_file,))
                total_size = sum(os.path.getsize(os.path.join(UPLOAD_FOLDER, f[0])) for f in files if os.path.exists(os.path.join(UPLOAD_FOLDER, f[0])))
            conn.commit()

# Start background thread to manage uploads
Thread(target=manage_uploads, daemon=True).start()

@app.route('/')
def index():
    with sqlite3.connect('filedata.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM files")
        uploaded_files = cursor.fetchall()
    persistent_files = os.listdir(PERSISTENT_FOLDER)
    return render_template('index.html', uploaded_files=uploaded_files, persistent_files=persistent_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        with sqlite3.connect('filedata.db') as conn:
            timestamp = int(time.time())
            conn.execute("INSERT INTO files (filename, timestamp) VALUES (?, ?)", (filename, timestamp))
            conn.commit()
        return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def download_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/persistent/<filename>')
def download_persistent(filename):
    return send_from_directory(app.config['PERSISTENT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
