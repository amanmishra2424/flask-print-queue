from flask import Flask, request, send_file, jsonify, render_template_string
from flask_cors import CORS
from PyPDF2 import PdfMerger
import os
import json
from datetime import datetime
import hashlib

app = Flask(__name__)
CORS(app)

# Create necessary folders
UPLOAD_FOLDER = 'uploads'
QUEUE_FOLDER = 'print_queue'
for folder in [UPLOAD_FOLDER, QUEUE_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Files to store print queues
QUEUE_FILE_BATCH1 = 'print_queue/queue_batch1.json'
QUEUE_FILE_BATCH2 = 'print_queue/queue_batch2.json'

# Admin password (SHA-256 hashed)
ADMIN_PASSWORD = hashlib.sha256("jai ho".encode()).hexdigest()

def load_queue(batch):
    queue_file = QUEUE_FILE_BATCH1 if batch == 1 else QUEUE_FILE_BATCH2
    if os.path.exists(queue_file):
        with open(queue_file, 'r') as f:
            return json.load(f)
    return []

def save_queue(queue, batch):
    queue_file = QUEUE_FILE_BATCH1 if batch == 1 else QUEUE_FILE_BATCH2
    with open(queue_file, 'w') as f:
        json.dump(queue, f, indent=2)

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
            button:disabled {
                background-color: #cccccc;
            }
            .status {
                margin-top: 15px;
                text-align: center;
                color: #666;
            }
            .error {
                color: red;
                margin-top: 10px;
                text-align: center;
            }
            .queue-list {
                margin-top: 20px;
            }
            .queue-item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            .batch-selection {
                display: flex;
                justify-content: space-between;
                margin-bottom: 15px;
            }
            .admin-section {
                margin-top: 30px;
                padding-top: 20px;
                border-top: 2px solid #eee;
            }
            .admin-password {
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 style="text-align: center;">Print Service Queue</h1>
            
            <div class="batch-selection">
                <button onclick="selectBatch(1)">Batch 1</button>
                <button onclick="selectBatch(2)">Batch 2</button>
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
            
            <input type="hidden" id="selectedBatch" value="1">
            
            <button id="submitButton" onclick="submitPrint()">Submit Print Request</button>
            
            <div id="status" class="status"></div>
            <div id="error" class="error"></div>
        </div>

        <!-- Admin Section -->
        <div class="container admin-section">
            <h2 style="text-align: center;">Admin Controls</h2>
            <div class="admin-password">
                <label for="adminPassword">Admin Password:</label>
                <input type="password" id="adminPassword">
            </div>
            <button class="admin" onclick="viewQueue()">View Current Queue</button>
            <button class="admin" onclick="mergePrintQueue()">Merge All PDFs for Printing</button>
            
            <div id="queueList" class="queue-list"></div>
        </div>

        <script>
            let currentBatch = 1;

            function selectBatch(batch) {
                currentBatch = batch;
                document.getElementById('selectedBatch').value = batch;
                document.querySelector('.batch-selection').querySelectorAll('button').forEach(btn => {
                    btn.style.backgroundColor = batch === 1 ? '#4CAF50' : '#2196F3';
                });
            }

            async function submitPrint() {
                const nameInput = document.getElementById('studentName');
                const fileInput = document.getElementById('pdfFile');
                const copies = document.getElementById('copies').value;
                const statusDiv = document.getElementById('status');
                const errorDiv = document.getElementById('error');
                const submitButton = document.getElementById('submitButton');
                const batch = document.getElementById('selectedBatch').value;

                statusDiv.textContent = '';
                errorDiv.textContent = '';

                if (!nameInput.value.trim()) {
                    errorDiv.textContent = 'Please enter your name';
                    return;
                }

                if (!fileInput.files[0]) {
                    errorDiv.textContent = 'Please select a PDF file';
                    return;
                }

                if (!fileInput.files[0].name.toLowerCase().endsWith('.pdf')) {
                    errorDiv.textContent = 'Please select a valid PDF file';
                    return;
                }

                const formData = new FormData();
                formData.append('pdf', fileInput.files[0]);
                formData.append('copies', copies);
                formData.append('name', nameInput.value);
                formData.append('batch', batch);

                try {
                    submitButton.disabled = true;
                    statusDiv.textContent = 'Submitting request...';

                    const response = await fetch('/submit', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        statusDiv.textContent = `Print request submitted for Batch ${batch} successfully!`;
                        nameInput.value = '';
                        fileInput.value = '';
                        copies.value = '1';
                    } else {
                        errorDiv.textContent = 'Error submitting request';
                    }
                } catch (error) {
                    errorDiv.textContent = 'Error uploading file';
                    console.error('Error:', error);
                } finally {
                    submitButton.disabled = false;
                }
            }

            async function viewQueue() {
                const queueList = document.getElementById('queueList');
                const adminPassword = document.getElementById('adminPassword').value;
                const batch = currentBatch;

                try {
                    const response = await fetch(`/queue?batch=${batch}&password=${encodeURIComponent(adminPassword)}`);
                    
                    if (response.status === 403) {
                        queueList.innerHTML = 'Incorrect admin password';
                        return;
                    }

                    const queue = await response.json();
                    
                    queueList.innerHTML = `<h3>Batch ${batch} Queue:</h3>` + 
                        queue.map(item => `
                            <div class="queue-item">
                                <strong>${item.name}</strong> - ${item.original_filename} (${item.copies} copies)
                                <br>Submitted: ${item.timestamp}
                            </div>
                        `).join('');
                } catch (error) {
                    queueList.innerHTML = 'Error loading queue';
                }
            }

            async function mergePrintQueue() {
                const adminPassword = document.getElementById('adminPassword').value;
                const batch = currentBatch;

                try {
                    const response = await fetch(`/merge-all?batch=${batch}&password=${encodeURIComponent(adminPassword)}`, {
                        method: 'POST'
                    });

                    if (response.status === 403) {
                        alert('Incorrect admin password');
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
        copies = int(request.form.get('copies', 1))
        name = request.form.get('name', 'Unknown')
        batch = int(request.form.get('batch', 1))
        
        if file.filename == '':
            return 'No file selected', 400
            
        if not file.filename.lower().endswith('.pdf'):
            return 'Invalid file type - Please upload a PDF file', 400
        
        # Save the file
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = os.path.join(QUEUE_FOLDER, filename)
        file.save(file_path)
        
        # Add to queue
        queue = load_queue(batch)
        queue.append({
            'name': name,
            'filename': filename,
            'original_filename': file.filename,
            'copies': copies,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_queue(queue, batch)
        
        return 'Success', 200
        
    except Exception as e:
        return str(e), 500

@app.route('/queue')
def get_queue():
    try:
        # Check admin password
        admin_password = request.args.get('password', '')
        if hashlib.sha256(admin_password.encode()).hexdigest() != ADMIN_PASSWORD:
            return 'Unauthorized', 403
        
        batch = int(request.args.get('batch', 1))
        return jsonify(load_queue(batch))
    except Exception as e:
        return str(e), 500

@app.route('/merge-all', methods=['POST'])
def merge_all():
    try:
        # Check admin password
        admin_password = request.args.get('password', '')
        if hashlib.sha256(admin_password.encode()).hexdigest() != ADMIN_PASSWORD:
            return 'Unauthorized', 403
        
        batch = int(request.args.get('batch', 1))
        queue = load_queue(batch)
        
        if not queue:
            return 'Queue is empty', 400
            
        merger = PdfMerger()
        
        # Merge all PDFs in queue with their specified copies
        for item in queue:
            file_path = os.path.join(QUEUE_FOLDER, item['filename'])
            if os.path.exists(file_path):
                for _ in range(item['copies']):
                    merger.append(file_path)
        
        # Save merged file
        output_path = os.path.join(UPLOAD_FOLDER, f'merged_queue_batch{batch}.pdf')
        merger.write(output_path)
        merger.close()
        
        # Clear the queue after merging
        save_queue([], batch)
        
        # Remove individual PDF files from queue folder
        for item in queue:
            file_path = os.path.join(QUEUE_FOLDER, item['filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Send the merged file
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f'print_queue_batch{batch}_{datetime.now().strftime("%Y%m%d")}.pdf'
        )
        
        # Clean up
        @response.call_on_close
        def cleanup():
            if os.path.exists(output_path):
                os.remove(output_path)
                
        return response
        
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)