import logging
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import base64
from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
SENDER_EMAIL = os.getenv('SMTP_EMAIL')
SENDER_PASSWORD = os.getenv('SMTP_PASSWORD')

# Validate required environment variables
if not all([SENDER_EMAIL, SENDER_PASSWORD]):
    raise ValueError("Missing required environment variables: SMTP_EMAIL, SMTP_PASSWORD")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='~/logs/sendemail.log'
)

app = Flask(__name__)

def send_email(to_email, subject, body, image_data=None):
    """
    Send email with provided parameters and optional image attachment
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Handle image attachment if provided
        if image_data:
            image_binary = base64.b64decode(image_data) if isinstance(image_data, str) else image_data
            img = MIMEImage(image_binary)
            img.add_header('Content-ID', '<qr_code>')
            img.add_header('Content-Disposition', 'inline')
            msg.attach(img)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        logging.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logging.error(f"Email sending failed: {e}")
        return False

@app.route('/send-email', methods=['POST'])
def send_email_endpoint():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['to_email', 'subject', 'body']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Send email with optional image
        success = send_email(
            data['to_email'],
            data['subject'],
            data['body'],
            data.get('image')  # Optional image data
        )

        if success:
            return jsonify({'message': 'Email sent successfully'}), 200
        else:
            return jsonify({'error': 'Failed to send email'}), 500

    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)



# curl -X POST http://localhost:5000/send-email \
# -H "Content-Type: application/json" \
# -d '{
#     "to_email": "recipient@example.com",
#     "subject": "Test Email",
#     "body": "This is a test email body",
#     "image": "base64_encoded_image_data"
# }'