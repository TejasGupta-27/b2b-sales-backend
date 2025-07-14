#!/usr/bin/env python3
"""
Check current enum values in the database
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from db.database import get_db, test_connection
from sqlalchemy import text

def check_enum_values():
    """Check current enum values in the database"""
    
    # Test database connection first
    if not test_connection():
        print("❌ Database connection failed!")
        return
    
    db = next(get_db())
    try:
        print("🔍 Checking enum values in database...")
        
        # Check UserRole enum values
        result = db.execute(text("""
            SELECT enumlabel 
            FROM pg_enum 
            WHERE enumtypid = (
                SELECT oid 
                FROM pg_type 
                WHERE typname = 'userrole'
            )
            ORDER BY enumlabel;
        """))
        
        userrole_values = [row[0] for row in result.fetchall()]
        
        print(f"\n📋 Current UserRole enum values in database:")
        for value in userrole_values:
            print(f"   - {value}")
        
        # Check what our Python enum expects
        from db.models import UserRole
        
        print(f"\n📋 Expected UserRole enum values from Python:")
        for role in UserRole:
            print(f"   - {role.value}")
        
        # Check for mismatches
        db_set = set(userrole_values)
        python_set = set(role.value for role in UserRole)
        
        missing_in_db = python_set - db_set
        extra_in_db = db_set - python_set
        
        if missing_in_db:
            print(f"\n❌ Missing in database: {missing_in_db}")
        
        if extra_in_db:
            print(f"\n⚠️ Extra in database: {extra_in_db}")
        
        if not missing_in_db and not extra_in_db:
            print(f"\n✅ Enum values match!")
        else:
            print(f"\n🔧 Enum values need to be fixed")
            
        return userrole_values
        
    except Exception as e:
        print(f"❌ Error checking enum values: {e}")
        return None
    finally:
        db.close()

def fix_enum_values():
    """Fix enum values to match Python enum"""
    
    db = next(get_db())
    try:
        print("\n🔧 Fixing enum values...")
        
        from db.models import UserRole
        
        # Drop the existing enum type and recreate it
        print("1. Dropping existing enum type...")
        
        # First, we need to handle any existing data
        # Let's check if there are any users with the old enum values
        result = db.execute(text("SELECT COUNT(*) FROM users"))
        user_count = result.scalar()
        
        if user_count > 0:
            print(f"⚠️ Found {user_count} existing users. Need to handle existing data.")
            
            # Convert the column to text temporarily
            db.execute(text("ALTER TABLE users ALTER COLUMN role TYPE TEXT USING role::TEXT"))
            db.commit()
            print("   - Converted role column to TEXT")
        
        # Drop the enum type
        db.execute(text("DROP TYPE IF EXISTS userrole CASCADE"))
        db.commit()
        print("   - Dropped old enum type")
        
        # Create new enum type with correct values
        enum_values = "', '".join([role.value for role in UserRole])
        create_enum_sql = f"CREATE TYPE userrole AS ENUM ('{enum_values}')"
        
        db.execute(text(create_enum_sql))
        db.commit()
        print(f"   - Created new enum type with values: {[role.value for role in UserRole]}")
        
        # Convert the column back to enum
        db.execute(text("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole"))
        db.commit()
        print("   - Converted role column back to enum")
        
        print("✅ Enum values fixed successfully!")
        
    except Exception as e:
        print(f"❌ Error fixing enum values: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🔍 B2B Sales AI - Enum Values Checker")
    print("=" * 50)
    
    values = check_enum_values()
    
    if values is not None:
        # Check if we need to fix enum values
        from db.models import UserRole
        python_values = set(role.value for role in UserRole)
        db_values = set(values)
        
        if python_values != db_values:
            print("\n🤔 Do you want to fix the enum values? (y/n): ", end="")
            try:
                choice = input().lower().strip()
                if choice in ['y', 'yes']:
                    fix_enum_values()
                else:
                    print("🔧 Enum values not fixed. You can run this script again later.")
            except (EOFError, KeyboardInterrupt):
                print("\n🔧 Enum values not fixed. You can run this script again later.") 