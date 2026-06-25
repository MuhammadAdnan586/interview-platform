"""
database.py
-------------
SQLite database setup via SQLAlchemy. SQLite is used deliberately —
zero external setup (no DB server to install/run), the whole database
lives in one file (interview_platform.db), which is perfect for a
portfolio project and small-scale real usage alike.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./interview_platform.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and always closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
