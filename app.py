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
from pathlib import Path
import logging
import sys

# Enhanced logging configuration
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Cloudinary Configuration
try:
    cloudinary.config(
        cloud_name='disht9nbk',
        api_key='587297388865477',
        api_secret='44JUq6ZcveKznDxyXT7OT4GyoTs'
    )
except Exception as e:
    logger.error(f"Cloudinary configuration error: {str(e)}")
    raise

# MongoDB Configuration
def get_mongodb_connection():
    try:
        MONGO_URI = 'mongodb+srv://print_queue_db:jai_ho@aman.dlsk6.mongodb.net/'
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Test the connection
        client.server_info()
        return client
    except Exception as e:
        logger.error(f"MongoDB connection error: {str(e)}")
        raise

# Initialize MongoDB connection
try:
    client = get_mongodb_connection()
    db = client['print_queue_db']
    batch1_collection = db['batch1_queue']
    batch2_collection = db['batch2_queue']
except Exception as e:
    logger.error(f"Failed to initialize MongoDB: {str(e)}")
    raise

# Set up temporary directory
TEMP_DIR = Path(tempfile.gettempdir()) / 'print_queue'
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Admin password (using the one from your code)
ADMIN_PASSWORD = hashlib.sha256('jai ho'.encode()).hexdigest()

# HTML template for the main page
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Print Queue System</title>
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

        button:hover {
            background-color: var(--primary-dark);
        }

        button i {
            font-size: 1.1rem;
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

        /* File input styling */
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-print"></i> Print Queue System</h1>
        </div>
        
        <div class="card">
            <h2><i class="fas fa-file-upload"></i> Submit Print Job</h2>
            <div class="form-group">
                <label for="studentName">Name</label>
                <input type="text" id="studentName" placeholder="Enter your name" required>
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
                <select id="batchSelect" required>
                    <option value="1">Batch 1</option>
                    <option value="2">Batch 2</option>
                </select>
            </div>
            
            <button onclick="submitPrint()">
                <i class="fas fa-paper-plane"></i> Submit Print Job
            </button>
            
            <div id="status"></div>
        </div>

        <div class="card">
            <h2><i class="fas fa-lock"></i> Admin Controls</h2>
            <div class="form-group">
                <label for="adminPassword">Admin Password</label>
                <input type="password" id="adminPassword" placeholder="Enter admin password">
            </div>
            
            <div class="button-group">
                <button onclick="viewQueue()">
                    <i class="fas fa-list"></i> View Queue
                </button>
                <button onclick="mergePrintQueue()">
                    <i class="fas fa-file-pdf"></i> Merge and Download
                </button>
            </div>
        </div>

        <div id="queueList"></div>
    </div>

    <script>
        // Update the file input button text when a file is selected
        document.getElementById('pdfFile').addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name || 'No file selected';
            document.getElementById('fileInputButton').innerHTML = `
                <i class="fas fa-file-pdf"></i>
                <p>${fileName}</p>
            `;
        });

        async function submitPrint() {
            const status = document.getElementById('status');
            status.textContent = 'Submitting...';
            status.className = 'status';
            
            try {
                const name = document.getElementById('studentName').value;
                const file = document.getElementById('pdfFile').files[0];
                const copies = document.getElementById('copies').value;
                const batch = document.getElementById('batchSelect').value;

                if (!name || !file || !copies || !batch) {
                    status.textContent = 'Please fill all fields';
                    status.className = 'status error';
                    return;
                }

                const formData = new FormData();
                formData.append('name', name);
                formData.append('pdf', file);
                formData.append('copies', copies);
                formData.append('batch', batch);

                const response = await fetch('/submit', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (response.ok) {
                    status.textContent = result.message;
                    status.className = 'status success';
                    // Clear form
                    document.getElementById('studentName').value = '';
                    document.getElementById('pdfFile').value = '';
                    document.getElementById('copies').value = '1';
                    document.getElementById('fileInputButton').innerHTML = `
                        <i class="fas fa-cloud-upload-alt"></i>
                        <p>Drop your PDF file here or click to browse</p>
                        <small>Only PDF files are accepted</small>
                    `;
                } else {
                    throw new Error(result.error || 'Submission failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
        }

        async function mergePrintQueue() {
            try {
                const password = document.getElementById('adminPassword').value;
                const batch = document.getElementById('batchSelect').value;

                if (!password || !batch) {
                    alert('Please enter password and select batch');
                    return;
                }

                const response = await fetch(`/merge?batch=${batch}&password=${encodeURIComponent(password)}`, {
                    method: 'POST'
                });

                if (!response.ok) {
                    const result = await response.json();
                    throw new Error(result.error || 'Merge failed');
                }

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `print_queue_batch${batch}_${new Date().toISOString().split('T')[0]}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                
                await viewQueue();
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }

        async function viewQueue() {
            const queueList = document.getElementById('queueList');
            const password = document.getElementById('adminPassword').value;
            const batch = document.getElementById('batchSelect').value;

            try {
                if (!password) {
                    queueList.innerHTML = '<div class="status error">Please enter admin password</div>';
                    return;
                }

                const response = await fetch(`/queue?batch=${batch}&password=${encodeURIComponent(password)}`);
                
                if (!response.ok) {
                    throw new Error('Unable to view queue');
                }

                const queue = await response.json();
                
                if (queue.length === 0) {
                    queueList.innerHTML = '<div class="status">Queue is empty</div>';
                    return;
                }

                queueList.innerHTML = queue.map(item => `
                    <div class="queue-item">
                        <strong>${item.name}</strong>
                        <div class="queue-info">
                            <div>
                                <i class="fas fa-file-pdf"></i>
                                ${item.original_filename}
                            </div>
                            <div>
                                <i class="fas fa-copy"></i>
                                ${item.copies} copies
                            </div>
                            <div>
                                <i class="fas fa-clock"></i>
                                ${item.timestamp}
                            </div>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                queueList.innerHTML = `<div class="status error">Error: ${error.message}</div>`;
            }
        }
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
        # Test MongoDB connection
        client.server_info()
        # Test Cloudinary connection
        cloudinary.api.ping()
        # Test temp directory
        test_file = TEMP_DIR / 'health_check.txt'
        test_file.write_text('test')
        test_file.unlink()
        return jsonify({"status": "healthy"}), 200
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

        # Validation
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

        # Save file temporarily
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{Path(file.filename).stem}.pdf"
        temp_path = TEMP_DIR / safe_filename

        try:
            file.save(str(temp_path))

            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                str(temp_path),
                resource_type="raw",
                folder="print_queue",
                public_id=f"print_{timestamp}_{Path(file.filename).stem}"
            )

            # Store in MongoDB
            collection = batch1_collection if batch == 1 else batch2_collection
            document = {
                'name': name,
                'original_filename': file.filename,
                'cloudinary_url': upload_result['secure_url'],
                'public_id': upload_result['public_id'],
                'copies': copies,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            collection.insert_one(document)

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
        queue = list(collection.find({}, {'_id': 0}))
        return jsonify(queue)

    except Exception as e:
        logger.error(f"View queue error: {str(e)}")
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

            # Clean up Cloudinary files and MongoDB records
            for item in queue:
                try:
                    cloudinary.uploader.destroy(item['public_id'], resource_type="raw")
                except Exception as e:
                    logger.error(f"Cloudinary cleanup error: {str(e)}")

            collection.delete_many({})

            return send_file(
                str(output_path),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'print_queue_batch{batch}_{datetime.now().strftime("%Y%m%d")}.pdf'
            )

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()
            if merge_dir and merge_dir.exists():
                try:
                    merge_dir.rmdir()
                except Exception as e:
                    logger.error(f"Error removing merge directory: {str(e)}")

    except Exception as e:
        logger.error(f"Merge queue error: {str(e)}")
        # Clean up on error
        if merge_dir and merge_dir.exists():
            try:
                for file in merge_dir.glob('*'):
                    file.unlink()
                merge_dir.rmdir()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {str(cleanup_error)}")
        return jsonify({'error': str(e)}), 500

def create_required_directories():
    """Create necessary directories for the application"""
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Successfully created required directories")
    except Exception as e:
        logger.error(f"Failed to create directories: {str(e)}")
        raise

def test_connections():
    """Test database and storage connections"""
    try:
        # Test MongoDB connection
        client.server_info()
        logger.info("Successfully connected to MongoDB")
        
        # Test Cloudinary configuration
        cloudinary.api.ping()
        logger.info("Successfully connected to Cloudinary")
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        # Initialize application requirements
        create_required_directories()
        test_connections()
        
        # Start the Flask application
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting server on port {port}")
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        sys.exit(1)

