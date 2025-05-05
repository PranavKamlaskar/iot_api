from sqlalchemy import Column, Integer, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone, timedelta

Base = declarative_base()

class SensorReading(Base):
        __tablename__ = 'readings'

        id = Column(Integer, primary_key=True)
        temperature = Column(Float, nullable=False)
        humidity = Column(Float, nullable=False)
        timestamp = Column(DateTime, default=datetime.utcnow)
