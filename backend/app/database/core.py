from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings 

# Use the real URL from your .env file
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,        # Increase from 5 to 20
    max_overflow=40,     # Allow more temporary connections
    pool_timeout=30,     # Wait 30s before failing
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get DB session in routers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()