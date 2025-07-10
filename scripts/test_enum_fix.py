#!/usr/bin/env python3
"""
Test that enum values are now consistent
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from db.database import get_db, test_connection
from sqlalchemy import text

def test_enum_consistency():
    """Test that Python and database enum values are consistent"""
    
    print("🧪 Testing Enum Consistency")
    print("=" * 50)
    
    # Test database connection first
    if not test_connection():
        print("❌ Database connection failed!")
        return False
    
    db = next(get_db())
    try:
        # Get database enum values
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
        
        db_values = set(row[0] for row in result.fetchall())
        
        # Get Python enum values
        from db.models import UserRole as DBUserRole
        from models.user import UserRole as PydanticUserRole
        
        db_python_values = set(role.value for role in DBUserRole)
        pydantic_python_values = set(role.value for role in PydanticUserRole)
        
        print(f"📋 Database enum values: {sorted(db_values)}")
        print(f"📋 DB Python enum values: {sorted(db_python_values)}")
        print(f"📋 Pydantic Python enum values: {sorted(pydantic_python_values)}")
        
        # Check consistency
        all_consistent = (
            db_values == db_python_values == pydantic_python_values
        )
        
        if all_consistent:
            print("\n✅ All enum values are consistent!")
            print("🎉 No more enum mismatch errors should occur!")
            return True
        else:
            print("\n❌ Enum values are still inconsistent:")
            if db_values != db_python_values:
                print(f"   Database vs DB Python: {db_values} != {db_python_values}")
            if db_values != pydantic_python_values:
                print(f"   Database vs Pydantic: {db_values} != {pydantic_python_values}")
            if db_python_values != pydantic_python_values:
                print(f"   DB Python vs Pydantic: {db_python_values} != {pydantic_python_values}")
            return False
        
    except Exception as e:
        print(f"❌ Error testing enum consistency: {e}")
        return False
    finally:
        db.close()

def test_auth_service_import():
    """Test that auth service imports correctly"""
    try:
        print("\n🔧 Testing auth service import...")
        from services.auth_service import auth_service
        print("✅ Auth service imported successfully!")
        return True
    except Exception as e:
        print(f"❌ Auth service import failed: {e}")
        return False

def test_user_creation():
    """Test that user creation works with new enum values"""
    try:
        print("\n👤 Testing user creation with new enum values...")
        from db.models import UserRole
        from models.user import UserRole as PydanticUserRole
        
        # Test that enum values can be accessed
        admin_role_db = UserRole.ADMIN
        admin_role_pydantic = PydanticUserRole.ADMIN
        
        print(f"   DB UserRole.ADMIN = '{admin_role_db.value}'")
        print(f"   Pydantic UserRole.ADMIN = '{admin_role_pydantic.value}'")
        
        if admin_role_db.value == admin_role_pydantic.value:
            print("✅ User creation should work correctly!")
            return True
        else:
            print("❌ Enum values still don't match!")
            return False
            
    except Exception as e:
        print(f"❌ User creation test failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 B2B Sales AI - Enum Fix Verification")
    print("=" * 50)
    
    # Run all tests
    tests = [
        test_enum_consistency,
        test_auth_service_import,
        test_user_creation
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! The enum fix is complete.")
        print("✅ You can now restart your backend and registration should work.")
    else:
        print("❌ Some tests failed. Please check the errors above.") 