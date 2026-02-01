import os
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor
import requests
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='/var/log/app/stock_alerts.log'
)

class StockAlertService:
    def __init__(self):
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
        """Get database connection with lazy loading"""
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
            return 'FAILED', error

    def process_stock_alerts(self):
        """Process all pending stock alerts"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, item_id, message, mobile_number, alert_type 
                    FROM stock_alert_logs 
                    WHERE status = 'PENDING'
                    AND (sent_at IS NULL OR next_alert_after <= NOW())
                    FOR UPDATE
                """)
                pending_alerts = cursor.fetchall()

                results = {'processed': 0, 'success': 0, 'failed': 0}
                
                if not pending_alerts:
                    return results

                for alert in pending_alerts:
                    status, error = self._send_whatsapp_message(alert['mobile_number'], alert['message'])
                    
                    if error:
                        logging.error(f"Stock Alert ID {alert['id']}: {error}")

                    cursor.execute("""
                        UPDATE stock_alert_logs 
                        SET status = %s,
                            error_message = %s,
                            sent_at = NOW()
                        WHERE id = %s
                    """, (status, error, alert['id']))
                    
                    results['processed'] += 1
                    if status == 'SUCCESS':
                        results['success'] += 1
                    else:
                        results['failed'] += 1

                self.connection.commit()
                return results

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Error processing stock alerts: {str(e)}")
            raise
        finally:
            if self._connection:
                self._connection.close()
                self._connection = None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = StockAlertService()
    results = service.process_stock_alerts()
    logging.info(f"Processed {results['processed']} stock alerts: "
                f"{results['success']} successful, {results['failed']} failed")
