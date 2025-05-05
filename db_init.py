from sqlalchemy import create_engine
from models import Base 
from dotenv import load_dotenv
import os 

load_dotenv()
DB_URL = os.getenv("DB_URL")

engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
print("database and table created")


