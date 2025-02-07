from flask import Flask, request, send_file, jsonify, render_template_string
from flask_cors import CORS
from PyPDF2 import PdfMerger, PdfReader
from bson import ObjectId
import os
import hashlib
import requests
from datetime import datetime
import cloudinary
import cloudinary.uploader
import cloudinary.api
from pymongo import MongoClient
import tempfile
from pathlib import Path
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

try:
    cloudinary.config(
        cloud_name='disht9nbk',
        api_key='587297388865477',
        api_secret='44JUq6ZcveKznDxyXT7OT4GyoTs'
    )
except Exception as e:
    logger.error(f"Cloudinary configuration error: {str(e)}")
    raise

def get_mongodb_connection():
    try:
        MONGO_URI = 'mongodb+srv://print_queue_db:jai_ho@aman.dlsk6.mongodb.net/'
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client
    except Exception as e:
        logger.error(f"MongoDB connection error: {str(e)}")
        raise

try:
    client = get_mongodb_connection()
    db = client['print_queue_db']
    batch1_collection = db['batch1_queue']
    batch2_collection = db['batch2_queue']
except Exception as e:
    logger.error(f"Failed to initialize MongoDB: {str(e)}")
    raise

TEMP_DIR = Path(tempfile.gettempdir()) / 'print_queue'
TEMP_DIR.mkdir(parents=True, exist_ok=True)
ADMIN_PASSWORD = hashlib.sha256('jai ho'.encode()).hexdigest()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Print For You</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4f46e5;
            --primary-dark: #4338ca;
            --secondary-color: #f3f4f6;
            --success-color: #10b981;
            --error-color: #ef4444;

            --text-color: #1f2937;
            --border-radius: 8px;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            background-color: #f9fafb;
            color: var(--text-color);
            padding: 2rem;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 2rem;
            color: var(--primary-color);
        }

        .card {
            background: white;
            border-radius: var(--border-radius);
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow);
        }

        .card h2 {
            color: var(--primary-color);
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
            color: var(--text-color);
        }

        input, select {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #e5e7eb;
            border-radius: var(--border-radius);
            font-size: 1rem;
            transition: border-color 0.2s;
        }

        input:focus, select:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }

        .button-group {
            display: flex;
            gap: 1rem;
            margin-top: 1.5rem;
        }

        button {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: var(--border-radius);
            font-size: 1rem;
            cursor: pointer;
            transition: background-color 0.2s;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
                    /* Footer Styles */
        .footer {
            background-color: #f9fafb;
            padding: 0.5rem;
            text-align: center;
            border-top: 1px solid #e5e7eb;
            margin-top: 1rem;
            color: #6b7280;
            height: 100px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }   

        .footer-content {
            max-width: 800px;
            margin: 0 auto;
        }

        .footer-slogan {
            font-style: italic;
            font-size: 1.1rem;
            margin-bottom: 1rem;
            color: var(--primary-color);
        }

        .footer-contact {
            display: flex;
            justify-content: center;
            gap: 1.5rem;
            margin-top: 1rem;
        }

        .footer-contact a {
            color: #6b7280;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: color 0.2s;
        }

        .footer-contact a:hover {
            color: var(--primary-color);
        }

        button:hover {
            background-color: var(--primary-dark);
        }

        button.delete-btn {
            background-color: var(--error-color);
            padding: 0.5rem 1rem;
        }

        button.delete-btn:hover {
            background-color: #dc2626;
        }

        .status {
            padding: 1rem;
            margin-top: 1rem;
            border-radius: var(--border-radius);
            font-weight: 500;
        }

        .success {
            background-color: #ecfdf5;
            color: var(--success-color);
            border: 1px solid #a7f3d0;
        }

        .error {
            background-color: #fef2f2;
            color: var(--error-color);
            border: 1px solid #fecaca;
        }

        .queue-item {
            background: var(--secondary-color);
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: var(--border-radius);
            border-left: 4px solid var(--primary-color);
        }

        .queue-item strong {
            color: var(--primary-color);
        }

        .queue-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 0.5rem;
        }

        .queue-info div {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .queue-info i {
            color: var(--primary-color);
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 1000;
        }

        .modal-content {
            background-color: white;
            margin: 15% auto;
            padding: 2rem;
            border-radius: var(--border-radius);
            width: 90%;
            max-width: 500px;
        }

        .modal-buttons {
            display: flex;
            justify-content: flex-end;
            gap: 1rem;
            margin-top: 1.5rem;
        }

        .modal-buttons button {
            padding: 0.5rem 1rem;
        }

        .file-input-wrapper {
            position: relative;
            overflow: hidden;
            display: inline-block;
            width: 100%;
        }

        .file-input-wrapper input[type="file"] {
            font-size: 100px;
            position: absolute;
            left: 0;
            top: 0;
            opacity: 0;
            cursor: pointer;
        }

        .file-input-button {
            background-color: var(--secondary-color);
            border: 1px dashed var(--primary-color);
            padding: 2rem;
            text-align: center;
            border-radius: var(--border-radius);
            cursor: pointer;
            transition: all 0.2s;
        }

        .file-input-button:hover {
            background-color: #e5e7eb;
        }

        .file-input-button i {
            font-size: 2rem;
            color: var(--primary-color);
            margin-bottom: 1rem;
        }

        @media (max-width: 768px) {
            body {
                padding: 1rem;
            }

            .button-group {
                flex-direction: column;
            }

            button {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-print"></i> Welcome, We Print For you</h1>
        </div>
        
        <div class="card">
            <h2><i class="fas fa-file-upload"></i> For Students</h2>
            <div class="form-group">
                <label for="studentName">Name</label>
                <input type="text" id="studentName" placeholder="Enter your name" required>
            </div>
            <div style="width:157px; height:44px">
            <a href="https://smallpdf.com/word-to-pdf" class="convert-btn" target="_blank">
                <button><i class="fas fa-file-pdf"></i> Word To Pdf</button>
            </a>
                </div>
            <div class="form-group">
                <label for="pdfFile">PDF File</label>
                <div class="file-input-wrapper">
                    <div class="file-input-button" id="fileInputButton">
                        <i class="fas fa-cloud-upload-alt"></i>
                        <p>Drop your PDF file here or click to browse</p>
                        <small>Only PDF files are accepted</small>
                    </div>
                    <input type="file" id="pdfFile" accept=".pdf" required>
                </div>
            </div>
            
            <div class="form-group">
                <label for="copies">Number of Copies</label>
                <input type="number" id="copies" min="1" value="1" required>
            </div>
            
            <div class="form-group">
                <label for="batchSelect">Batch</label>
                <select id="batchSelect" required onchange="viewQueue()">
                    <option value="1">Batch 1</option>
                    <option value="2">Batch 2</option>
                </select>
            </div>
            
            <button onclick="submitPrint()">
                <i class="fas fa-paper-plane"></i> Submit Print Job
            </button>
            
            <div id="status"></div>
        </div>

        <div id="queueList"></div>

        <div class="card">
            <h2><i class="fas fa-lock"></i> Admin Controls</h2>
            <div class="form-group">
                <label for="adminPassword">Admin Password</label>
                <div style="position: relative;">
                    <input type="password" id="adminPassword" placeholder="Enter admin password">
                    <i class="fas fa-eye password-toggle" 
                       onclick="togglePasswordVisibility()" 
                       style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); cursor: pointer;"></i>
                </div>
            </div>
            
            <div class="button-group">
                <button onclick="mergePrintQueue()">
                    <i class="fas fa-file-pdf"></i> Merge and Download
                </button>
            </div>
        </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div id="deleteModal" class="modal">
        <div class="modal-content">
            <h3>Confirm Deletion</h3>
            <p>Are you sure you want to delete this print job?</p>
            <div class="modal-buttons">
                <button onclick="confirmDelete()" class="delete-btn">
                    <i class="fas fa-trash"></i> Delete
                </button>
                <button onclick="closeModal()" style="background-color: #6b7280;">
                    <i class="fas fa-times"></i> Cancel
                </button>
            </div>
        </div>
    </div>
            <div style="height:100px;">
              <footer class="footer">
       
     <div class="footer-content">
            <div class="footer-slogan">
                "Print Smarter, Print Faster: Your Documents, Our Passion"
            </div>
            <div class="copyright">
                &copy; 2025 Print For You. All Rights Reserved.
            </div>
            <div class="footer-contact">
                <a href="mailto:amanmishraaa767@gmail.com">
                    <i class="fas fa-envelope"></i> amanmishraaa767@gmail.com
                </a>
                <a href="tel:+917678023772">
                    <i class="fas fa-phone"></i> 7678023772
                </a>
            </div>
        </div>
         </footer>
         </div>
    <script>
        // File input handling
        document.getElementById('pdfFile').addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name || 'No file selected';
            document.getElementById('fileInputButton').querySelector('p').textContent = fileName;
        });

        // Toggle password visibility
        function togglePasswordVisibility() {
            const passwordInput = document.getElementById('adminPassword');
            const icon = document.querySelector('.password-toggle');
            
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                passwordInput.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        }

        let deleteItemId = null;

        function showDeleteModal(id) {
            deleteItemId = id;
            document.getElementById('deleteModal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('deleteModal').style.display = 'none';
            deleteItemId = null;
        }

        async function confirmDelete() {
            if (!deleteItemId) return;
            
            const status = document.getElementById('status');
            const batch = document.getElementById('batchSelect').value;
            
            try {
                const response = await fetch(`/delete/${deleteItemId}?batch=${batch}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    status.textContent = data.message || 'Print job deleted successfully';
                    status.className = 'status success';
                    viewQueue();
                } else {
                    throw new Error(data.error || 'Delete failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
            
            closeModal();
        }

        async function submitPrint() {
            const status = document.getElementById('status');
            const studentName = document.getElementById('studentName').value;
            const pdfFile = document.getElementById('pdfFile').files[0];
            const copies = document.getElementById('copies').value;
            const batch = document.getElementById('batchSelect').value;

            if (!studentName || !pdfFile || !copies || !batch) {
                status.textContent = 'Please fill in all fields';
                status.className = 'status error';
                return;
            }

            const formData = new FormData();
            formData.append('name', studentName);
            formData.append('pdf', pdfFile);
            formData.append('copies', copies);
            formData.append('batch', batch);

            try {
                status.textContent = 'Submitting print job...';
                status.className = 'status';

                const response = await fetch('/submit', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    status.textContent = data.message || 'Print job submitted successfully';
                    status.className = 'status success';
                    
                    // Clear form
                    document.getElementById('studentName').value = '';
                    document.getElementById('pdfFile').value = '';
                    document.getElementById('copies').value = '1';
                    document.getElementById('fileInputButton').querySelector('p').textContent = 'Drop your PDF file here or click to browse';
                    
                    // Refresh queue
                    viewQueue();
                } else {
                    throw new Error(data.error || 'Submission failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
        }

        async function viewQueue() {
            const queueList = document.getElementById('queueList');
            const batch = document.getElementById('batchSelect').value;

            try {
                const response = await fetch(`/queue?batch=${batch}`);
                const queue = await response.json();

                if (!response.ok) {
                    throw new Error(queue.error || 'Failed to fetch queue');
                }

                if (queue.length === 0) {
                    queueList.innerHTML = `
                        <div class="card">
                            <h2><i class="fas fa-list"></i> Print Queue (Batch ${batch})</h2>
                            <p>Queue is empty</p>
                        </div>`;
                    return;
                }

                let queueHTML = `
                    <div class="card">
                        <h2><i class="fas fa-list"></i> Print Queue (Batch ${batch})</h2>`;

                queue.forEach((item, index) => {
                    queueHTML += `
                        <div class="queue-item">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <strong>#${index + 1}</strong>
                                <button onclick="showDeleteModal('${item._id}')" class="delete-btn">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                            <div class="queue-info">
                                <div><i class="fas fa-user"></i> ${item.name}</div>
                                <div><i class="fas fa-file-pdf"></i> ${item.original_filename}</div>
                                <div><i class="fas fa-copy"></i> ${item.copies} copies</div>
                                <div><i class="fas fa-file-alt"></i> ${item.page_count} pages</div>
                                <div><i class="fas fa-clock"></i> ${item.timestamp}</div>
                            </div>
                        </div>`;
                });

                queueHTML += '</div>';
                queueList.innerHTML = queueHTML;

            } catch (error) {
                queueList.innerHTML = `
                    <div class="card">
                        <h2><i class="fas fa-list"></i> Print Queue (Batch ${batch})</h2>
                        <div class="status error">Error: ${error.message}</div>
                    </div>`;
            }
        }

        async function mergePrintQueue() {
            const status = document.getElementById('status');
            const password = document.getElementById('adminPassword').value;
            const batch = document.getElementById('batchSelect').value;

            if (!password) {
                status.textContent = 'Please enter admin password';
                status.className = 'status error';
                return;
            }

            try {
                status.textContent = 'Merging PDFs...';
                status.className = 'status';

                const response = await fetch(`/merge?password=${encodeURIComponent(password)}&batch=${batch}`, {
                    method: 'POST'
                });

                if (response.ok) {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/pdf')) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `print_queue_batch${batch}_${new Date().toISOString().split('T')[0]}.pdf`;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.body.removeChild(a);

                        status.textContent = 'PDFs merged and downloaded successfully. Queue has been cleared.';
                        status.className = 'status success';
                        
                        document.getElementById('adminPassword').value = '';
                        
                        setTimeout(viewQueue, 1000);
                    } else {
                        throw new Error('Invalid response format');
                    }
                } else {
                    const error = await response.json();
                    throw new Error(error.error || 'Merge failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
        }

        // Add auto-refresh functionality
        function startQueueAutoRefresh() {
            setInterval(viewQueue, 30000); // Refresh every 30 seconds
        }

        // Initialize auto-refresh when page loads
        document.addEventListener('DOMContentLoaded', () => {
            viewQueue();
            startQueueAutoRefresh();
        });

        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('deleteModal');
            if (event.target === modal) {
                closeModal();
            }
        }
        <div style="height:200px;">
           <footer class="footer";>
       
                <div class="footer-content">
            <div class="footer-slogan">
                "Print Smarter, Print Faster: Your Documents, Our Passion"
            </div>
            <div class="copyright">
                &copy; 2025 Print For You. All Rights Reserved.
            </div>
            <div class="footer-contact">
                <a href="mailto:amanmishraaa767@gmail.com">
                    <i class="fas fa-envelope"></i> amanmishraaa767@gmail.com
                </a>
                <a href="tel:+917678023772">
                    <i class="fas fa-phone"></i> 7678023772
                </a>
            </div>
        </div>
         </footer>
         </div>
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/health')
def health_check():
    try:
        client.server_info()
        cloudinary.api.ping()
        test_file = TEMP_DIR / 'health_check.txt'
        test_file.write_text('test')
        test_file.unlink()
        return "Server Working on port http://127.0.0.1:5000/", 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/submit', methods=['POST'])
def submit_print():
    try:
        if 'pdf' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['pdf']
        name = request.form.get('name')
        copies = request.form.get('copies')
        batch = request.form.get('batch')
        
        if not all([name, copies, batch, file.filename]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        try:
            copies = int(copies)
            batch = int(batch)
            if copies < 1 or batch not in [1, 2]:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid copies or batch value'}), 400

        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{Path(file.filename).stem}.pdf"
        temp_path = TEMP_DIR / safe_filename

        try:
            file.save(str(temp_path))
            
            # Get page count
            pdf_reader = PdfReader(str(temp_path))
            page_count = len(pdf_reader.pages)
            
            upload_result = cloudinary.uploader.upload(
                str(temp_path),
                resource_type="raw",
                folder="print_queue",
                public_id=f"print_{timestamp}_{Path(file.filename).stem}"
            )
            
            collection = batch1_collection if batch == 1 else batch2_collection
            document = {
                'name': name,
                'original_filename': file.filename,
                'cloudinary_url': upload_result['secure_url'],
                'public_id': upload_result['public_id'],
                'copies': copies,
                'page_count': page_count,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            result = collection.insert_one(document)
            document['_id'] = str(result.inserted_id)

            return jsonify({'message': 'Print request submitted successfully'}), 200

        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return jsonify({'error': 'Error processing file'}), 500
        finally:
            if temp_path.exists():
                temp_path.unlink()

    except Exception as e:
        logger.error(f"Submit print error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/queue', methods=['GET'])
def view_queue():
    try:
        batch = request.args.get('batch')

        if not batch:
            return jsonify({'error': 'Batch number is required'}), 400

        try:
            batch = int(batch)
            if batch not in [1, 2]:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid batch number'}), 400

        collection = batch1_collection if batch == 1 else batch2_collection
        queue = list(collection.find())
        
        # Convert ObjectId to string for JSON serialization
        for item in queue:
            item['_id'] = str(item['_id'])
            
        return jsonify(queue)

    except Exception as e:
        logger.error(f"View queue error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/delete/<item_id>', methods=['DELETE'])
def delete_print_job(item_id):
    try:
        batch = request.args.get('batch')
        if not batch:
            return jsonify({'error': 'Batch number is required'}), 400

        try:
            batch = int(batch)
            if batch not in [1, 2]:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid batch number'}), 400

        collection = batch1_collection if batch == 1 else batch2_collection
        
        # Find the document first to get Cloudinary information
        document = collection.find_one({'_id': ObjectId(item_id)})
        if not document:
            return jsonify({'error': 'Print job not found'}), 404

        # Delete from Cloudinary
        try:
            cloudinary.uploader.destroy(document['public_id'], resource_type="raw")
        except Exception as e:
            logger.error(f"Error deleting from Cloudinary: {str(e)}")

        # Delete from MongoDB
        result = collection.delete_one({'_id': ObjectId(item_id)})
        
        if result.deleted_count == 0:
            return jsonify({'error': 'Print job not found'}), 404

        return jsonify({'message': 'Print job deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Delete print job error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/merge', methods=['POST'])
def merge_queue():
    merge_dir = None
    try:
        password = request.args.get('password', '')
        batch = request.args.get('batch')

        if not batch or hashlib.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD:
            return jsonify({'error': 'Invalid credentials'}), 403

        try:
            batch = int(batch)
            if batch not in [1, 2]:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid batch number'}), 400

        collection = batch1_collection if batch == 1 else batch2_collection
        queue = list(collection.find())

        if not queue:
            return jsonify({'error': 'Queue is empty'}), 404

        merge_dir = Path(tempfile.mkdtemp(prefix='merge_', dir=TEMP_DIR))
        merger = PdfMerger()
        temp_files = []

        try:
            for item in queue:
                response = requests.get(item['cloudinary_url'], timeout=30)
                response.raise_for_status()
                
                temp_path = merge_dir / f"temp_{Path(item['original_filename']).name}"
                temp_files.append(temp_path)
                
                temp_path.write_bytes(response.content)
                
                for _ in range(item['copies']):
                    merger.append(str(temp_path))

            output_path = merge_dir / f'merged_batch_{batch}.pdf'
            merger.write(str(output_path))
            merger.close()

            cleanup_success = True
            for item in queue:
                try:
                    cloudinary.uploader.destroy(item['public_id'], resource_type="raw")
                except Exception as e:
                    logger.error(f"Cloudinary cleanup error: {str(e)}")
                    cleanup_success = False

            try:
                collection.delete_many({})
            except Exception as e:
                logger.error(f"MongoDB cleanup error: {str(e)}")
                cleanup_success = False

            if not cleanup_success:
                logger.warning("Some cleanup operations failed, but proceeding with merge download")

            return send_file(
                str(output_path),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'print_queue_batch{batch}_{datetime.now().strftime("%Y%m%d")}.pdf'
            )

        finally:
            for temp_file in temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception as e:
                    logger.error(f"Error removing temp file {temp_file}: {str(e)}")
            
            if merge_dir and merge_dir.exists():
                try:
                    for file in merge_dir.glob('*'):
                        try:
                            file.unlink()
                        except Exception as e:
                            logger.error(f"Error removing file in merge dir: {str(e)}")
                    merge_dir.rmdir()
                except Exception as e:
                    logger.error(f"Error removing merge directory: {str(e)}")

    except Exception as e:
        logger.error(f"Merge queue error: {str(e)}")
        if merge_dir and merge_dir.exists():
            try:
                for file in merge_dir.glob('*'):
                    try:
                        file.unlink()
                    except Exception:
                        pass
                merge_dir.rmdir()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {str(cleanup_error)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        client.server_info()  # Test MongoDB connection
        cloudinary.api.ping()  #
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=True)
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        sys.exit(1)