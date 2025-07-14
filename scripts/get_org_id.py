#!/usr/bin/env python3
"""
Get organization ID for registration
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from db.database import get_db, test_connection
from db.models import Organization as DBOrganization
import uuid

def get_organization_id():
    """Get the first available organization ID"""
    
    # Test database connection first
    if not test_connection():
        print("❌ Database connection failed!")
        print("🔧 Make sure your database is running and accessible")
        return None
    
    db = next(get_db())
    try:
        # Look for existing organizations
        org = db.query(DBOrganization).first()
        if org:
            print(f"✅ Organization found:")
            print(f"   ID: {org.id}")
            print(f"   Name: {org.name}")
            print(f"   Domain: {org.domain}")
            print(f"   Type: {org.org_type}")
            print(f"   Max Users: {org.max_users}")
            print(f"\n📋 Use this ID for registration: {org.id}")
            print(f"\n📝 Copy this for your frontend:")
            print(f'   organization_id: "{org.id}"')
            return org.id
        else:
            print("❌ No organization found in database!")
            print("\n🔧 Options to fix this:")
            print("1. Run setup script: python scripts/setup_initial_data.py")
            print("2. Or create organization manually (see below)")
            print("\n🏗️ To create organization manually:")
            print("   1. Login as admin if you have admin user")
            print("   2. Or run the create_default_org script")
            return None
    finally:
        db.close()

def create_default_organization():
    """Create a default organization if none exists"""
    from db.models import OrganizationType
    from datetime import datetime
    
    db = next(get_db())
    try:
        # Check if organization already exists
        existing_org = db.query(DBOrganization).first()
        if existing_org:
            print(f"✅ Organization already exists: {existing_org.name}")
            return existing_org.id
        
        # Create default organization
        org_id = str(uuid.uuid4())
        organization = DBOrganization(
            id=org_id,
            name="Default Organization",
            domain="example.com",
            org_type=OrganizationType.ENTERPRISE,
            max_users=50,
            max_leads=10000,
            ai_token_limit_monthly=500000,
            is_active=True,
            settings={
                "is_default": True,
                "created_by_script": True
            }
        )
        
        db.add(organization)
        db.commit()
        db.refresh(organization)
        
        print(f"✅ Created default organization:")
        print(f"   ID: {organization.id}")
        print(f"   Name: {organization.name}")
        print(f"   Domain: {organization.domain}")
        print(f"\n📋 Use this ID for registration: {organization.id}")
        
        return organization.id
        
    except Exception as e:
        print(f"❌ Failed to create organization: {e}")
        db.rollback()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    print("🏢 B2B Sales AI - Organization ID Finder")
    print("=" * 50)
    
    # First try to find existing organization
    org_id = get_organization_id()
    
    if not org_id:
        print("\n🔧 Creating default organization...")
        org_id = create_default_organization()
        
        if org_id:
            print(f"\n🎉 Success! Organization created with ID: {org_id}")
        else:
            print("\n❌ Failed to create organization")
            print("🔧 Try running: python scripts/setup_initial_data.py") 