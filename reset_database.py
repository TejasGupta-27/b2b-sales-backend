#!/usr/bin/env python3
"""
Database Reset Script for B2B Sales Backend

This script will:
1. Drop all existing tables
2. Remove conflicting enum types
3. Recreate tables from SQLAlchemy models
4. Provide a clean database state

Run this if you're having database conflicts or want to start fresh.
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from db.database import reset_database, test_connection, engine
from db.models import Base

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def force_cleanup_enums():
    """Force cleanup of conflicting enum types"""
    try:
        logger.info("🧹 Force cleaning up enum types...")
        with engine.connect() as conn:
            # Start a transaction
            trans = conn.begin()
            try:
                # Drop any existing enum types that might conflict
                cleanup_queries = [
                    "DROP TYPE IF EXISTS messagetype CASCADE;",
                    "DROP TYPE IF EXISTS leadstatus CASCADE;",
                ]
                
                for query in cleanup_queries:
                    try:
                        conn.execute(text(query))
                        logger.info(f"✅ Executed: {query}")
                    except Exception as e:
                        logger.warning(f"⚠️ Query failed (might be normal): {query} - {e}")
                
                trans.commit()
                logger.info("✅ Enum cleanup completed")
                
            except Exception as e:
                trans.rollback()
                logger.error(f"❌ Enum cleanup failed: {e}")
                raise
                
    except Exception as e:
        logger.error(f"❌ Force cleanup failed: {e}")
        raise

def main():
    """Main reset function"""
    print("🚀 B2B Sales Backend Database Reset Tool")
    print("=" * 50)
    
    # Confirm with user
    print("\n⚠️  WARNING: This will DELETE ALL DATA in your database!")
    print("This includes:")
    print("  - All leads")
    print("  - All chat messages") 
    print("  - All quotes")
    print("  - All recommendations")
    print("  - All other data")
    
    confirm = input("\nAre you sure you want to proceed? (type 'YES' to confirm): ")
    if confirm != 'YES':
        print("❌ Reset cancelled.")
        return
    
    try:
        # Test connection first
        logger.info("🔍 Testing database connection...")
        if not test_connection():
            logger.error("❌ Cannot connect to database. Check your connection settings.")
            return
        
        logger.info("✅ Database connection successful")
        
        # Force cleanup of enum types
        force_cleanup_enums()
        
        # Reset the database
        logger.info("🔄 Resetting database...")
        reset_database()
        
        logger.info("✅ Database reset completed successfully!")
        print("\n🎉 Database has been reset successfully!")
        print("You can now start your application with clean tables.")
        
    except Exception as e:
        logger.error(f"❌ Database reset failed: {e}")
        print(f"\n❌ Reset failed: {e}")
        print("\nIf you continue to have issues, you may need to:")
        print("1. Drop the entire database and recreate it")
        print("2. Check for any remaining alembic migration conflicts")
        print("3. Manually connect to postgres and run: DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        sys.exit(1)

if __name__ == "__main__":
    main() 