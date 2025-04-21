from sqlalchemy import create_engine
from config import DATABASE_URL
from models import Base, Notification


def initialize_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    print("DB init success")

if __name__ == "__main__":
    try:
        initialize_db()
    except Exception as e:
        print(f"DB init fail: {e}")
