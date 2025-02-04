from flask import Flask, request, render_template, send_file
import os
import json
from PyPDF2 import PdfMerger, PdfReader

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
MERGED_FOLDER = "merged"
HISTORY_FILE = "history.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MERGED_FOLDER, exist_ok=True)

# Define folder structure
sections = {"1copy": 1, "2copy": 2, "3copy": 3, "4copy": 4}
for section in sections:
    os.makedirs(os.path.join(UPLOAD_FOLDER, section), exist_ok=True)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def is_valid_pdf(file_path):
    """Check if a file is a valid PDF"""
    try:
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            return len(reader.pages) > 0
    except Exception:
        return False

def merge_pdfs():
    merger = PdfMerger()
    for section, copies in sections.items():
        folder_path = os.path.join(UPLOAD_FOLDER, section)
        for filename in sorted(os.listdir(folder_path)):
            file_path = os.path.join(folder_path, filename)
            if is_valid_pdf(file_path):
                for _ in range(copies):  # Duplicate the file based on copy count
                    merger.append(file_path)
            else:
                print(f"Skipping invalid PDF: {filename}")
    merged_pdf_path = os.path.join(MERGED_FOLDER, "final_merged.pdf")
    merger.write(merged_pdf_path)
    merger.close()
    return merged_pdf_path

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    history = load_history()
    if request.method == 'POST':
        copy_type = request.form['copy_type']
        if 'file' not in request.files:
            return render_template('upload.html', sections=sections.keys(), message="No file part", history=history)
        file = request.files['file']
        if file.filename == '':
            return render_template('upload.html', sections=sections.keys(), message="No selected file", history=history)
        save_path = os.path.join(UPLOAD_FOLDER, copy_type, file.filename)
        file.save(save_path)
        
        # Save to history
        history.append({"copy_type": copy_type, "filename": file.filename})
        save_history(history)
        
        return render_template('upload.html', sections=sections.keys(), message=f"File '{file.filename}' uploaded successfully to {copy_type}", history=history)
    return render_template('upload.html', sections=sections.keys(), history=history)

@app.route('/delete', methods=['POST'])
def delete_file():
    copy_type = request.form['copy_type']
    filename = request.form['filename']
    file_path = os.path.join(UPLOAD_FOLDER, copy_type, filename)
    
    history = load_history()
    history = [entry for entry in history if not (entry["copy_type"] == copy_type and entry["filename"] == filename)]
    save_history(history)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        return "File deleted successfully"
    return "File not found"

@app.route('/merge', methods=['GET'])
def merge_and_download():
    merged_pdf = merge_pdfs()
    return send_file(merged_pdf, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)