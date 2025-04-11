import logging
import time
from datetime import datetime, timedelta
import pytz
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# WAHA Configuration
WAHA_HOST = os.getenv('WAHA_HOST')
WAHA_SESSION = os.getenv('WAHA_SESSION')

# Email Configuration
EMAIL_SERVICE = os.getenv('EMAIL_SERVICE')
ALERT_EMAIL = os.getenv('WAHA_ALERT_EMAIL')

# Business Hours Configuration
BUSINESS_START = int(os.getenv('BUSINESS_START'))
BUSINESS_END = int(os.getenv('BUSINESS_END'))

# Validate required environment variables
required_vars = [
    'WAHA_HOST', 'WAHA_SESSION', 
    'EMAIL_SERVICE', 'WAHA_ALERT_EMAIL',
    'BUSINESS_START', 'BUSINESS_END'
]
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='~/logs/waha_monitor.log'
)

# Add timezone configuration
IST = pytz.timezone('Asia/Kolkata')

def send_qr_code_alert():
    """Send QR code email"""
    try:
        # Get QR code image
        qr_response = requests.get(f"{WAHA_HOST}/api/default/auth/qr?format=image", stream=True)
        if qr_response.status_code != 200:
            logging.error("Failed to get QR code image")
            return False

        # Prepare email payload
        payload = {
            "to_email": ALERT_EMAIL,
            "subject": "WAHA QR Code Required",
            "body": (
                "WAHA session requires QR code scan.\n"
                "Please scan the attached QR code using WhatsApp mobile app.\n"
                f"Check time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')}"
            ),
            "image": qr_response.content  # Send raw image data
        }

        # Send via email service
        response = requests.post(
            EMAIL_SERVICE,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        success = response.status_code == 200
        if success:
            logging.info("QR code email sent successfully")
        return success

    except Exception as e:
        logging.error(f"QR code email sending failed: {e}")
        return False

def check_waha_session():
    """Check if WAHA session is connected"""
    try:
        response = requests.get(f"{WAHA_HOST}/api/sessions/{WAHA_SESSION}")
        if response.status_code == 200:
            data = response.json()
            status = data.get('status')
            
            if status == 'SCAN_QR_CODE':
                logging.info("WAHA status: SCAN_QR_CODE - Sending QR code email")
                send_qr_code_alert()
                return False
                
            is_connected = (
                status == 'WORKING' and 
                data.get('engine', {}).get('state') == 'CONNECTED'
            )
            status_text = "CONNECTED" if is_connected else "DISCONNECTED"
            logging.info(
                f"WAHA session status: {status_text} "
                f"(Status: {status}, "
                f"Engine: {data.get('engine', {}).get('state')})"
            )
            return is_connected
        logging.warning(f"Failed to get WAHA session status, HTTP status: {response.status_code}")
        return False
    except Exception as e:
        logging.error(f"WAHA status check failed: {e}")
        return False

def send_alert():
    """Send alert email using email service"""
    try:
        payload = {
            "to_email": ALERT_EMAIL,
            "subject": "WAHA Session Alert",
            "body": (
                f"WAHA session '{WAHA_SESSION}' is DISCONNECTED.\n"
                f"Last check time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                f"Host: {WAHA_HOST}\n"
                "Please check the WAHA service."
            )
        }
        
        response = requests.post(
            EMAIL_SERVICE,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Alert sending failed: {e}")
        return False

def get_next_run_time():
    """Calculate next run time based on current IST time"""
    now = datetime.now(IST)
    current_hour = now.hour

    if current_hour < BUSINESS_START:
        # Before business hours, wait until today's start time
        next_run = now.replace(hour=BUSINESS_START, minute=0, second=0, microsecond=0)
    elif current_hour >= BUSINESS_END:
        # After business hours, wait until tomorrow's start time
        next_run = now.replace(hour=BUSINESS_START, minute=0, second=0, microsecond=0) + timedelta(days=1)
    else:
        # During business hours, wait until next hour
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    return next_run

def main():
    """Main monitoring loop"""
    logging.info("WAHA session monitoring started...")
    last_alert_time = 0
    alert_interval = 3600  # Send alert maximum once per hour

    while True:
        try:
            now = datetime.now(IST)
            
            # Check if within business hours
            if BUSINESS_START <= now.hour < BUSINESS_END:
                is_connected = check_waha_session()
                current_time = time.time()

                if not is_connected and (current_time - last_alert_time) >= alert_interval:
                    if send_alert():
                        last_alert_time = current_time
                        logging.info("Alert sent successfully")

            # Calculate sleep time until next run
            next_run = get_next_run_time()
            sleep_seconds = (next_run - now).total_seconds()
            
            logging.info(f"Sleeping until {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            time.sleep(sleep_seconds)

        except Exception as e:
            logging.error(f"Monitoring cycle error: {e}")
            time.sleep(300)  # On error, retry after 5 minutes

if __name__ == "__main__":
    main()
