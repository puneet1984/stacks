import os
import logging
from flask import Flask, request, jsonify
from ftplib import FTP
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# FTP Configuration
FTP_HOST = os.getenv('FTP_HOST')
FTP_USER = os.getenv('FTP_USER')
FTP_PASS = os.getenv('FTP_PASS')
FTP_PATH = os.getenv('FTP_PATH')
BASE_URL = os.getenv('FTP_BASE_URL')

# Validate required environment variables
required_vars = ['FTP_HOST', 'FTP_USER', 'FTP_PASS', 'FTP_PATH', 'FTP_BASE_URL']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='~/logs/ftp_upload.log'
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'htdocs/'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def ftp_upload(local_file, remote_filename):
    """Upload file to FTP server"""
    try:
        with FTP(FTP_HOST) as ftp:
            ftp.login(user=FTP_USER, passwd=FTP_PASS)
            ftp.cwd(FTP_PATH)
            
            with open(local_file, 'rb') as file:
                ftp.storbinary(f'STOR {remote_filename}', file)
            
            logging.info(f"Successfully uploaded {remote_filename}")
            return True
    except Exception as e:
        logging.error(f"FTP upload failed: {str(e)}")
        return False

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = secure_filename(file.filename)
        local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save file temporarily
        file.save(local_path)
        
        # Upload to FTP
        if ftp_upload(local_path, filename):
            # Clean up temporary file
            os.remove(local_path)
            file_url = f"{BASE_URL.rstrip('/')}/{filename}"
            return jsonify({
                'message': 'File uploaded successfully',
                'filename': filename,
                'url': file_url
            }), 200
        else:
            os.remove(local_path)
            return jsonify({'error': 'FTP upload failed'}), 500
            
    except Exception as e:
        logging.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)


# curl -X POST -F "file=@/path/to/local/file.txt" http://localhost:5001/upload

