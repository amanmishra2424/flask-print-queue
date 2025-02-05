from flask import Flask, request, send_file, jsonify, render_template_string
from flask_cors import CORS
from PyPDF2 import PdfMerger
import os
import hashlib
import requests
from datetime import datetime
import cloudinary
import cloudinary.uploader
import cloudinary.api
from pymongo import MongoClient
import tempfile
from bson import ObjectId

app = Flask(__name__)
CORS(app)

# Cloudinary Configuration
cloudinary.config(
    cloud_name='disht9nbk',
    api_key='587297388865477',
    api_secret='44JUq6ZcveKznDxyXT7OT4GyoTs')

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGODB_URI', 'mongodb+srv://print_queue_db:jai_ho@aman.dlsk6.mongodb.net/')
client = MongoClient(MONGO_URI)
db = client['print_queue_db']
batch1_collection = db['batch1_queue']
batch2_collection = db['batch2_queue']

# Create temporary directory for file operations
TEMP_DIR = tempfile.mkdtemp()
TEMP_DIR = '/tmp'  # Use /tmp directory on Render
# Admin password (SHA-256 hashed)
ADMIN_PASSWORD = hashlib.sha256(os.environ.get('ADMIN_PASSWORD', 'jai ho').encode()).hexdigest()

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Print Service Queue</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
            }
            .container {
                border: 1px solid #ccc;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
            }
            input {
                width: 100%;
                padding: 8px;
                margin-bottom: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                width: 100%;
                margin-bottom: 10px;
            }
            button.admin {
                background-color: #2196F3;
            }
            button:hover {
                opacity: 0.9;
            }
            .status {
                margin-top: 15px;
                padding: 10px;
                border-radius: 4px;
            }
            .success {
                background-color: #dff0d8;
                color: #3c763d;
            }
            .error {
                background-color: #f2dede;
                color: #a94442;
            }
            .queue-list {
                margin-top: 20px;
            }
            .queue-item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 style="text-align: center;">Print Service Queue</h1>
            
            <div class="form-group">
                <label for="batchSelect">Select Batch:</label>
                <select id="batchSelect" style="width: 100%; padding: 8px; margin-bottom: 15px;">
                    <option value="1">Batch 1</option>
                    <option value="2">Batch 2</option>
                </select>
            </div>

            <div class="form-group">
                <label for="studentName">Your Name:</label>
                <input type="text" id="studentName" required>
            </div>
            
            <div class="form-group">
                <label for="pdfFile">Select PDF File:</label>
                <input type="file" id="pdfFile" accept=".pdf" required>
            </div>
            
            <div class="form-group">
                <label for="copies">Number of Copies:</label>
                <input type="number" id="copies" min="1" max="100" value="1" required>
            </div>
            
            <button onclick="submitPrint()">Submit Print Request</button>
            
            <div id="status" class="status"></div>
        </div>

        <div class="container">
            <h2 style="text-align: center;">Admin Controls</h2>
            <div class="form-group">
                <label for="adminPassword">Admin Password:</label>
                <input type="password" id="adminPassword">
            </div>
            <button class="admin" onclick="viewQueue()">View Queue</button>
            <button class="admin" onclick="mergePrintQueue()">Merge and Download Queue</button>
            <div id="queueList" class="queue-list"></div>
        </div>

        <script>
            async function submitPrint() {
                const name = document.getElementById('studentName').value;
                const file = document.getElementById('pdfFile').files[0];
                const copies = document.getElementById('copies').value;
                const batch = document.getElementById('batchSelect').value;
                const status = document.getElementById('status');

                if (!name || !file || !copies) {
                    status.textContent = 'Please fill all fields';
                    status.className = 'status error';
                    return;
                }

                const formData = new FormData();
                formData.append('name', name);
                formData.append('pdf', file);
                formData.append('copies', copies);
                formData.append('batch', batch);

                try {
                    const response = await fetch('/submit', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        status.textContent = 'Print request submitted successfully!';
                        status.className = 'status success';
                        document.getElementById('studentName').value = '';
                        document.getElementById('pdfFile').value = '';
                        document.getElementById('copies').value = '1';
                    } else {
                        const error = await response.text();
                        status.textContent = `Error: ${error}`;
                        status.className = 'status error';
                    }
                } catch (error) {
                    status.textContent = 'Error submitting request';
                    status.className = 'status error';
                }
            }

            async function viewQueue() {
                const password = document.getElementById('adminPassword').value;
                const batch = document.getElementById('batchSelect').value;
                const queueList = document.getElementById('queueList');

                try {
                    const response = await fetch(`/queue?batch=${batch}&password=${encodeURIComponent(password)}`);
                    
                    if (response.status === 403) {
                        queueList.innerHTML = '<div class="error">Invalid admin password</div>';
                        return;
                    }

                    const queue = await response.json();
                    
                    if (queue.length === 0) {
                        queueList.innerHTML = '<div>Queue is empty</div>';
                        return;
                    }

                    queueList.innerHTML = queue.map(item => `
                        <div class="queue-item">
                            <strong>${item.name}</strong><br>
                            File: ${item.original_filename}<br>
                            Copies: ${item.copies}<br>
                            Submitted: ${item.timestamp}
                        </div>
                    `).join('');
                } catch (error) {
                    queueList.innerHTML = '<div class="error">Error loading queue</div>';
                }
            }

            async function mergePrintQueue() {
                const password = document.getElementById('adminPassword').value;
                const batch = document.getElementById('batchSelect').value;

                try {
                    const response = await fetch(`/merge?batch=${batch}&password=${encodeURIComponent(password)}`, {
                        method: 'POST'
                    });

                    if (response.status === 403) {
                        alert('Invalid admin password');
                        return;
                    }

                    if (response.status === 404) {
                        alert('Queue is empty');
                        return;
                    }

                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `print_queue_batch${batch}_${new Date().toISOString().split('T')[0]}.pdf`;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        a.remove();
                        viewQueue(); // Refresh the queue display
                    }
                } catch (error) {
                    alert('Error merging PDFs');
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route('/submit', methods=['POST'])
def submit_print():
    try:
        if 'pdf' not in request.files:
            return 'No file uploaded', 400

        file = request.files['pdf']
        name = request.form.get('name')
        copies = int(request.form.get('copies', 1))
        batch = int(request.form.get('batch', 1))

        if not name:
            return 'Name is required', 400

        if file.filename == '':
            return 'No file selected', 400

        if not file.filename.lower().endswith('.pdf'):
            return 'Only PDF files are allowed', 400

        # Save file temporarily
        temp_path = os.path.join(TEMP_DIR, file.filename)
        file.save(temp_path)

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            temp_path,
            resource_type="raw",
            folder="print_queue",
            public_id=f"print_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        )

        # Clean up temp file
        os.remove(temp_path)

        # Store in MongoDB
        document = {
            'name': name,
            'original_filename': file.filename,
            'cloudinary_url': upload_result['secure_url'],
            'public_id': upload_result['public_id'],
            'copies': copies,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        collection = batch1_collection if batch == 1 else batch2_collection
        collection.insert_one(document)

        return 'Success', 200

    except Exception as e:
        return str(e), 500

@app.route('/queue')
def view_queue():
    try:
        password = request.args.get('password', '')
        batch = int(request.args.get('batch', 1))

        if hashlib.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD:
            return 'Unauthorized', 403

        collection = batch1_collection if batch == 1 else batch2_collection
        queue = list(collection.find({}, {'_id': 0}))
        return jsonify(queue)

    except Exception as e:
        return str(e), 500

@app.route('/merge', methods=['POST'])
def merge_queue():
    try:
        password = request.args.get('password', '')
        batch = int(request.args.get('batch', 1))

        if hashlib.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD:
            return 'Unauthorized', 403

        collection = batch1_collection if batch == 1 else batch2_collection
        queue = list(collection.find())

        if not queue:
            return 'Queue is empty', 404

        merger = PdfMerger()
        temp_files = []

        # Download and merge PDFs
        for item in queue:
            response = requests.get(item['cloudinary_url'])
            temp_path = os.path.join(TEMP_DIR, f"temp_{item['original_filename']}")
            temp_files.append(temp_path)
            
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            for _ in range(item['copies']):
                merger.append(temp_path)

        # Save merged PDF
        output_path = os.path.join(TEMP_DIR, f'merged_batch_{batch}.pdf')
        merger.write(output_path)
        merger.close()

        # Clean up Cloudinary files and MongoDB records
        for item in queue:
            cloudinary.uploader.destroy(item['public_id'], resource_type="raw")
        collection.delete_many({})

        # Clean up temp files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        # Send merged PDF
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f'print_queue_batch{batch}_{datetime.now().strftime("%Y%m%d")}.pdf'
        )

        # Clean up merged PDF after sending
        @response.call_on_close
        def cleanup():
            if os.path.exists(output_path):
                os.remove(output_path)

        return response

    except Exception as e:
        return str(e), 500
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)