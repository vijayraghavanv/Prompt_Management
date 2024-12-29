# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.exceptions import AppException

settings = get_settings()

# Database URL format: postgresql://user:password@host:port/dbname
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,  # Enable connection health checks
        pool_size=5,  # Set connection pool size
        max_overflow=10  # Maximum number of connections to create beyond pool_size
    )
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create database engine: {str(e)}")
    raise AppException(
        status_code=500,
        detail="Database configuration error",
        error_code="DATABASE_CONFIG_ERROR"
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    Database dependency to be used in FastAPI endpoints.
    Yields a database session and ensures it's closed after use.

    Yields:
        Session: SQLAlchemy database session

    Raises:
        AppException: If database connection fails
    """
    db = SessionLocal()
    try:
        logger.debug("Creating database session")
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {str(e)}")
        raise AppException(
            status_code=500,
            detail="Database session error",
            error_code="DATABASE_SESSION_ERROR"
        )
    finally:
        logger.debug("Closing database session")
        db.close()