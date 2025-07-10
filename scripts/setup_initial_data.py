#!/usr/bin/env python3
"""
Initial setup script for B2B Sales AI Assistant multi-user system.
This script creates the initial admin user and organization.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from db.database import create_tables, get_db, test_connection
from db.models import User as DBUser, Organization as DBOrganization, UserRole, OrganizationType
from services.auth_service import auth_service
from config import settings

def create_initial_organization(db: Session) -> DBOrganization:
    """Create the initial organization"""
    print("🏢 Creating initial organization...")
    
    # Check if any organization exists
    existing_org = db.query(DBOrganization).first()
    if existing_org:
        print(f"✅ Organization already exists: {existing_org.name}")
        return existing_org
    
    # Create default organization
    organization = DBOrganization(
        id=str(uuid.uuid4()),
        name="Default Organization",
        domain="example.com",
        org_type=OrganizationType.ENTERPRISE,
        max_users=50,  # Higher limit for initial org
        max_leads=10000,
        ai_token_limit_monthly=500000,  # Higher limit for initial org
        is_active=True,
        settings={
            "is_default": True,
            "created_by_setup": True
        }
    )
    
    db.add(organization)
    db.commit()
    db.refresh(organization)
    
    print(f"✅ Created organization: {organization.name} (ID: {organization.id})")
    return organization

def create_admin_user(db: Session, organization: DBOrganization) -> DBUser:
    """Create the initial admin user"""
    print("👤 Creating initial admin user...")
    
    # Check if admin user exists
    admin_email = "admin@example.com"
    existing_admin = db.query(DBUser).filter(DBUser.email == admin_email).first()
    if existing_admin:
        print(f"✅ Admin user already exists: {existing_admin.email}")
        return existing_admin
    
    # Create admin user
    admin_password = "admin123"  # Default password - should be changed immediately
    hashed_password = auth_service.get_password_hash(admin_password)
    
    admin_user = DBUser(
        id=str(uuid.uuid4()),
        email=admin_email,
        hashed_password=hashed_password,
        first_name="System",
        last_name="Administrator",
        role=UserRole.ADMIN,
        organization_id=organization.id,
        is_active=True,
        is_verified=True,
        api_rate_limit=10000,  # Higher limit for admin
        ai_token_limit=100000,  # Higher limit for admin
        preferences={
            "created_by_setup": True
        }
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    print(f"✅ Created admin user: {admin_user.email}")
    print(f"🔑 Default password: {admin_password}")
    print("⚠️  IMPORTANT: Please change the admin password immediately after first login!")
    
    return admin_user

def create_demo_users(db: Session, organization: DBOrganization):
    """Create demo users for testing"""
    print("👥 Creating demo users...")
    
    demo_users = [
        {
            "email": "sales1@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": UserRole.SALES_AGENT
        },
        {
            "email": "manager@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "role": UserRole.SALES_MANAGER
        },
        {
            "email": "viewer@example.com",
            "first_name": "Bob",
            "last_name": "Wilson",
            "role": UserRole.VIEWER
        }
    ]
    
    for user_data in demo_users:
        # Check if user exists
        existing_user = db.query(DBUser).filter(DBUser.email == user_data["email"]).first()
        if existing_user:
            print(f"   - User already exists: {existing_user.email}")
            continue
        
        # Create demo user
        password = "demo123"  # Default password for demo users
        hashed_password = auth_service.get_password_hash(password)
        
        demo_user = DBUser(
            id=str(uuid.uuid4()),
            email=user_data["email"],
            hashed_password=hashed_password,
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            role=user_data["role"],
            organization_id=organization.id,
            is_active=True,
            is_verified=True,
            api_rate_limit=settings.default_user_api_rate_limit,
            ai_token_limit=settings.default_user_ai_token_limit,
            preferences={
                "created_by_setup": True,
                "is_demo_user": True
            }
        )
        
        db.add(demo_user)
        print(f"   - Created demo user: {demo_user.email} ({demo_user.role.value})")
    
    db.commit()
    print("✅ Demo users created successfully")

def setup_database():
    """Initialize database with tables"""
    print("🗄️  Setting up database...")
    
    if not test_connection():
        print("❌ Database connection failed!")
        return False
    
    try:
        create_tables()
        print("✅ Database tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 B2B Sales AI Assistant - Initial Setup")
    print("=" * 50)
    
    # Setup database
    if not setup_database():
        sys.exit(1)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Create initial organization
        organization = create_initial_organization(db)
        
        # Create admin user
        admin_user = create_admin_user(db, organization)
        
        # Create demo users
        create_demo_users(db, organization)
        
        print("\n" + "=" * 50)
        print("🎉 Initial setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the application")
        print("2. Login with admin credentials:")
        print(f"   Email: {admin_user.email}")
        print("   Password: admin123")
        print("3. Change the admin password immediately")
        print("4. Create additional organizations and users as needed")
        print("\nDemo users are also available:")
        print("- sales1@example.com / demo123 (Sales Agent)")
        print("- manager@example.com / demo123 (Sales Manager)")
        print("- viewer@example.com / demo123 (Viewer)")
        print("\n⚠️  Remember to change all default passwords in production!")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main() 