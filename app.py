import ssl
from flask import Flask, request, send_file, jsonify, render_template_string, session, redirect, url_for
from flask_cors import CORS
from PyPDF2 import PdfMerger, PdfReader
from bson import ObjectId
import os
import hashlib
import requests
from datetime import datetime
from pymongo import MongoClient
import tempfile
from pathlib import Path
import logging
import sys
import psutil
import json
from flask_bcrypt import Bcrypt
import asyncio
import aiohttp
import certifi
import concurrent.futures
import aiofiles
import math
from dotenv import load_dotenv
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import random
import base64
import uuid
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import shutil

load_dotenv()

# Update constants
GITHUB_TOKEN="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"
GITHUB_REPO = "amanmishra2424/printstorage"
GITHUB_API_URL = "https://api.github.com"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB max file size
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONCURRENT_DOWNLOADS = 5  # Define this constant for async downloads

# PhonePe keys
PHONEPE_MERCHANT_ID = "PGTESTPAYUAT143"
PHONEPE_SALT_KEY = "ab3ab177-b468-4791-8071-275c404d8ab0"
PHONEPE_SALT_INDEX = 1
PHONEPE_API_URL = "https://api-preprod.phonepe.com/apis/pg-sandbox"  # Use production URL in production

def log_memory_usage():
    """Log current memory usage"""
    process = psutil.Process(os.getpid())

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'A@2424'
CORS(app)
bcrypt = Bcrypt(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Replace with your SMTP server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'amankumar050804@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'kxqeipaqzwpohbmk'  # Replace with your email password
app.config['MAIL_DEFAULT_SENDER'] = 'amankumar050804@gmail.com'  # Replace with your email

mail = Mail(app)

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

def validate_batch(batch):
    try:
        batch = int(batch)
    except ValueError:
        return jsonify({'error': 'Invalid batch number'}), 400
    return batch

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
    users_collection = db['users']
    batch1_collection = db['batch1_queue']
    batch2_collection = db['batch2_queue']
    payment_requests_collection = db['payment_requests']
    phonepe_payments_collection = db['phonepe_payments']  # New collection for phonepe payments
except Exception as e:
    logger.error(f"Failed to initialize MongoDB: {str(e)}")
    raise

# Update existing users to include pending_dues field
users_collection.update_many(
    {'pending_dues': {'$exists': False}},
    {'$set': {'pending_dues': 0}}
)

TEMP_DIR = Path(tempfile.gettempdir()) / 'print_queue'
TEMP_DIR.mkdir(parents=True, exist_ok=True)
ADMIN_PASSWORD = hashlib.sha256('jai ho'.encode()).hexdigest()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Print For You</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        .footer {
            height: auto;
            background-color: white;
            color: var(--primary-color);
            padding: 1.5rem;
            margin-top: 2rem;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 0.5rem;
            width: 100%;
        }

        .footer-content {
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-bottom: 0.5rem;
            flex-wrap: wrap;
        }

        .footer a {
            color: var(--primary-color);
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .footer a:hover {
            text-decoration: underline;
        }

        .copyright {
            font-size: 0.9rem;
            opacity: 0.9;
        }

        @media (max-width: 768px) {
            .footer-content {
                flex-direction: column;
                gap: 0.5rem;
            }
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            background-color: #f9fafb;
            color: var(--text-color);
            padding: 1rem;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
            width: 100%;
        }

        .header {
            text-align: center;
            margin-bottom: 2rem;
            color: var(--primary-color);
        }

        .card {
            background: white;
            border-radius: var(--border-radius);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: var(--shadow);
            width: 100%;
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
            flex-wrap: wrap;
        }

        button {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: var(--border-radius);
            font-size: 1rem;
            cursor: pointer;
            transition: background-color 0.2s, filter 0.2s;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            filter: brightness(1.1);
        }

        button:hover {
            background-color: var(--primary-dark);
            filter: brightness(1.3);
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
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
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
            filter: brightness(1.1);
        }

        .modal-buttons button:hover {
            filter: brightness(1.3);
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
                padding: 0.5rem;
            }

            .button-group {
                flex-direction: column;
            }

            button {
                width: 100%;
            }
            
            .card {
                padding: 1rem;
            }
        }

        table {
            width: 100%;
            border-collapse: collapse;
            overflow-x: auto;
            display: block;
        }

        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }

        th {
            background-color: #f2f2f2;
        }

        tr:hover {
            background-color: #f5f5f5;
        }
        
        /* Payment confirmation modal */
        #paymentConfirmModal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 1000;
        }
        
        .payment-btn {
            background-color: #22c55e;
            margin-right: 10px;
        }
        
        .payment-btn:hover {
            background-color: #16a34a;
        }
        
        .phonepe-payment-button {
            background-color: #4f46e5;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        /* Dropdown styles */
        .dropdown {
            position: relative;
            display: inline-block;
            width: 100%;
        }
        
        .dropdown-content {
            display: none;
            position: absolute;
            background-color: white;
            min-width: 160px;
            box-shadow: var(--shadow);
            z-index: 1;
            border-radius: var(--border-radius);
            width: 100%;
        }
        
        .dropdown-content button {
            width: 100%;
            text-align: left;
            padding: 12px 16px;
            border: none;
            background: none;
            color: var(--text-color);
            cursor: pointer;
            border-radius: 0;
        }
        
        .dropdown-content button:hover {
            background-color: var(--secondary-color);
        }
        
        .dropdown-button {
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .show {
            display: block;
        }
        
        @media (min-width: 768px) {
            table {
                display: table;
                overflow-x: initial;
            }
            
            .dropdown {
                width: auto;
            }
            
            .dropdown-content {
                width: auto;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-print"></i> Welcome, We Print For you</h1>
        </div>

        {% if user %}
        <div class="card">
            <h2><i class="fas fa-user"></i> Welcome, {{ user['name'] }}</h2>
            <p>Your Pending Dues: ₹{{ pending_dues }}</p>
            <button onclick="logout()">
                <i class="fas fa-sign-out-alt"></i> Logout
            </button>
        </div>
        {% elif admin %}
        <div class="card">
            <h2><i class="fas fa-user-shield"></i> Admin Panel</h2>
            <button onclick="logout()">
                <i class="fas fa-sign-out-alt"></i> Logout
            </button>
        </div>
        {% else %}
        <div class="card" id="loginCard">
            <h2><i class="fas fa-sign-in-alt"></i> Login</h2>
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" placeholder="Enter your email" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" placeholder="Enter your password" required>
            </div>
            <button onclick="login()">
                <i class="fas fa-sign-in-alt"></i> Login
            </button>
            <div id="loginStatus" class="status"></div>
            <p>Don't have an account? <a href="#" onclick="showRegisterCard()">Register</a></p>
            <p>Admin? <a href="#" onclick="showAdminLoginCard()">Admin Login</a></p>
            <p>Forgot your password? <a href="#" onclick="showForgotPasswordCard()">Forgot Password</a></p>
        </div>

        <div class="card" id="registerCard" style="display: none;">
            <h2><i class="fas fa-user-plus"></i> Register</h2>
            <div class="form-group">
                <label for="registerName">Name</label>
                <input type="text" id="registerName" placeholder="Enter your name" required>
            </div>
            <div class="form-group">
                <label for="registerEmail">Email</label>
                <input type="email" id="registerEmail" placeholder="Enter your email" required>
            </div>
            <div class="form-group">
                <label for="registerPassword">Password</label>
                <input type="password" id="registerPassword" placeholder="Enter your password" required>
            </div>
            <div class="form-group">
                <label for="registerRollNo">Roll No</label>
                <input type="text" id="registerRollNo" placeholder="Enter your roll no" required>
            </div>
            <div class="form-group">
                <label for="registerBatch">Batch</label>
                <select id="registerBatch" required>
                    <option value="1">Batch 1</option>
                    <option value="2">Batch 2</option>
                </select>
            </div>
            <button onclick="register()">
                <i class="fas fa-user-plus"></i> Register
            </button>
            <div id="registerStatus" class="status"></div>
            <p>Already have an account? <a href="#" onclick="showLoginCard()">Login</a></p>
        </div>

        <div class="card" id="adminLoginCard" style="display: none;">
            <h2><i class="fas fa-user-shield"></i> Admin Login</h2>
            <div class="form-group">
                <label for="adminEmail">Email</label>
                <input type="email" id="adminEmail" placeholder="Enter admin email" required>
            </div>
            <div class="form-group">
                <label for="adminPassword">Password</label>
                <input type="password" id="adminPassword" placeholder="Enter admin password" required>
            </div>
            <button onclick="adminLogin()">
                <i class="fas fa-sign-in-alt"></i> Login
            </button>
            <div id="adminLoginStatus" class="status"></div>
            <p>Not an admin? <a href="#" onclick="showLoginCard()">User Login</a></p>
        </div>

        <div class="card" id="forgotPasswordCard" style="display: none;">
            <h2><i class="fas fa-key"></i> Forgot Password</h2>
            <div class="form-group">
                <label for="forgotPasswordEmail">Email</label>
                <input type="email" id="forgotPasswordEmail" placeholder="Enter your email" required>
            </div>
            <button onclick="forgotPassword()">
                <i class="fas fa-paper-plane"></i> Send Reset Link
            </button>
            <div id="forgotPasswordStatus" class="status"></div>
            <p>Remembered your password? <a href="#" onclick="showLoginCard()">Login</a></p>
        </div>
        {% endif %}

        {% if admin %}
        <div class="card">
            <h2><i class="fas fa-lock"></i> Admin Controls</h2>
            <div class="form-group">
                <label for="adminBatchSelect">Select Batch</label>
                <select id="adminBatchSelect" required>
                    <option value="1">Batch 1</option>
                    <option value="2">Batch 2</option>
                </select>
            </div>
            
            <!-- Admin dropdown menu -->
            <div class="dropdown">
                <button onclick="toggleAdminDropdown()" class="dropdown-button">
                    <span><i class="fas fa-cog"></i> Admin Actions</span>
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div id="adminDropdown" class="dropdown-content">
                    <button onclick="mergePrintQueue()">
                        <i class="fas fa-file-pdf"></i> Merge and Download
                    </button>
                    <button onclick="viewBilling()">
                        <i class="fas fa-money-bill-wave"></i> View Billing
                    </button>
                    <button onclick="viewPaymentRequests()">
                        <i class="fas fa-money-bill-wave"></i> View Payment Requests
                    </button>
                    <button onclick="viewAllQueues()">
                        <i class="fas fa-list"></i> View All Queues
                    </button>
                </div>
            </div>
            
            <div id="mergeStatus" class="status"></div>
        </div>

        <div class="card" id="billingCard" style="display: none;">
            <h2><i class="fas fa-money-bill-wave"></i> Billing Information</h2>
            <div id="billingInfo"></div>
        </div>

        <div class="card" id="paymentRequestsCard" style="display: none;">
            <h2><i class="fas fa-money-bill-wave"></i> Payment Requests</h2>
            <div id="paymentRequests"></div>
        </div>
        
        <div class="card" id="allQueuesCard" style="display: none;">
            <h2><i class="fas fa-list"></i> All Print Queues</h2>
            <div id="allQueuesContent"></div>
        </div>
        {% endif %}

        {% if user %}
        <div class="card">
            <h2><i class="fas fa-file-upload"></i> For Students</h2>
            <div class="form-group">
                <label for="studentName">Name</label>
                <input type="text" id="studentName" placeholder="Enter your name" value="{{ user['name'] }}" required>
            </div>

            <a href="https://smallpdf.com/word-to-pdf" class="convert-btn" target="_blank">
                <button><i class="fas fa-file-pdf"></i> Word To Pdf</button>
            </a>

            <div class="form-group">
                <label for="pdfFiles">PDF Files</label>
                <div class="file-input-wrapper">
                    <div class="file-input-button" id="fileInputButton">
                        <i class="fas fa-cloud-upload-alt"></i>
                        <p>Drop your PDF files here or click to browse</p>
                        <small>Only PDF files are accepted</small>
                    </div>
                    <input type="file" id="pdfFiles" accept=".pdf" multiple required>
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
        {% endif %}

        {% if user %}
        <div class="card">
            <h2><i class="fas fa-money-bill-wave"></i> Payment Options</h2>
            <div class="form-group">
                <label for="amountPaid">Amount Paid</label>
                <input type="number" id="amountPaid" placeholder="Enter the amount" required>
            </div>
            <!-- Update payment button to only show PhonePe -->
            <div class="button-group">
                <button onclick="submitPaymentRequest()">
                    <i class="fas fa-paper-plane"></i> Via Cash
                </button>
                <button onclick="showPhonePePayment()" class="payment-btn">
                    <i class="fas fa-mobile-alt"></i> Pay via PhonePe
                </button>
            </div>

            <div id="paymentRequestStatus" class="status"></div>
        </div>
        {% endif %}

        <div id="deleteModal" class="modal">
            <div class="modal-content">
                <h2>Confirm Delete</h2>
                <p>Are you sure you want to delete this print job?</p>
                <div class="modal-buttons">
                    <button onclick="deletePrintJob()">Delete</button>
                    <button onclick="closeModal()">Cancel</button>
                </div>
            </div>
        </div>
        
        <!-- Payment confirmation modal -->
        <div id="paymentConfirmModal" class="modal">
            <div class="modal-content">
                <h2><i class="fas fa-money-bill-wave"></i> Payment Confirmation</h2>
                <p id="paymentConfirmMessage"></p>
                <div class="modal-buttons">
                    <button onclick="initiatePhonePePayment()" class="payment-btn">Yes, Pay Now</button>
                    <button onclick="closePaymentModal()">No, Later</button>
                </div>
            </div>
        </div>
        
        <!-- PhonePe payment form container -->
        <div id="phonepe-container"></div>
        
        <footer class="footer">
            <div class="footer-content">
                <a href="tel:7678023772"><i class="fas fa-phone"></i> +91 7678023772</a>
                <a href="mailto:amanmishraaa767@gmail.com"><i class="fas fa-envelope"></i> amanmishraaa767@gmail.com</a>
            </div>
            <div class="copyright">
                Copyright &copy; 2025 We Print For You. All rights reserved.
            </div>
        </footer>
    </div>

    
    <script>
        // File input handling
        document.getElementById('pdfFiles')?.addEventListener('change', function(e) {
            const files = e.target.files;
            const fileNames = Array.from(files).map(file => file.name).join(', ') || 'No files selected';
            document.getElementById('fileInputButton').querySelector('p').textContent = fileNames;
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
        
        // Admin dropdown toggle
        function toggleAdminDropdown() {
            document.getElementById("adminDropdown").classList.toggle("show");
        }
        
        // Close dropdown when clicking outside
        window.onclick = function(event) {
            if (!event.target.matches('.dropdown-button') && !event.target.matches('.dropdown-button *')) {
                const dropdowns = document.getElementsByClassName("dropdown-content");
                for (let i = 0; i < dropdowns.length; i++) {
                    const openDropdown = dropdowns[i];
                    if (openDropdown.classList.contains('show')) {
                        openDropdown.classList.remove('show');
                    }
                }
            }
        }

        let deleteItemId = null;
        let pendingDuesAmount = {{ pending_dues if pending_dues else 0 }};

        function showDeleteModal(id) {
            deleteItemId = id;
            document.getElementById('deleteModal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('deleteModal').style.display = 'none';
            deleteItemId = null;
        }
        
        function closePaymentModal() {
            document.getElementById('paymentConfirmModal').style.display = 'none';
        }
        
        function showPhonePePayment() {
            if (pendingDuesAmount <= 0) {
                alert("You don't have any pending dues to pay.");
                return;
            }
            
            const amountInput = document.getElementById('amountPaid');
            const amount = parseFloat(amountInput.value);
            
            if (!amount || amount <= 0) {
                alert("Please enter a valid amount to pay.");
                return;
            }
            
            if (amount > pendingDuesAmount) {
                alert("The amount you entered is greater than your pending dues. Please enter a smaller amount.");
                return;
            }
            
            const paymentConfirmMessage = document.getElementById('paymentConfirmMessage');
            paymentConfirmMessage.textContent = `Your total pending due is ₹${pendingDuesAmount}. Do you wish to pay ₹${amount} now?`;
            document.getElementById('paymentConfirmModal').style.display = 'block';
        }
        
        async function initiatePhonePePayment() {
            closePaymentModal();
            const amount = document.getElementById('amountPaid').value;
            
            try {
                const response = await fetch('/create_phonepe_order', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ amount: amount })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to create payment order');
                }
                
                // Redirect to PhonePe payment page
                window.location.href = data.payment_url;
                
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }

        async function deletePrintJob() {
            if (!deleteItemId) return;

            const status = document.getElementById('status');
            const batch = document.getElementById('batchSelect').value;

            try {
                const response = await fetch(`/delete_print_job/${deleteItemId}?batch=${batch}`, {
                    method: 'DELETE'
                });

                const data = await response.json();

                if (response.ok) {
                    status.textContent = data.message || 'Print job deleted successfully';
                    status.className = 'status success';
                    viewQueue();
                    updatePendingDues(); // Update pending dues after deleting a print job
                } else {
                    throw new Error(data.error || 'Delete request failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }

            closeModal();
        }

        async function updatePendingDues() {
            try {
                const response = await fetch('/get_pending_dues');
                const data = await response.json();
                
                if (response.ok) {
                    pendingDuesAmount = data.pending_dues;
                    document.querySelector('p:contains("Your Pending Dues:")').textContent = `Your Pending Dues: ₹${pendingDuesAmount}`;
                }
            } catch (error) {
                console.error('Error updating pending dues:', error);
            }
        }

        async function submitPrint() {
            const status = document.getElementById('status');
            const studentName = document.getElementById('studentName').value;
            const pdfFiles = document.getElementById('pdfFiles').files;
            const copies = document.getElementById('copies').value;
            const batch = document.getElementById('batchSelect').value;

            if (!studentName || pdfFiles.length === 0 || !copies || !batch) {
                status.textContent = 'Please fill in all fields';
                status.className = 'status error';
                return;
            }

            const formData = new FormData();
            formData.append('name', studentName);
            for (let i = 0; i < pdfFiles.length; i++) {
                formData.append('pdfs', pdfFiles[i]);
            }
            formData.append('copies', copies);
            formData.append('batch', batch);

            try {
                status.textContent = 'Validating and submitting print job...';
                status.className = 'status';

                const response = await fetch('/submit', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    status.innerHTML = `
                        <div>Print job submitted successfully!</div>
                        <div style="font-size: 0.9em; margin-top: 8px;">
                            Files: ${data.details.filenames.join(', ')}<br>
                            Pages: ${data.details.pages}<br>
                            Copies: ${data.details.copies}
                        </div>
                    `;
                    status.className = 'status success';
                    
                    // Clear form
                    document.getElementById('studentName').value = '';
                    document.getElementById('pdfFiles').value = '';
                    document.getElementById('copies').value = '1';
                    document.getElementById('fileInputButton').querySelector('p').textContent = 'Drop your PDF files here or click to browse';
                    
                    // Refresh queue
                    viewQueue();
                    
                    // Update pending dues
                    pendingDuesAmount = data.pending_dues;
                    
                    // Show payment confirmation if there are pending dues
                    if (data.pending_dues > 0) {
                        const paymentConfirmMessage = document.getElementById('paymentConfirmMessage');
                        paymentConfirmMessage.textContent = `Your total pending due is ₹${data.pending_dues}. Do you wish to pay now?`;
                        document.getElementById('paymentConfirmModal').style.display = 'block';
                    }
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
                            <h2><i class="fas fa-list"></i> Your Print Queue (Batch ${batch})</h2>
                            <p>Your queue is empty</p>
                        </div>`;
                    return;
                }

                let queueHTML = `
                    <div class="card">
                        <h2><i class="fas fa-list"></i> Your Print Queue (Batch ${batch})</h2>`;

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
                        <h2><i class="fas fa-list"></i> Your Print Queue (Batch ${batch})</h2>
                        <div class="status error">Error: ${error.message}</div>
                    </div>`;
            }
        }

        async function mergePrintQueue() {
            const status = document.getElementById('mergeStatus');
            const batchSelect = document.getElementById('adminBatchSelect');
            const password = prompt('Please enter admin password:');
            const batch = batchSelect.value;

            if (!password) {
                status.textContent = 'Password is required';
                status.className = 'status error';
                return;
            }

            try {
                status.textContent = 'Merging PDFs...';
                status.className = 'status';

                const response = await fetch(`/merge?batch=${batch}&password=${encodeURIComponent(password)}`, {
                    method: 'POST'
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Merge failed');
                }

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

                    status.textContent = 'PDFs merged and downloaded successfully';
                    status.className = 'status success';
                } else {
                    throw new Error('Invalid response format');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
                console.error('Merge error:', error);
            }
        }

        // User login
        async function login() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const status = document.getElementById('loginStatus');

            if (!email || !password) {
                status.textContent = 'Please fill in all fields';
                status.className = 'status error';
                return;
            }

            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (response.ok) {
                    status.textContent = 'Login successful';
                    status.className = 'status success';
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    throw new Error(data.error || 'Login failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
        }

        // Admin login
        async function adminLogin() {
            const email = document.getElementById('adminEmail').value;
            const password = document.getElementById('adminPassword').value;
            const status = document.getElementById('adminLoginStatus');

            if (!email || !password) {
                status.textContent = 'Please fill in all fields';
                status.className = 'status error';
                return;
            }

            try {
                const response = await fetch('/admin_login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (response.ok) {
                    status.textContent = 'Login successful';
                    status.className = 'status success';
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    throw new Error(data.error || 'Login failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
        }

        // User registration
        async function register() {
            const name = document.getElementById('registerName').value;
            const email = document.getElementById('registerEmail').value;
            const password = document.getElementById('registerPassword').value;
            const rollNo = document.getElementById('registerRollNo').value;
            const batch = document.getElementById('registerBatch').value;
            const status = document.getElementById('registerStatus');

            if (!name || !email || !password || !rollNo || !batch) {
                status.textContent = 'Please fill in all fields';
                status.className = 'status error';
                return;
            }

            status.textContent = 'Please wait, sending mail...';
            status.className = 'status';

            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ name, email, password, rollNo, batch })
                });

                const data = await response.json();

                if (response.ok) {
                    status.textContent = data.message || 'Registration successful. Please check your email for the OTP to confirm your address.';
                    status.className = 'status success';
                    setTimeout(() => {
                        showOtpCard();
                    }, 1000);
                } else {
                    throw new Error(data.error || 'Registration failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
        }

        // Show register card
        function showRegisterCard() {
            document.getElementById('loginCard').style.display = 'none';
            document.getElementById('registerCard').style.display = 'block';
        }

        // Show login card
        function showLoginCard() {
            document.getElementById('registerCard').style.display = 'none';
            document.getElementById('otpCard').style.display = 'none';
            document.getElementById('forgotPasswordCard').style.display = 'none';
            document.getElementById('adminLoginCard').style.display = 'none';
            document.getElementById('loginCard').style.display = 'block';
        }

        // Show admin login card
        function showAdminLoginCard() {
            document.getElementById('loginCard').style.display = 'none';
            document.getElementById('adminLoginCard').style.display = 'block';
        }

        // Show forgot password card
        function showForgotPasswordCard() {
            document.getElementById('loginCard').style.display = 'none';
            document.getElementById('forgotPasswordCard').style.display = 'block';
        }

        async function forgotPassword() {
            const email = document.getElementById('forgotPasswordEmail').value;
            const status = document.getElementById('forgotPasswordStatus');

            if (!email) {
                status.textContent = 'Email is required';
                status.className = 'status error';
                return;
            }

            try {
                const response = await fetch('/forgot_password', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email })
                });

                const data = await response.json();

                if (response.ok) {
                    status.textContent = data.message || 'Password reset email sent';
                    status.className = 'status success';
                } else {
                    throw new Error(data.error || 'Password reset request failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            if (document.getElementById('queueList')) {
                viewQueue();
            }
        });

        async function viewBilling() {
            const billingCard = document.getElementById('billingCard');
            const billingInfo = document.getElementById('billingInfo');

            try {
                const response = await fetch('/billing');
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to fetch billing information');
                }

                let billingHTML = `
                    <div class="bg-white p-8 rounded-lg shadow mb-8">
                        <h2 class="text-2xl font-bold text-indigo-600 mb-4"><i class="fas fa-money-bill-wave"></i> Batch 1 Billing</h2>
                        <table class="table-auto w-full">
                            <thead>
                                <tr>
                                    <th class="px-4 py-2">Name</th>
                                    <th class="px-4 py-2">Email</th>
                                    <th class="px-4 py-2">Pending Dues (₹)</th>
                                </tr>
                            </thead>
                            <tbody>`;

                data.batch1.users.forEach((user) => {
                    billingHTML += `
                                <tr class="bg-gray-100">
                                    <td class="border px-4 py-2">${user.name}</td>
                                    <td class="border px-4 py-2">${user.email}</td>
                                    <td class="border px-4 py-2">₹${user.pending_dues}</td>
                                </tr>`;
                });

                billingHTML += `
                            </tbody>
                            <tfoot>
                                <tr class="bg-gray-200">
                                    <td colspan="2" class="border px-4 py-2 font-bold">Total Batch 1 Dues</td>
                                    <td class="border px-4 py-2 font-bold">₹${data.batch1.total_dues}</td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                    
                    <div class="bg-white p-8 rounded-lg shadow mb-8">
                        <h2 class="text-2xl font-bold text-indigo-600 mb-4"><i class="fas fa-money-bill-wave"></i> Batch 2 Billing</h2>
                        <table class="table-auto w-full">
                            <thead>
                                <tr>
                                    <th class="px-4 py-2">Name</th>
                                    <th class="px-4 py-2">Email</th>
                                    <th class="px-4 py-2">Pending Dues (₹)</th>
                                </tr>
                            </thead>
                            <tbody>`;

                data.batch2.users.forEach((user) => {
                    billingHTML += `
                                <tr class="bg-gray-100">
                                    <td class="border px-4 py-2">${user.name}</td>
                                    <td class="border px-4 py-2">${user.email}</td>
                                    <td class="border px-4 py-2">₹${user.pending_dues}</td>
                                </tr>`;
                });

                billingHTML += `
                            </tbody>
                            <tfoot>
                                <tr class="bg-gray-200">
                                    <td colspan="2" class="border px-4 py-2 font-bold">Total Batch 2 Dues</td>
                                    <td class="border px-4 py-2 font-bold">₹${data.batch2.total_dues}</td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>`;

                billingInfo.innerHTML = billingHTML;
                billingCard.style.display = 'block';

            } catch (error) {
                billingInfo.innerHTML = `
                    <div class="bg-white p-8 rounded-lg shadow mb-8">
                        <h2 class="text-2xl font-bold text-indigo-600 mb-4"><i class="fas fa-money-bill-wave"></i> Billing Information</h2>
                        <div class="bg-red-100 text-red-600 p-4 rounded-lg">Error: ${error.message}</div>
                    </div>`;
                billingCard.style.display = 'block';
            }
        }

        async function submitPaymentRequest() {
            const amountPaid = document.getElementById('amountPaid').value;
            const status = document.getElementById('paymentRequestStatus');

            if (!amountPaid) {
                status.textContent = 'Please enter the amount you paid';
                status.className = 'status error';
                return;
            }

            try {
                const response = await fetch('/submit_payment_request', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ amount_paid: amountPaid })
                });

                const data = await response.json();

                if (response.ok) {
                    status.textContent = data.message || 'Payment request submitted successfully';
                    status.className = 'status success';
                } else {
                    throw new Error(data.error || 'Submission failed');
                }
            } catch (error) {
                status.textContent = `Error: ${error.message}`;
                status.className = 'status error';
            }
        }

        async function viewPaymentRequests() {
            const paymentRequestsCard = document.getElementById('paymentRequestsCard');
            const paymentRequestsDiv = document.getElementById('paymentRequests');

            try {
                const response = await fetch('/view_payment_requests');
                const requests = await response.json();

                if (!response.ok) {
                    throw new Error(requests.error || 'Failed to fetch payment requests');
                }

                let paymentRequestsHTML = '<h2>Payment Requests</h2><table><thead><tr><th>User</th><th>Amount Paid</th><th>Action</th></tr></thead><tbody>';

                requests.forEach(request => {
                    paymentRequestsHTML += `
                    <tr>
                        <td>${request.user_name} (${request.user_email})</td>
                        <td>${request.amount_paid}</td>
                        <td><button onclick="approvePaymentRequest('${request._id}')">Approve</button></td>
                    </tr>`;
                });

                paymentRequestsHTML += '</tbody></table>';
                paymentRequestsDiv.innerHTML = paymentRequestsHTML;
                paymentRequestsCard.style.display = 'block';

            } catch (error) {
                paymentRequestsDiv.innerHTML = `<div class="status error">Error: ${error.message}</div>`;
                paymentRequestsCard.style.display = 'block';
            }
        }

        async function approvePaymentRequest(requestId) {
            try {
                const response = await fetch(`/approve_payment_request/${requestId}`, {
                    method: 'POST'
                });

                const data = await response.json();

                if (response.ok) {
                    alert(data.message || 'Payment request approved successfully');
                    viewPaymentRequests();
                } else {
                    throw new Error(data.error || 'Approval failed');
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            if (document.getElementById('paymentRequests')) {
                viewPaymentRequests();
            }
        });

        // Logout function
        async function logout() {
            try {
                const response = await fetch('/logout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (response.ok) {
                    alert(data.message || 'Logout successful');
                    window.location.reload();
                } else {
                    throw new Error(data.error || 'Logout failed');
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }

        async function viewAllQueues() {
            const allQueuesCard = document.getElementById('allQueuesCard');
            const allQueuesContent = document.getElementById('allQueuesContent');

            try {
                const response = await fetch('/admin/all-queues');
                const queues = await response.json();

                if (!response.ok) {
                    throw new Error(queues.error || 'Failed to fetch queues');
                }

                let html = '';
                
                // Batch 1 Queue
                html += `<h3>Batch 1 Queue</h3>`;
                if (queues.batch1.length === 0) {
                    html += `<p>No print jobs in Batch 1</p>`;
                } else {
                    queues.batch1.forEach((item, index) => {
                        html += createQueueItemHTML(item, index, 1);
                    });
                }

                // Batch 2 Queue
                html += `<h3>Batch 2 Queue</h3>`;
                if (queues.batch2.length === 0) {
                    html += `<p>No print jobs in Batch 2</p>`;
                } else {
                    queues.batch2.forEach((item, index) => {
                        html += createQueueItemHTML(item, index, 2);
                    });
                }

                allQueuesContent.innerHTML = html;
                allQueuesCard.style.display = 'block';

            } catch (error) {
                allQueuesContent.innerHTML = `<div class="status error">Error: ${error.message}</div>`;
                allQueuesCard.style.display = 'block';
            }
        }

        function createQueueItemHTML(item, index, batch) {
            return `
                <div class="queue-item">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <strong>Batch ${batch} - #${index + 1}</strong>
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
        }
    </script>
</body>
</html>

<!-- Add OTP verification form in your HTML template -->
<div class="card" id="otpCard" style="display: none;">
    <h2><i class="fas fa-key"></i> Verify OTP</h2>
    <div class="form-group">
        <label for="otpEmail">Email</label>
        <input type="email" id="otpEmail" placeholder="Enter your email" required>
    </div>
    <div class="form-group">
        <label for="otp">OTP</label>
        <input type="text" id="otp" placeholder="Enter the OTP" required>
    </div>
    <button onclick="verifyOtp()">
        <i class="fas fa-check"></i> Verify OTP
    </button>
    <div id="otpStatus" class="status"></div>
</div>

<script>
    async function verifyOtp() {
        const email = document.getElementById('otpEmail').value;
        const otp = document.getElementById('otp').value;
        const status = document.getElementById('otpStatus');

        if (!email || !otp) {
            status.textContent = 'Please fill in all fields';
            status.className = 'status error';
            return;
        }

        try {
            const response = await fetch('/verify_otp', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, otp })
            });

            const data = await response.json();

            if (response.ok) {
                status.textContent = data.message || 'Email confirmed successfully!';
                status.className = 'status success';
                clearTimeout(otpTimer);
                setTimeout(() => {
                    showLoginCard();
                }, 1000);
            } else {
                throw new Error(data.error || 'OTP verification failed');
            }
        } catch (error) {
            status.textContent = `Error: ${error.message}`;
            status.className = 'status error';
        }
    }

    function startOtpTimer() {
        const status = document.getElementById('otpStatus');
        let timeLeft = 300; // 5 minutes in seconds

        otpTimer = setInterval(() => {
            if (timeLeft <= 0) {
                clearInterval(otpTimer);
                status.textContent = 'OTP expired. Please request a new OTP.';
                status.className = 'status error';
            } else {
                const minutes = Math.floor(timeLeft / 60);
                const seconds = timeLeft % 60;
                status.textContent = `Time left: ${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
                status.className = 'status';
                timeLeft--;
            }
        }, 1000);
    }

    // Show OTP card and start timer
    function showOtpCard() {
        document.getElementById('registerCard').style.display = 'none';
        document.getElementById('otpCard').style.display = 'block';
        startOtpTimer();
    }
</script>
"""

@app.route('/')
def index():
    if 'user' in session:
        user = session['user']
        user_data = users_collection.find_one({'email': user['email']})
        pending_dues = user_data.get('pending_dues', 0)
        return render_template_string(HTML_TEMPLATE, pending_dues=pending_dues, user=user)
    elif 'admin' in session:
        return render_template_string(HTML_TEMPLATE, admin=session['admin'])
    return render_template_string(HTML_TEMPLATE)

@app.route('/health', methods=['GET', 'POST'])  # Correct for multiple methods
def health_check():
    try:
        client.server_info()
        test_file = TEMP_DIR / 'health_check.txt'
        test_file.write_text('test')
        test_file.unlink()
        return "Server Working on port http://127.0.0.1:5000/", 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = users_collection.find_one({'email': email})

    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid credentials'}), 403

    if not user.get('email_confirmed'):
        return jsonify({'error': 'Email address not confirmed. Please check your email.'}), 403

    session['user'] = {
        'name': user['name'],
        'email': user['email'],
        'role': user['role'],
        'batch': user['batch']
    }
    return jsonify({'message': 'Login successful'}), 200



@app.route('/admin_login', methods=['POST'])
def admin_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if email != 'mishraaman2424@gmail.com' or hashlib.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD:
        return jsonify({'error': 'Invalid credentials'}), 403

    session['admin'] = {
        'name': 'admin',
        'email': email,
        'role': 'admin',
        'batch': 1
    }
    return jsonify({'message': 'Login successful'}), 200

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    rollNo = data.get('rollNo')
    batch = data.get('batch')

    if not name or not email or not password or not rollNo or not batch:
        return jsonify({'error': 'All fields are required'}), 400

    if users_collection.find_one({'email': email}):
        return jsonify({'error': 'Email already registered'}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    otp = generate_otp()
    user = {
        'name': name,
        'email': email,
        'password': hashed_password,
        'rollNo': rollNo,
        'batch': int(batch),
        'role': 'user',
        'pending_dues': 0,
        'email_confirmed': False,
        'otp': otp  # Store OTP
    }
    users_collection.insert_one(user)
    send_verification_email(name, email, otp)  # Pass the user's name, email, and OTP

    return jsonify({'message': 'Registration successful. Please check your email for the OTP to confirm your address.'}), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    session.pop('admin', None)
    return jsonify({'message': 'Logout successful'}), 200

@app.route('/get_pending_dues', methods=['GET'])
def get_pending_dues():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
        
    user = users_collection.find_one({'email': session['user']['email']})
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    return jsonify({'pending_dues': user.get('pending_dues', 0)}), 200

@app.route('/submit', methods=['POST'])
def submit_print():
    try:
        logger.info("Starting file upload process")
        if 'pdfs' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400

        if 'user' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

        files = request.files.getlist('pdfs')
        logger.info(f"Files received: {[file.filename for file in files]}")
        name = session['user']['name']
        copies = request.form.get('copies')
        batch = session['user']['batch']

        if not all([name, copies, batch, files]):
            return jsonify({'error': 'Missing required fields'}), 400

        try:
            copies = int(copies)
            batch = int(batch)
            if copies < 1 or batch not in [1, 2]:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid copies or batch value'}), 400

        filenames = []
        total_pages = 0

        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({'error': 'Only PDF files are allowed'}), 400

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f"{timestamp}_{Path(file.filename).stem}.pdf"
            temp_path = TEMP_DIR / safe_filename

            try:
                file.save(str(temp_path))
                logger.info(f"File saved to temp path: {temp_path}")

                # Validate PDF
                try:
                    with open(str(temp_path), 'rb') as pdf_file:
                        pdf_reader = PdfReader(pdf_file)

                        if len(pdf_reader.pages) == 0:
                            raise ValueError("The PDF file has no pages")

                        if pdf_reader.is_encrypted:
                            raise ValueError("Password protected PDFs are not allowed")

                        page_count = len(pdf_reader.pages)

                        try:
                            pdf_reader.pages[0].extract_text()
                        except Exception:
                            raise ValueError("The PDF file appears to be corrupted or invalid")

                except Exception as pdf_error:
                    return jsonify({'error': f'Invalid PDF file: {str(pdf_error)}'}), 400

                try:
                    logger.info("Uploading to GitHub...")
                    upload_result = upload_to_github(str(temp_path), safe_filename)
                    logger.info(f"Upload successful. URL: {upload_result['url']}")

                    document = {
                        'name': name,
                        'original_filename': file.filename,
                        'github_url': upload_result['url'],
                        'release_id': upload_result['id'],
                        'copies': copies,
                        'page_count': page_count,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'status': 'pending'
                    }

                except requests.exceptions.RequestException as e:
                    logger.error(f"GitHub API error: {str(e)}")
                    return jsonify({'error': 'Failed to upload file'}), 500

                collection = batch1_collection if batch == 1 else batch2_collection
                result = collection.insert_one(document)
                document['_id'] = str(result.inserted_id)

                filenames.append(file.filename)
                total_pages += page_count

            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                return jsonify({'error': f'Error processing file: {str(e)}'}), 500
            finally:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception as e:
                        logger.error(f"Error removing temporary file: {str(e)}")

        total_cost = total_pages * copies * 2
        users_collection.update_one(
            {'email': session['user']['email']},
            {'$inc': {'pending_dues': total_cost}}
        )

        user = users_collection.find_one({'email': session['user']['email']})
        pending_dues = user.get('pending_dues', 0)

        return jsonify({
            'message': 'Print request submitted successfully',
            'details': {
                'filenames': filenames,
                'pages': total_pages,
                'copies': copies
            },
            'pending_dues': pending_dues
        }), 200

    except Exception as e:
        logger.error(f"Submit print error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/queue', methods=['GET'])
def view_queue():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

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
        
        # Only fetch queue items for the current user
        queue = list(collection.find({'name': session['user']['name']}))

        # Convert ObjectId to string for JSON serialization
        for item in queue:
            item['_id'] = str(item['_id'])

        return jsonify(queue)

    except Exception as e:
        logger.error(f"View queue error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/delete_print_job/<item_id>', methods=['DELETE'])
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

        # Check if user is logged in
        if 'user' not in session and 'admin' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

        # Find the document first
        document = collection.find_one({'_id': ObjectId(item_id)})
        if not document:
            return jsonify({'error': 'Print job not found'}), 404

        # Check authorization
        if 'admin' not in session:  # If not admin, check if user owns the document
            if 'user' not in session or document['name'] != session['user']['name']:
                return jsonify({'error': 'Not authorized to delete this print job'}), 403

        # Delete from MongoDB
        result = collection.delete_one({'_id': ObjectId(item_id)})

        if result.deleted_count == 0:
            return jsonify({'error': 'Print job not found'}), 404

        # Adjust user's pending dues
        total_pages = document['page_count'] * document['copies']
        total_cost = total_pages * 2
        
        # If it's a user deleting their own job, update their dues
        if 'user' in session:
            users_collection.update_one(
                {'email': session['user']['email']},
                {'$inc': {'pending_dues': -total_cost}}
            )
        # If it's an admin deleting a job, update the job owner's dues
        elif 'admin' in session:
            user = users_collection.find_one({'name': document['name']})
            if user:
                users_collection.update_one(
                    {'_id': user['_id']},
                    {'$inc': {'pending_dues': -total_cost}}
                )

        # Delete from GitHub
        try:
            delete_from_github(document['release_id'])
        except Exception as e:
            logger.error(f"Error deleting from GitHub: {str(e)}")

        return jsonify({'message': 'Print job deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Delete print job error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

async def download_file(session, url, path):
    """Optimized file download with chunked transfer"""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context, limit=MAX_CONCURRENT_DOWNLOADS)
    timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(path, 'wb') as f:
                chunk_size = 64 * 1024  # 64KB chunks
                while True:
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break
                    await f.write(chunk)

@app.route('/merge', methods=['POST'])
def merge_queue():
    merge_dir = None
    
    try:
        batch = request.args.get('batch')
        password = request.args.get('password')
        
        if not batch:
            return jsonify({'error': 'Batch number is required'}), 400
            
        if not password or hashlib.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD:
            return jsonify({'error': 'Invalid admin password'}), 403

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
        merger = PdfMerger(strict=False)
        files_merged = False
        successful_merges = []
        errors = []

        # Process each file in the queue
        for item in queue:
            try:
                temp_path = merge_dir / f"temp_{item['original_filename']}"
                logger.info(f"Downloading {item['github_url']}")
                
                # Download file with authentication
                response = download_from_github(item['github_url'])
                
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # Validate and merge PDF
                with open(temp_path, 'rb') as pdf_file:
                    reader = PdfReader(pdf_file)
                    if len(reader.pages) > 0:
                        for _ in range(item['copies']):  # Append the file multiple times based on copies
                            merger.append(temp_path)
                        files_merged = True
                        successful_merges.append(item)
                        logger.info(f"Successfully processed {item['original_filename']}")
                    else:
                        errors.append(f"Empty PDF: {item['original_filename']}")

            except Exception as e:
                errors.append(f"Error processing {item['original_filename']}: {str(e)}")
                logger.error(f"Error processing file: {str(e)}")
            finally:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception as e:
                        logger.error(f"Error removing temporary file: {str(e)}")

        if not files_merged:
            error_msg = "No valid PDFs to merge. Errors: " + "; ".join(errors)
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 400

        # Create merged PDF
        output_path = merge_dir / f'merged_batch_{batch}.pdf'
        merger.write(str(output_path))
        merger.close()

        # Clean up successful merges
        for item in successful_merges:
            try:
                delete_url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO}/releases/{item['release_id']}"
                headers = {
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json"
                }
                requests.delete(delete_url, headers=headers)
                collection.delete_one({'_id': item['_id']})
            except Exception as e:
                logger.error(f"Cleanup error for {item['original_filename']}: {str(e)}")

        return send_file(
            str(output_path),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'print_queue_batch{batch}_{datetime.now().strftime("%Y%m%d")}.pdf'
        )

    except Exception as e:
        logger.error(f"Merge queue error: {str(e)}")
        return jsonify({'error': str(e)}), 500

    finally:
        if merge_dir and merge_dir.exists():
            try:
                shutil.rmtree(merge_dir)
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'error': 'Email and OTP are required'}), 400

    user = users_collection.find_one({'email': email})

    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user['otp'] == otp:
        users_collection.update_one({'email': email}, {'$set': {'email_confirmed': True}, '$unset': {'otp': ""}})
        return jsonify({'message': 'Email confirmed successfully!'}), 200
    else:
        return jsonify({'error': 'Invalid OTP'}), 400
        
@app.route('/pending_dues', methods=['GET'])
def pending_dues():
    try:
        if 'admin' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

        # Get all users
        users = list(users_collection.find({'role': 'user'}))
        
        # Separate users by batch
        batch1_users = []
        batch2_users = []
        
        for user in users:
            # Use the stored pending dues value
            user_dues = {
                'name': user['name'],
                'email': user['email'],
                'pending_dues': user['pending_dues']
            }
            
            if user.get('batch') == 1:
                batch1_users.append(user_dues)
            else:
                batch2_users.append(user_dues)

        # Calculate total dues for each batch
        total_batch1_dues = sum(user['pending_dues'] for user in batch1_users)
        total_batch2_dues = sum(user['pending_dues'] for user in batch2_users)

        return jsonify({
            'batch1': {
                'users': batch1_users,
                'total_dues': total_batch1_dues
            },
            'batch2': {
                'users': batch2_users,
                'total_dues': total_batch2_dues
            }
        })

    except Exception as e:
        logger.error(f"Pending dues error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/billing', methods=['GET'])
def billing():
    try:
        if 'admin' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

        # Get all users
        users = list(users_collection.find({'role': 'user'}))
        
        # Separate users by batch
        batch1_users = []
        batch2_users = []
        
        for user in users:
            # Use the stored pending dues value
            user_dues = {
                'name': user['name'],
                'email': user['email'],
                'pending_dues': user['pending_dues']
            }
            
            if user.get('batch') == 1:
                batch1_users.append(user_dues)
            else:
                batch2_users.append(user_dues)

        # Calculate total dues for each batch
        total_batch1_dues = sum(user['pending_dues'] for user in batch1_users)
        total_batch2_dues = sum(user['pending_dues'] for user in batch2_users)

        return jsonify({
            'batch1': {
                'users': batch1_users,
                'total_dues': total_batch1_dues
            },
            'batch2': {
                'users': batch2_users,
                'total_dues': total_batch2_dues
            }
        })

    except Exception as e:
        logger.error(f"Billing error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/submit_payment_request', methods=['POST'])
def submit_payment_request():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        amount_paid = data.get('amount_paid')

        if not amount_paid:
            return jsonify({'error': 'Amount paid is required'}), 400

        try:
            amount_paid = float(amount_paid)
            if amount_paid <= 0:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid amount'}), 400

        payment_request = {
            'user_email': session['user']['email'],
            'user_name': session['user']['name'],
            'amount_paid': amount_paid,
            'status': 'pending',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        payment_requests_collection.insert_one(payment_request)

        return jsonify({'message': 'Payment request submitted successfully'}), 200

    except Exception as e:
        logger.error(f"Submit payment request error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/view_payment_requests', methods=['GET'])
def view_payment_requests():
    try:
        if 'admin' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

        payment_requests = list(payment_requests_collection.find({'status': 'pending'}))

        # Convert ObjectId to string for JSON serialization
        for request in payment_requests:
            request['_id'] = str(request['_id'])

        return jsonify(payment_requests)

    except Exception as e:
        logger.error(f"View payment requests error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/approve_payment_request/<request_id>', methods=['POST'])
def approve_payment_request(request_id):
    try:
        if 'admin' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

        payment_request = payment_requests_collection.find_one({'_id': ObjectId(request_id)})

        if not payment_request:
            return jsonify({'error': 'Payment request not found'}), 404

        if payment_request['status'] != 'pending':
            return jsonify({'error': 'Payment request already processed'}), 400

        # Update user's pending dues
        users_collection.update_one(
            {'email': payment_request['user_email']},
            {'$inc': {'pending_dues': -payment_request['amount_paid']}}
        )

        # Update payment request status
        payment_requests_collection.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {'status': 'approved'}}
        )

        return jsonify({'message': 'Payment request approved successfully'}), 200

    except Exception as e:
        logger.error(f"Approve payment request error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Add GitHub upload function
def upload_to_github(file_path, filename):
    """Upload file to GitHub releases for public repository"""
    try:
        # Use token authentication for public repo
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",  # Note: using 'token' instead of 'Bearer'
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Generate unique tag name
        tag_name = f"pdf-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Create release data
        release_data = {
            "tag_name": tag_name,
            "name": filename,
            "body": "Print Queue PDF File",
            "draft": False,
            "prerelease": False
        }
        
        # Create a new release
        release_url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO}/releases"
        logger.info(f"Creating release at: {release_url}")
        release_response = requests.post(release_url, json=release_data, headers=headers)
        release_response.raise_for_status()
        release_data = release_response.json()
        
        # Upload the PDF file
        upload_url = release_data['upload_url'].split('{')[0]
        logger.info(f"Uploading file to: {upload_url}")
        
        with open(file_path, 'rb') as f:
            upload_headers = headers.copy()
            upload_headers["Content-Type"] = "application/pdf"
            upload_response = requests.post(
                upload_url,
                headers=upload_headers,
                params={'name': filename},
                data=f
            )
            upload_response.raise_for_status()
            
        return {
            'url': upload_response.json()['browser_download_url'],
            'id': release_data['id']
        }
        
    except Exception as e:
        logger.error(f"GitHub upload error: {str(e)}")
        raise

def download_from_github(url):
    """Download file from public GitHub repository"""
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/octet-stream"
        }
        
        response = requests.get(
            url,
            headers=headers,
            stream=True,
            verify=True,
            timeout=30
        )
        response.raise_for_status()
        return response
    except Exception as e:
        logger.error(f"GitHub download error: {str(e)}")
        raise

# Add to your delete_print_job function
def delete_from_github(release_id):
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        delete_url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO}/releases/{release_id}"
        response = requests.delete(delete_url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error deleting from GitHub: {str(e)}")
        raise

def generate_otp():
    return str(random.randint(1000, 9999))

def send_verification_email(user_name, user_email, otp):
    html = render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verify Your Email - Print For You</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f9fafb;
                color: #333;
                padding: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background-color: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            h2 {
                color: #4f46e5;
            }
            .otp {
                font-size: 24px;
                font-weight: bold;
                color: #4f46e5;
                margin: 20px 0;
            }
            .button {
                display: inline-block;
                padding: 10px 20px;
                background-color: #4f46e5;
                color: #fff;
                text-decoration: none;
                border-radius: 4px;
            }
            .footer {
                margin-top: 20px;
                text-align: center;
                font-size: 12px;
                color: #777;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Welcome, {{ user_name }} to <strong>Print For You</strong>!</h2>
            <p>We're excited to have you here! You're just one step away from accessing our services.</p>
            <p>To verify your email, please use the following OTP:</p>
            <div class="otp">{{ otp }}</div>
            <p>Alternatively, you can click the button below to verify your email:</p>
            <a href="https://flask-print-queue.onrender.com/verify?otp={{ otp }}" class="button">Verify Email</a>
            <p>If you did not request this, please ignore this email.</p>
            <div class="footer">
                <p>&copy; 2025 Print For You. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """, user_name=user_name , otp=otp)

    msg = Message(f"Verify Your Email - Print For You ({user_name})", recipients=[user_email])
    msg.html = html
    mail.send(msg)

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = serializer.loads(token, salt='email-confirmation-salt', max_age=3600)
    except Exception as e:
        return jsonify({'error': 'The confirmation link is invalid or has expired.'}), 400

    user = users_collection.find_one({'email': email})
    if user:
        users_collection.update_one({'email': email}, {'$set': {'email_confirmed': True}})
        return jsonify({'message': 'Email confirmed successfully!'}), 200
    return jsonify({'error': 'User not found.'}), 404

# Add this function to generate a password reset token
def generate_password_reset_token(email):
    return serializer.dumps(email, salt='password-reset-salt')

# Add this function to verify the password reset token
def verify_password_reset_token(token, expiration=3600):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None
    return email

# Add this function to send the password reset email
def send_password_reset_email(email, token):
    reset_url = url_for('reset_password', token=token, _external=True)
    html = render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Your Password - Print For You</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f9fafb;
                color: #333;
                padding: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background-color: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            h2 {
                color: #4f46e5;
            }
            .button {
                display: inline-block;
                padding: 10px 20px;
                background-color: #4f46e5;
                color: #fff;
                text-decoration: none;
                border-radius: 4px;
            }
            .footer {
                margin-top: 20px;
                text-align: center;
                font-size: 12px;
                color: #777;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Reset Your Password</h2>
            <p>To reset your password, click the button below:</p>
            <a href="{{ reset_url }}" class="button">Reset Password</a>
            <p>If you did not request this, please ignore this email.</p>
            <div class="footer">
                <p>&copy; 2025 Print For You. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """, reset_url=reset_url)

    msg = Message("Reset Your Password - Print For You", recipients=[email])
    msg.html = html
    mail.send(msg)

# Add this route to handle the forgot password request
@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = users_collection.find_one({'email': email})

    if not user:
        return jsonify({'error': 'User not found'}), 404

    token = generate_password_reset_token(email)
    send_password_reset_email(email, token)

    return jsonify({'message': 'Password reset email sent'}), 200

# Add this route to handle the password reset form
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = verify_password_reset_token(token)

    if not email:
        return jsonify({'error': 'Invalid or expired token'}), 400

    if request.method == 'POST':
        data = request.get_json()
        new_password = data.get('password')

        if not new_password:
            return jsonify({'error': 'Password is required'}), 400

        hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        users_collection.update_one({'email': email}, {'$set': {'password': hashed_password}})

        return jsonify({'message': 'Password reset successful'}), 200

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Your Password - Print For You</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f9fafb;
                color: #333;
                padding: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background-color: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            h2 {
                color: #4f46e5;
            }
            .form-group {
                margin-bottom: 1.5rem;
            }
            label {
                display: block;
                margin-bottom: 0.5rem;
                font-weight: 500;
                color: #333;
            }
            input {
                width: 100%;
                padding: 0.75rem;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                font-size: 1rem;
                transition: border-color 0.2s;
            }
            input:focus {
                outline: none;
                border-color: #4f46e5;
                box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
            }
            button {
                background-color: #4f46e5;
                color: white;
                border: none;
                padding: 0.75rem 1.5rem;
                border-radius: 8px;
                font-size: 1rem;
                cursor: pointer;
                transition: background-color 0.2s, filter 0.2s;
                display: flex;
                align-items: center;
                gap: 0.5rem;
                filter: brightness(1.1);
            }
            button:hover {
                background-color: #4338ca;
                filter: brightness(1.3);
            }
            .status {
                padding: 1rem;
                margin-top: 1rem;
                border-radius: 8px;
                font-weight: 500;
            }
            .success {
                background-color: #ecfdf5;
                color: #10b981;
                border: 1px solid #a7f3d0;
            }
            .error {
                background-color: #fef2f2;
                color: #ef4444;
                border: 1px solid #fecaca;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Reset Your Password</h2>
            <form id="resetPasswordForm">
                <div class="form-group">
                    <label for="password">New Password</label>
                    <input type="password" id="password" placeholder="Enter your new password" required>
                </div>
                <button type="submit">Reset Password</button>
                <div id="status" class="status"></div>
            </form>
        </div>
        <script>
            document.getElementById('resetPasswordForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const password = document.getElementById('password').value;
                const status = document.getElementById('status');

                if (!password) {
                    status.textContent = 'Password is required';
                    status.className = 'status error';
                    return;
                }

                try {
                    const response = await fetch(window.location.pathname, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ password })
                    });

                    const data = await response.json();

                    if (response.ok) {
                        status.textContent = data.message || 'Password reset successful';
                        status.className = 'status success';
                    } else {
                        throw new Error(data.error || 'Password reset failed');
                    }
                } catch (error) {
                    status.textContent = `Error: ${error.message}`;
                    status.className = 'status error';
                }
            });
        </script>
    </body>
    </html>
    """)

@app.route('/admin/all-queues')
def view_all_queues():
    try:
        if 'admin' not in session:
            return jsonify({'error': 'Unauthorized'}), 403

        batch1_queue = list(batch1_collection.find())
        batch2_queue = list(batch2_collection.find())

        # Convert ObjectId to string for JSON serialization
        for queue in [batch1_queue, batch2_queue]:
            for item in queue:
                item['_id'] = str(item['_id'])

        return jsonify({
            'batch1': batch1_queue,
            'batch2': batch2_queue
        })

    except Exception as e:
        logger.error(f"View all queues error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def generate_phonepe_payload(amount, user_email, transaction_id):
    payload = {
        "merchantId": PHONEPE_MERCHANT_ID,
        "merchantTransactionId": transaction_id,
        "merchantUserId": user_email,
        "amount": int(amount * 100),  # Convert to paise
        "redirectUrl": request.url_root + "payment/confirmation",  # Use dynamic URL based on host
        "redirectMode": "POST",
        "callbackUrl": request.url_root + "payment/callback",  # Use dynamic URL based on host
        "mobileNumber": "",
        "paymentInstrument": {
            "type": "PAY_PAGE"
        }
    }
    return payload

def generate_phonepe_checksum(payload):
    payload_str = json.dumps(payload, separators=(',', ':'))
    encoded_payload = base64.b64encode(payload_str.encode()).decode()
    
    message = f"{encoded_payload}/pg/v1/pay{PHONEPE_SALT_KEY}"
    sha256_hash = hashlib.sha256(message.encode()).hexdigest()
    checksum = f"{sha256_hash}###{PHONEPE_SALT_INDEX}"
    
    return encoded_payload, checksum

@app.route('/create_phonepe_order', methods=['POST'])
def create_phonepe_order():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Unauthorized'}), 403
            
        data = request.get_json()
        amount = data.get('amount')
        
        if not amount:
            return jsonify({'error': 'Amount is required'}), 400
            
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid amount'}), 400

        # Generate unique transaction ID
        transaction_id = str(uuid.uuid4())
        
        # Create payload
        payload = generate_phonepe_payload(
            amount, 
            session['user']['email'],
            transaction_id
        )
        
        # Generate checksum
        encoded_payload, checksum = generate_phonepe_checksum(payload)
        
        # Make request to PhonePe
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum
        }
        
        response = requests.post(
            f"{PHONEPE_API_URL}/pg/v1/pay",
            json={
                "request": encoded_payload
            },
            headers=headers
        )
        
        response_data = response.json()
        
        if response_data.get('success'):
            # Store transaction details
            phonepe_payments_collection.insert_one({
                'user_email': session['user']['email'],
                'user_name': session['user']['name'],
                'amount': amount,
                'transaction_id': transaction_id,
                'status': 'pending',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            return jsonify({
                'success': True,
                'payment_url': response_data['data']['instrumentResponse']['redirectInfo']['url']
            }), 200
        else:
            logger.error(f"PhonePe API error: {response_data}")
            return jsonify({
                'error': response_data.get('message', 'Payment initialization failed')
            }), 400
            
    except Exception as e:
        logger.error(f"Create PhonePe order error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/payment/confirmation', methods=['POST'])
def payment_confirmation():
    try:
        # Get the payment data from the request
        data = request.form
        
        # Log the payment data
        logger.info(f"Payment confirmation received: {data}")
        
        # Extract the transaction ID
        transaction_id = data.get('merchantTransactionId')
        
        if not transaction_id:
            logger.error("No transaction ID in payment confirmation")
            return redirect(url_for('index'))
        
        # Find the payment in the database
        payment = phonepe_payments_collection.find_one({'transaction_id': transaction_id})
        
        if not payment:
            logger.error(f"Payment not found for transaction ID: {transaction_id}")
            return redirect(url_for('index'))
        
        # Check if payment was successful
        payment_status = data.get('code')
        
        if payment_status == 'PAYMENT_SUCCESS':
            # Update payment status
            phonepe_payments_collection.update_one(
                {'transaction_id': transaction_id},
                {'$set': {'status': 'completed'}}
            )
            
            # Update user's pending dues
            users_collection.update_one(
                {'email': payment['user_email']},
                {'$inc': {'pending_dues': -payment['amount']}}
            )
            
            # Set a success message in the session
            session['payment_message'] = f"Payment of ₹{payment['amount']} successful!"
        else:
            # Update payment status
            phonepe_payments_collection.update_one(
                {'transaction_id': transaction_id},
                {'$set': {'status': 'failed'}}
            )
            
            # Set a failure message in the session
            session['payment_message'] = "Payment failed. Please try again."
        
        # Redirect to the home page
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Payment confirmation error: {str(e)}")
        return redirect(url_for('index'))

@app.route('/payment/callback', methods=['POST'])
def phonepe_callback():
    try:
        data = request.get_json()
        checksum = request.headers.get('X-VERIFY')

        calculated_checksum = hashlib.sha256(
            f"{json.dumps(data, separators=(',',':'))}{PHONEPE_SALT_KEY}".encode()
        ).hexdigest() + f"###{PHONEPE_SALT_INDEX}"

        if calculated_checksum != checksum:
            logger.error("Invalid checksum in payment callback")
            return jsonify({'error': 'Invalid checksum'}), 400

        transaction_id = data['data']['merchantTransactionId']
        payment = phonepe_payments_collection.find_one({'transaction_id': transaction_id})

        if not payment:
            logger.error(f"Payment not found for transaction ID: {transaction_id}")
            return jsonify({'error': 'Payment not found'}), 404

        if data['code'] == 'PAYMENT_SUCCESS':
            phonepe_payments_collection.update_one(
                {'transaction_id': transaction_id},
                {'$set': {'status': 'completed'}}
            )
            users_collection.update_one(
                {'email': payment['user_email']},
                {'$inc': {'pending_dues': -payment['amount']}}
            )
            return jsonify({'message': 'Payment successful'}), 200
        else:
            phonepe_payments_collection.update_one(
                {'transaction_id': transaction_id},
                {'$set': {'status': 'failed'}}
            )
            return jsonify({'error': 'Payment failed'}), 400

    except Exception as e:
        logger.error(f"PhonePe callback error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True)