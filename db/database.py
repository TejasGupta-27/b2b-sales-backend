from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings
import logging

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with optimized settings
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=20,  # Increased from default 5
    max_overflow=30,  # Increased from default 10
    pool_timeout=30,  # Add timeout for getting connections
    echo=settings.db_echo_sql,  # Use configurable SQL logging
    connect_args={
        "connect_timeout": 10
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

def drop_all_tables():
    """Drop all tables - useful for clean reset"""
    try:
        logger.info("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("All tables dropped successfully")
    except Exception as e:
        logger.error(f"Failed to drop tables: {e}")
        raise

def create_tables():
    """Create all tables"""
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise

def reset_database():
    """Drop and recreate all tables - complete reset"""
    try:
        logger.info("Performing complete database reset...")
        drop_all_tables()
        create_tables()
        logger.info("Database reset completed successfully")
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise

def test_connection():
    """Test database connection"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

def cleanup_conflicting_data():
    """Clean up any conflicting data or types from previous setups"""
    try:
        with engine.connect() as conn:
            # Check and handle existing enum types
            logger.info("Checking for existing enum types...")
            
            # Check if old uppercase enum exists and drop it
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel IN ('USER', 'ASSISTANT', 'SYSTEM')
                );
            """))
            
            if result.scalar():
                logger.info("Found old uppercase enum values, cleaning up...")
                # This is complex and might require manual intervention
                # For now, just log the issue
                logger.warning("Manual cleanup may be required for enum conflicts")
            
            conn.commit()
            logger.info("Cleanup check completed")
            
    except Exception as e:
        logger.warning(f"Cleanup check failed (this might be normal): {e}") 