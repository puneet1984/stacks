import os
import pymysql
from pymysql.cursors import DictCursor
import requests
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add separate loggers for success and failure
success_logger = logging.getLogger('success_reviews')
error_logger = logging.getLogger('failed_reviews')

# Configure success logger
success_handler = logging.FileHandler('/var/log/app/successful_reviews.log')
success_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
success_logger.addHandler(success_handler)
success_logger.setLevel(logging.INFO)

# Configure error logger
error_handler = logging.FileHandler('/var/log/app/failed_reviews.log')
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
error_logger.addHandler(error_handler)
error_logger.setLevel(logging.ERROR)

class GoogleReviewService:
    def __init__(self):
        self.google_review_link = os.getenv('GOOGLE_REVIEW_LINK', 'https://g.page/r/default-review-link')
        self.waha_url = os.getenv('WAHA_API_URL', 'http://localhost:5002')
        self.db_config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USERNAME'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME'),
            'port': int(os.getenv('DB_PORT')),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'autocommit': False
        }
        self._connection = None

    @property
    def connection(self):
        if self._connection is None:
            self._connection = pymysql.connect(**self.db_config)
        return self._connection

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

    def get_yesterday_patients(self):
        """Fetch patients registered yesterday who haven't received review request"""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.id as patient_id, p.mobile_number, p.name
                FROM patients p
                LEFT JOIN sms_logs s ON p.id = s.patient_id AND s.sms_type = 'REVIEW_REQUEST'
                WHERE DATE(p.created_at) = DATE(NOW() - INTERVAL 1 DAY)
                AND p.mobile_number IS NOT NULL
                AND (s.status IS NULL OR s.status != 'SUCCESS')
            """)
            return cursor.fetchall()

    def get_pending_review_requests(self):
        """Fetch pending or failed review requests"""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.id as patient_id, p.mobile_number, p.name, s.id as sms_id
                FROM patients p
                JOIN sms_logs s ON p.id = s.patient_id 
                WHERE s.sms_type = 'REVIEW_REQUEST'
                AND s.status IN ('PENDING', 'PENDING-ERROR', 'FAILED')
                AND p.mobile_number IS NOT NULL
                AND DATE(s.created_at) >= DATE(NOW() - INTERVAL 1 DAY)
            """)
            return cursor.fetchall()

    def retry_pending_requests(self):
        """Retry sending pending review requests"""
        try:
            pending = self.get_pending_review_requests()
            results = {'processed': 0, 'success': 0, 'failed': 0}

            if not pending:
                logging.info("No pending review requests found")
                return results

            for patient in pending:
                message = (f"प्रिय {patient['name']},\n\n"
                          f"हमारी सेवाओं को चुनने के लिए धन्यवाद! आपकी राय हमारे लिए महत्वपूर्ण है।\n"
                          f"कृपया अपना अनुभव साझा करने के लिए एक क्षण निकालें: {self.google_review_link}\n\n"
                          f"आपकी समीक्षा हमें बेहतर सेवा प्रदान करने में मदद करती है।")

                status, error = self._send_whatsapp_message(patient['mobile_number'], message)
                review_status = 'SUCCESS' if status == 'SUCCESS' else 'PENDING-ERROR'
                
                # Log success or failure
                if status == 'SUCCESS':
                    success_logger.info(f"Review retry successful - Patient: {patient['name']} (ID: {patient['patient_id']}) Mobile: {patient['mobile_number']}")
                else:
                    error_logger.error(f"Review retry failed - Patient: {patient['name']} (ID: {patient['patient_id']}) Mobile: {patient['mobile_number']} Error: {error}")

                with self.connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE sms_logs 
                        SET status = %s,
                            error_message = %s,
                            sent_at = NOW()
                        WHERE id = %s
                    """, (review_status, error, patient['sms_id']))

                results['processed'] += 1
                if status == 'SUCCESS':
                    results['success'] += 1
                else:
                    results['failed'] += 1

            self.connection.commit()
            return results

        except Exception as e:
            if self._connection:
                self._connection.rollback()
            logging.error(f"Error retrying review requests: {str(e)}")
            raise

    def send_review_requests(self):
        """Send Google review requests in Hindi to yesterday's patients"""
        try:
            patients = self.get_yesterday_patients()
            results = {'processed': 0, 'success': 0, 'failed': 0}

            if not patients:
                logging.info("No patients found from yesterday")
                return results

            for patient in patients:
                message = (f"प्रिय {patient['name']},\n\n"
                          f"हमारी सेवाओं को चुनने के लिए धन्यवाद! आपकी राय हमारे लिए महत्वपूर्ण है।\n"
                          f"कृपया अपना अनुभव साझा करने के लिए एक क्षण निकालें: {self.google_review_link}\n\n"
                          f"आपकी समीक्षा हमें बेहतर सेवा प्रदान करने में मदद करती है।")

                with self.connection.cursor() as cursor:
                    # First insert into sms_logs
                    cursor.execute("""
                        INSERT INTO sms_logs (patient_id, mobile_number, message, 
                                           message_type, sms_type, status)
                        VALUES (%s, %s, %s, 'whatsapp', 'REVIEW_REQUEST', 'PENDING')
                    """, (patient['patient_id'], patient['mobile_number'], message))
                    
                    status, error = self._send_whatsapp_message(patient['mobile_number'], message)
                    review_status = 'SUCCESS' if status == 'SUCCESS' else 'PENDING-ERROR'
                    
                    # Log success or failure
                    if status == 'SUCCESS':
                        success_logger.info(f"Review request successful - Patient: {patient['name']} (ID: {patient['patient_id']}) Mobile: {patient['mobile_number']}")
                    else:
                        error_logger.error(f"Review request failed - Patient: {patient['name']} (ID: {patient['patient_id']}) Mobile: {patient['mobile_number']} Error: {error}")

                    # Update the status in sms_logs
                    cursor.execute("""
                        UPDATE sms_logs 
                        SET status = %s,
                            error_message = %s,
                            sent_at = NOW()
                        WHERE patient_id = %s
                        AND sms_type = 'REVIEW_REQUEST'
                        ORDER BY id DESC LIMIT 1
                    """, (review_status, error, patient['patient_id']))

                    results['processed'] += 1
                    if status == 'SUCCESS':
                        results['success'] += 1
                    else:
                        results['failed'] += 1

            self.connection.commit()
            return results

        except Exception as e:
            if self._connection:
                self._connection.rollback()
            logging.error(f"Error sending review requests: {str(e)}")
            raise
        finally:
            if self._connection:
                self._connection.close()
                self._connection = None

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='/var/log/app/google_reviews.log'
    )
    
    service = GoogleReviewService()
    
    # First retry pending messages
    retry_results = service.retry_pending_requests()
    logging.info(f"Retried {retry_results['processed']} pending review requests: "
                f"{retry_results['success']} successful, {retry_results['failed']} failed")
    
    # Then process new messages
    new_results = service.send_review_requests()
    logging.info(f"Processed {new_results['processed']} new review requests: "
                f"{new_results['success']} successful, {new_results['failed']} failed")
