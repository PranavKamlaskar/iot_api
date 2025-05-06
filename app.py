from flask import Flask, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import SensorReading, Base
from dotenv import load_dotenv
import os 
from datetime import datetime, timedelta, timezone
from flask import Response
import csv
from io import StringIO
import io
from flask import render_template
import logging

#app.py Receives, stores, and serves temperature/humidity data
#.env    Keeps secrets/config clean and secure
#alert_checker.py    Pulls data from /api/latest and sends alerts
#docker-compose.yml  Runs web, db, and alerts as containers




# Logging setup  Logs all received readings.This helps with debugging and auditing incoming data.
logging.basicConfig(
        filename="readings.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
)



#load env vars  
load_dotenv()
API_KEY= os.getenv("API_KEY")
DB_URL= os.getenv("DB_URL")

READ_API_KEY = os.getenv("READ_API_KEY")



#db setup    Connects to PostgreSQL using SQLAlchemy. Creates tables if they don’t exist (via Base.metadata.create_all()).
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
#flask app
app = Flask(__name__)

@app.route("/api/data", methods=["POST"])
def receive_data():
    # this line is used to check API key
    if request.headers.get("X-API-KEY") != API_KEY:         #Requires an API key.Stores JSON { temperature, humidity } in the DB.Logs the reading.
        return jsonify({"error": "unauthorized access"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "invalid JSON"}), 400

    try:
        temp = float(data["temperature"])
        hum = float(data["humidity"])
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid Payload"}), 400

    #save to db
    session = Session()
    reading = SensorReading(temperature=temp, humidity=hum)  # timestamp will be auto-set
    session.add(reading)
    session.commit()
    session.close()
    
    logging.info(f"Received reading: Temperature={temp}°C, Humidity={hum}%")

    return jsonify({"message": "Data received"}), 201

@app.route("/")
def index():
        return "IoT Temperature Monitor API is running!"

@app.route("/api/latest", methods=["GET"])
def latest_reading():
    if request.headers.get("X-READ-KEY") != READ_API_KEY:           #Requires a read key.Returns the most recent reading
        return jsonify({"error": "unauthorized access"}), 401

    session= Session()
    reading= session.query(SensorReading).order_by(SensorReading.timestamp.desc()).first()
    session.close()

    if not reading:
        return jsonify({"error": "no data available "}),404

    return jsonify({
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "timestamp": reading.timestamp.isoformat()
    }), 200

@app.route("/api/readings", methods=["GET"])
def get_readings():
    if request.headers.get("X-READ-KEY") != READ_API_KEY:
        return jsonify({"error": "unauthorized access"}), 401

    session = Session()

    # Optional filter by time range
    range_param = request.args.get("range")
    query = session.query(SensorReading)

    if range_param:
        now = datetime.utcnow()
        if range_param == "24h":
            since = now - timedelta(hours=24)
        elif range_param == "7d":
            since = now - timedelta(days=7)
        else:
            return jsonify({"error": "Invalid range. Use '24h' or '7d'."}), 400
        query = query.filter(SensorReading.timestamp >= since)

    readings = query.order_by(SensorReading.timestamp.desc()).all()
    session.close()

    # Return JSON list
    data = [
        {
            "temperature": r.temperature,
            "humidity": r.humidity,
            "timestamp": r.timestamp.isoformat()
        } for r in readings
    ]

    return jsonify(data), 200

@app.route("/api/readings.csv", methods=["GET"])
def export_csv():
    session = Session()

    # Optional time filter
    time_range = request.args.get("range")  # e.g., 24h or 7d
    query = session.query(SensorReading)

    if time_range == "24h":
        since = datetime.utcnow() - timedelta(days=1)
        query = query.filter(SensorReading.timestamp >= since)
    elif time_range == "7d":
        since = datetime.utcnow() - timedelta(days=7)
        query = query.filter(SensorReading.timestamp >= since)

    readings = query.order_by(SensorReading.timestamp.desc()).all()
    session.close()

    # Write to CSV using StringIO
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "temperature", "humidity"])  # header

    for r in readings:
        writer.writerow([r.timestamp.isoformat(), r.temperature, r.humidity])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=readings.csv"
    return response

@app.route("/dashboard", methods=["GET"])
def dashboard():
    session = Session()
    readings = session.query(SensorReading).order_by(SensorReading.timestamp.desc()).limit(20).all()
    session.close()
    return render_template("dashboard.html", readings=readings)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

