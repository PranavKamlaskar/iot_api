#!/usr/bin/env python3

import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import SensorReading, Base
import requests
import smtplib
from email.mime.text import MIMEText
import logging
import time



#How it Fits In Your Docker Setup
#Component   Role
#web service (Flask) Stores sensor data
#db service (Postgres)   Stores persistent readings
#alerts service (this script)    Periodically checks latest data, triggers alerts
#.env    Provides configuration across all services




# Load .env variables
load_dotenv()
DB_URL = os.getenv("DB_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

# Thresholds .last_alert prevents sending duplicate alerts for the same data.
TEMP_THRESHOLD = 30.0
HUM_THRESHOLD = 25.0

# Alert state file
ALERT_STATE_FILE = ".last_alert"

# DB setup . Connects to the same PostgreSQL database used by the Flask app .Queries the latest reading.
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

logging.basicConfig(
    filename="alert.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

#session = Session()
#reading = SensorReading(temperature=45.0, humidity=15.0)  # High temp, low humidity
#session.add(reading)
#session.commit()
#session.close()

print("🔧 Inserted test reading.")

# --- Alert helpers ---

def get_last_alert_time():
    if not Path(ALERT_STATE_FILE).exists():
        return None
    with open(ALERT_STATE_FILE, "r") as f:
        data = json.load(f)
        return datetime.fromisoformat(data.get("timestamp"))

def set_last_alert_time(timestamp):
    with open(ALERT_STATE_FILE, "w") as f:
        json.dump({"timestamp": timestamp.isoformat()}, f)

def send_telegram_alert(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Telegram alert sent.")
        else:
            print(f"❌ Telegram error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

def send_email_alert(subject, body):
    if not all([EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_TO]):
        print("⚠️ Email credentials missing.")
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("✅ Email alert sent.")
    except Exception as e:
        print(f"❌ Email send failed: {e}")

# --- Main logic ---

def check_alert_conditions():                           #etches the most recent reading.Compares it with the last alert time to avoid redundancy. Sends alert if:Temp > 30°C and Humidity < 25%

    session = Session()
    reading = session.query(SensorReading).order_by(SensorReading.timestamp.desc()).first()
    session.close()

    if not reading:
        print("⚠️ No sensor data available.")
        logging.error("No sensor data available.")
        return

    print(f"Latest Reading: Temp={reading.temperature}°C, Humidity={reading.humidity}%, Time={reading.timestamp}")
    logging.info("Latest Reading: Temp=%.1f°C, Humidity=%.1f%%, Time=%s", reading.temperature, reading.humidity, str(reading.timestamp))

    last_alert_time = get_last_alert_time()
    if last_alert_time and reading.timestamp <= last_alert_time:
        print("🔁 Skipping: No new data since last alert.")
        logging.warning("Skipping: No new data since last alert.")

        return

    if reading.temperature > TEMP_THRESHOLD or reading.humidity < HUM_THRESHOLD:
        print("🚨 ALERT: Threshold breached!")
        logging.warning("ALERT: Threshold breached! Temp=%.1f, Humidity=%.1f", reading.temperature, reading.humidity)

        alert_msg = (
            f"🚨 Alert!\n"
            f"Temp: {reading.temperature}°C\n"
            f"Humidity: {reading.humidity}%\n"
            f"Time: {reading.timestamp}"
        )
        send_telegram_alert(alert_msg)
        send_email_alert("🚨 IoT Alert Triggered", alert_msg)
        set_last_alert_time(reading.timestamp)
    else:
        print("✅ Normal conditions.")
        logging.info("Conditions normal. Temp=%.1f, Humidity=%.1f", reading.temperature, reading.humidity)
        
if __name__ == "__main__":                                                              #Designed to work as a background service inside a Docker container.
    while True:
        check_alert_conditions()
        time.sleep(60)

