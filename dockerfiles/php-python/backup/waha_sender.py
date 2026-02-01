import logging
import requests
import re
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify

# Load environment variables
load_dotenv()

# WAHA Configuration
WAHA_HOST = os.getenv('WAHA_HOST')
WAHA_SESSION = os.getenv('WAHA_SESSION')

# Validate required environment variables
required_vars = ['WAHA_HOST', 'WAHA_SESSION']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='/var/log/app/waha_sender.log'
)

class WAHAClient:
    def __init__(self, base_url=WAHA_HOST, session=WAHA_SESSION):
        self.base_url = base_url.rstrip('/')
        self.session = session

    def check_session(self):
        """Check if WhatsApp session is active and working"""
        try:
            response = requests.get(
                f"{self.base_url}/api/sessions/{self.session}",
                headers={'Accept': 'application/json'}
            )
            response.raise_for_status()
            result = response.json()
            
            return {
                'status': result.get('status'),
                'is_working': result.get('status') == 'WORKING',
                'engine_state': result.get('engine', {}).get('state'),
                'is_connected': result.get('engine', {}).get('state') == 'CONNECTED'
            }
        except requests.RequestException as e:
            logging.error(f"Session check failed: {e}")
            return None

    def validate_number(self, phone_number: str) -> str:
        """Validate and format phone number"""
        number = re.sub(r'\D', '', phone_number)
        if len(number) == 10:
            number = '91' + number
        if not re.match(r'^\d{2,4}\d{10}$', number):
            raise ValueError('Invalid phone number format. Must be country code + 10 digits')
        return f"{number}@c.us"

    def check_number(self, phone):
        """Check if phone number exists on WhatsApp"""
        try:
            # Remove chat_id validation since API expects raw number
            response = requests.post(
                f"{self.base_url}/api/contacts/check-exists",
                json={
                    "phone": phone,  # Send raw phone number
                    "session": self.session
                },
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            result = response.json()
            logging.info(f"Check number response: {result}")
            return {
                'numberExists': result.get('status', '').lower() == 'valid',
                'chatId': result.get('id')
            }
        except Exception as e:
            logging.error(f"Check number failed: {e}")
            return None

    def send_message(self, phone, message):
        """Send WhatsApp message"""
        try:
            # Check session status first
            status = self.check_session()
            if not status or not status['is_working'] or not status['is_connected']:
                raise Exception(f"WhatsApp session is not active. Status: {status}")

            chat_id = self.validate_number(phone)
            payload = {
                "chatId": chat_id,
                "text": message,
                "session": self.session,
                "linkPreview": True
            }

            response = requests.post(
                f"{self.base_url}/api/sendText",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Send message failed: {e}")
            return None

app = Flask(__name__)
waha_client = WAHAClient()

@app.route('/health', methods=['GET'])
def health_check():
    status = waha_client.check_session()
    if status:
        return jsonify({'status': 'healthy', 'whatsapp_status': status})
    return jsonify({'status': 'error', 'message': 'WhatsApp session check failed'}), 500

@app.route('/send-message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        if not data or 'phone' not in data or 'message' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields: phone and message'
            }), 400

        result = waha_client.send_message(data['phone'], data['message'])
        if result:
            return jsonify({'status': 'success', 'data': result})
        return jsonify({'status': 'error', 'message': 'Failed to send message'}), 500

    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/contacts/check-exists', methods=['GET'])
def check_contact():
    try:
        phone = request.args.get('phone')
        if not phone:
            return jsonify({
                'status': 'error',
                'message': 'Missing phone number parameter'
            }), 400

        result = waha_client.check_number(phone)
        if result:
            return jsonify({'status': 'success', 'data': result})
        return jsonify({
            'status': 'error', 
            'message': 'Failed to check number'
        }), 500

    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002)