import os
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor  # More explicit import
import requests
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='/var/log/app/patient_alerts.log'
)

class PatientMessageService:
    def __init__(self):
        self.waha_url = os.getenv('WAHA_API_URL', 'http://localhost:5002')
        self.db_config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USERNAME'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME'),
            'port': int(os.getenv('DB_PORT')),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,  # Direct reference to cursor class
            'autocommit': False
        }
        self._connection = None

    @property
    def connection(self):
        """Get database connection with specific cursor class"""
        if self._connection is None:
            self._connection = pymysql.connect(**self.db_config)
        return self._connection

    def get_cursor(self, cursor_class=None):
        """Get cursor with optional different cursor type"""
        return self.connection.cursor(cursor_class or DictCursor)

    def _send_whatsapp_message(self, phone, message):
        try:
            response = requests.post(
                f"{self.waha_url}/send-message",
                json={"phone": phone, "message": message}
            )
            response.raise_for_status()
            return 'SUCCESS', None
        except requests.RequestException as e:
            error = f"WhatsApp API Error: {str(e)}"
            return 'PENDING', error

    def process_pending_messages(self):
        """Process all pending patient-related messages from sms_logs table"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT patient_id, mobile_number, message, template_id, 
                           message_type, sms_type 
                    FROM sms_logs 
                    WHERE status = 'PENDING'
                    AND sms_type IN ('REGISTRATION', 'APPOINTMENT')
                """)
                pending_msgs = cursor.fetchall()
                results = {'processed': 0, 'success': 0, 'failed': 0}
                
                if not pending_msgs:
                    return results

                for msg in pending_msgs:
                    status, error = self._send_whatsapp_message(msg['mobile_number'], msg['message'])
                    
                    if error:
                        logging.error(f"Message ID {msg['patient_id']}: {error}")

                    cursor.execute("""
                        UPDATE sms_logs 
                        SET status = %s,
                            message_type = 'whatsapp',
                            error_message = %s,
                            sent_at = NOW()
                        WHERE patient_id = %s
                    """, (status, error, msg['patient_id']))
                    
                    results['processed'] += 1
                    if status == 'SUCCESS':
                        results['success'] += 1
                    else:
                        results['failed'] += 1

                self.connection.commit()
                return results

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Error processing messages: {str(e)}")
            raise
        finally:
            if self._connection:
                self._connection.close()
                self._connection = None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = PatientMessageService()
    
    # Process patient messages
    patient_results = service.process_pending_messages()
    logging.info(f"Processed {patient_results['processed']} patient messages: "
                f"{patient_results['success']} successful, {patient_results['failed']} failed")
