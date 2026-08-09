from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

def make_engine(url: str | None = None):
    return create_engine(url or settings.database_url, connect_args={"check_same_thread": False} if (url or settings.database_url).startswith("sqlite") else {})

engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

