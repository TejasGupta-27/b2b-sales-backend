#!/usr/bin/env python3
"""
Test script for organization and user metrics
"""

import sys
import asyncio
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from db.database import get_db
from services.metrics_service import get_metrics_service
import time

def test_organization_user_metrics():
    """Test organization and user metrics collection"""
    print("🧪 Testing Organization and User Metrics")
    print("=" * 50)
    
    # Get database session and metrics service
    db = next(get_db())
    metrics_service = get_metrics_service()
    
    try:
        print("\n📊 Updating organization metrics...")
        metrics_service.update_organization_metrics(db)
        
        print("👥 Updating user metrics...")
        metrics_service.update_user_metrics(db)
        
        print("\n📈 Testing user API usage tracking...")
        # Simulate some user API usage
        metrics_service.record_user_api_usage(
            user_id="test-user-1",
            user_email="test@example.com",
            organization_id="test-org-1",
            endpoint="/api/chat",
            method="POST"
        )
        
        print("🎯 Testing user feature usage...")
        metrics_service.record_user_feature_usage(
            user_id="test-user-1",
            organization_id="test-org-1",
            feature="chat",
            action="send_message"
        )
        
        print("💬 Testing user chat interactions...")
        metrics_service.record_user_chat_interaction(
            user_id="test-user-1",
            organization_id="test-org-1",
            interaction_type="message_sent"
        )
        
        print("📄 Testing user quote generation...")
        metrics_service.record_user_quote_generation(
            user_id="test-user-1",
            user_email="test@example.com",
            organization_id="test-org-1",
            quote_status="success"
        )
        
        print("🏢 Testing organization revenue metrics...")
        metrics_service.update_organization_revenue_metrics(
            organization_id="test-org-1",
            organization_name="Test Organization",
            metric_type="total_revenue",
            value=150000.0,
            currency="USD"
        )
        
        print("🔒 Testing tenant isolation health...")
        metrics_service.update_tenant_isolation_health(
            organization_id="test-org-1",
            check_type="data_isolation",
            status=1
        )
        
        print("\n📋 Getting current metrics...")
        metrics_data = metrics_service.get_metrics()
        
        # Count organization and user related metrics
        org_metrics_count = 0
        user_metrics_count = 0
        
        for line in metrics_data.split('\n'):
            if line.startswith('b2b_organization_'):
                org_metrics_count += 1
            elif line.startswith('b2b_user_'):
                user_metrics_count += 1
        
        print(f"✅ Found {org_metrics_count} organization metric lines")
        print(f"✅ Found {user_metrics_count} user metric lines")
        
        # Show sample metrics
        print("\n📊 Sample Organization Metrics:")
        for line in metrics_data.split('\n'):
            if 'b2b_organizations_total' in line and not line.startswith('#'):
                print(f"  {line}")
        
        print("\n👥 Sample User Metrics:")
        for line in metrics_data.split('\n'):
            if 'b2b_users_total' in line and not line.startswith('#'):
                print(f"  {line}")
            elif 'b2b_user_api_usage' in line and not line.startswith('#'):
                print(f"  {line}")
                break  # Just show one example
        
        print("\n🎉 Organization and User Metrics Test Completed Successfully!")
        print(f"📊 Total organization metrics tracked: {org_metrics_count}")
        print(f"👥 Total user metrics tracked: {user_metrics_count}")
        
        # Test recommendation for dashboard
        print("\n📋 Dashboard Setup Recommendations:")
        print("1. 🏢 Organization Overview Panel - Shows org types and counts")
        print("2. 📊 Organization Quota Utilization - Shows usage vs limits")
        print("3. 👥 User Distribution by Role - Shows user roles breakdown")
        print("4. 📈 Top Active Users - Shows most active users")
        print("5. 🌐 Organization Activity Trends - Shows org activity over time")
        print("6. 🔗 User API Usage Rate - Shows API usage per user")
        print("7. 🎯 User Lead Management Performance - Shows leads per user")
        
        print("\n🔗 Access your updated dashboard at:")
        print("   http://48.210.58.7/monitoring/")
        print("   (admin/admin123)")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()

if __name__ == "__main__":
    test_organization_user_metrics() 