from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings
import logging
import os

logger = logging.getLogger(__name__)

# Get CPU count for optimal pool sizing
import multiprocessing
cpu_count = multiprocessing.cpu_count()

# Calculate optimal pool size based on CPU cores and workers
# Assuming 4 workers (from gunicorn config), we want 2-3 connections per worker
optimal_pool_size = min(cpu_count * 2, 50)  # Cap at 50 connections
optimal_max_overflow = min(optimal_pool_size * 1.5, 75)  # Cap at 75 overflow

# Create SQLAlchemy engine with optimized settings for multi-user support
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=optimal_pool_size,  # Dynamic pool size based on CPU cores
    max_overflow=optimal_max_overflow,  # Dynamic overflow based on pool size
    pool_timeout=30,  # Add timeout for getting connections
    echo=settings.db_echo_sql,  # Use configurable SQL logging
    connect_args={
        "connect_timeout": 10,
        "application_name": "b2b_sales_backend"  # Help identify connections
    }
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

def test_connection():
    """Test database connection"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            return result.fetchone()[0] == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

def reset_database():
    """Reset database by dropping and recreating all tables"""
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("Database reset completed")
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise

def cleanup_conflicting_data():
    """Clean up any conflicting data from previous setups"""
    try:
        with engine.connect() as connection:
            # Clean up any orphaned data
            connection.execute(text("DELETE FROM chat_messages WHERE lead_id IS NULL"))
            connection.execute(text("DELETE FROM leads WHERE id NOT IN (SELECT DISTINCT lead_id FROM chat_messages WHERE lead_id IS NOT NULL)"))
            connection.commit()
            logger.info("Conflicting data cleanup completed")
    except Exception as e:
        logger.warning(f"Data cleanup failed (this is normal for fresh installs): {e}")

def get_connection_stats():
    """Get database connection pool statistics"""
    try:
        return {
            "pool_size": engine.pool.size(),
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
            "invalid": engine.pool.invalid()
        }
    except Exception as e:
        logger.error(f"Failed to get connection stats: {e}")
        return {} 