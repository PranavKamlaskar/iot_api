from flask import Flask, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import SensorReading, Base
from dotenv import load_dotenv
import os 
from datetime import datetime, timedelta, timezone

#load env vars
load_dotenv()
API_KEY= os.getenv("API_KEY")
DB_URL= os.getenv("DB_URL")

#db setup
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

#flask app
app = Flask(__name__)

@app.route("/api/data", methods=["POST"])
def receive_data():
    # this line is used to check API key
    if request.headers.get("X-API-KEY") != API_KEY:
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


    return jsonify({"message": "Data received"}), 201

@app.route("/")
def index():
        return "IoT Temperature Monitor API is running!"

@app.route("/api/latest", methods=["GET"])
def latest_reading():
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


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

