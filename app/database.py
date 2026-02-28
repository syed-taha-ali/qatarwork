"""
Database Configuration
Handles database connections with proper pooling and concurrency settings.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Database engine configuration
engine_config = {
    "poolclass": QueuePool,
    "pool_size": 10,              # Maximum number of connections to keep in pool
    "max_overflow": 20,            # Maximum overflow connections beyond pool_size
    "pool_timeout": 30,            # Seconds to wait before giving up on getting a connection
    "pool_recycle": 3600,          # Recycle connections after 1 hour
    "pool_pre_ping": True,         # Verify connections before using them
    "echo": False,                 # Set to True for SQL query logging (development only)
}

# Add SQLite-specific settings if using SQLite
if "sqlite" in settings.DATABASE_URL:
    engine_config["connect_args"] = {"check_same_thread": False}
    # SQLite doesn't support connection pooling the same way
    engine_config.pop("poolclass", None)
    engine_config.pop("pool_size", None)
    engine_config.pop("max_overflow", None)
    logger.warning("Using SQLite - connection pooling disabled")

# Create engine with configuration
engine = create_engine(settings.DATABASE_URL, **engine_config)

# Session factory with proper isolation level
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative base for models
Base = declarative_base()


def get_db():
    """
    Database dependency for FastAPI routes.
    
    Yields a database session and ensures proper cleanup.
    
    Usage:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
