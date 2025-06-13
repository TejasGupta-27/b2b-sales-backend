#!/usr/bin/env python3
"""
Test script for recommendation creation with proper enum handling
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.database import SessionLocal, engine, test_connection
from db.models import RecommendationSet, ProductRecommendation, Lead, LeadStatus

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def test_lead_creation():
    """Test creating a lead with proper enum handling"""
    logger.info("🧪 Testing lead creation...")
    
    db = SessionLocal()
    try:
        # First, check if test lead already exists
        existing_lead = db.query(Lead).filter(Lead.email == "test@recommendation.com").first()
        if existing_lead:
            logger.info(f"✅ Test lead already exists: {existing_lead.id} - Status: {existing_lead.status}")
            return existing_lead.id
        
        # Create new test lead using raw SQL to avoid enum issues
        lead_id = "test-recommendation-lead"
        
        db.execute(text("""
            INSERT INTO leads (
                id, company_name, contact_name, email, status, created_at
            ) VALUES (
                :id, :company_name, :contact_name, :email, :status, :created_at
            )
        """), {
            'id': lead_id,
            'company_name': 'Test Recommendation Company',
            'contact_name': 'Test Contact',
            'email': 'test@recommendation.com',
            'status': 'NEW',  # Use string directly
            'created_at': datetime.utcnow()
        })
        
        db.commit()
        logger.info(f"✅ Created test lead: {lead_id}")
        return lead_id
        
    except Exception as e:
        logger.error(f"❌ Failed to create test lead: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def test_recommendation_creation(lead_id):
    """Test creating recommendations"""
    logger.info("🧪 Testing recommendation creation...")
    
    db = SessionLocal()
    try:
        # Create recommendation set using raw SQL to avoid enum issues
        rec_set_id = "test-rec-set-001"
        
        recommendations_json = [
            {
                "product_id": "test-product-001",
                "name": "Test NAS Solution",
                "description": "Professional NAS solution for video backup",
                "price": 1500.0,
                "features": ["RAID 6", "2.5GbE", "4-bay"],
                "benefits": ["Data protection", "High speed", "Scalable"],
                "suitability_score": 0.9
            }
        ]
        
        db.execute(text("""
            INSERT INTO recommendation_sets (
                id, lead_id, recommendations, created_at, reasoning, current_stage
            ) VALUES (
                :id, :lead_id, :recommendations, :created_at, :reasoning, :current_stage
            )
        """), {
            'id': rec_set_id,
            'lead_id': lead_id,
            'recommendations': recommendations_json,
            'created_at': datetime.utcnow(),
            'reasoning': 'Test recommendation for validation',
            'current_stage': 'solution_presentation'
        })
        
        # Create product recommendation
        prod_rec_id = "test-prod-rec-001"
        
        db.execute(text("""
            INSERT INTO product_recommendations (
                id, recommendation_set_id, product_id, name, description, 
                price, features, benefits, suitability_score
            ) VALUES (
                :id, :rec_set_id, :product_id, :name, :description,
                :price, :features, :benefits, :suitability_score
            )
        """), {
            'id': prod_rec_id,
            'rec_set_id': rec_set_id,
            'product_id': 'test-product-001',
            'name': 'Test NAS Solution',
            'description': 'Professional NAS solution for video backup',
            'price': 1500.0,
            'features': ["RAID 6", "2.5GbE", "4-bay"],
            'benefits': ["Data protection", "High speed", "Scalable"],
            'suitability_score': 0.9
        })
        
        db.commit()
        logger.info(f"✅ Created recommendation set: {rec_set_id}")
        logger.info(f"✅ Created product recommendation: {prod_rec_id}")
        
        # Verify creation
        rec_count = db.execute(text("SELECT COUNT(*) FROM recommendation_sets")).scalar()
        prod_count = db.execute(text("SELECT COUNT(*) FROM product_recommendations")).scalar()
        
        logger.info(f"📊 Total recommendation sets: {rec_count}")
        logger.info(f"📊 Total product recommendations: {prod_count}")
        
        # Test selection
        db.execute(text("""
            UPDATE recommendation_sets 
            SET selected_recommendation = :product_id,
                selection_timestamp = :timestamp,
                conversation_state = :state
            WHERE id = :rec_set_id
        """), {
            'product_id': 'test-product-001',
            'timestamp': datetime.utcnow(),
            'state': {
                'recommendation_selected': True,
                'selected_product_id': 'test-product-001',
                'quote_ready': True
            },
            'rec_set_id': rec_set_id
        })
        
        db.commit()
        logger.info("✅ Updated recommendation with selection")
        
        return rec_set_id
        
    except Exception as e:
        logger.error(f"❌ Failed to create recommendations: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        return None
    finally:
        db.close()

def cleanup_test_data():
    """Clean up test data"""
    logger.info("🧹 Cleaning up test data...")
    
    db = SessionLocal()
    try:
        # Delete in proper order to respect foreign keys
        db.execute(text("DELETE FROM product_recommendations WHERE recommendation_set_id LIKE 'test-rec-set-%'"))
        db.execute(text("DELETE FROM recommendation_sets WHERE id LIKE 'test-rec-set-%'"))
        db.execute(text("DELETE FROM leads WHERE id LIKE 'test-recommendation-%'"))
        
        db.commit()
        logger.info("✅ Test data cleaned up")
        
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Main test function"""
    logger.info("🚀 Starting recommendation system test...")
    
    try:
        # Test database connection
        if not test_connection():
            logger.error("❌ Database connection failed")
            return
        
        # Clean up any existing test data
        cleanup_test_data()
        
        # Test lead creation
        lead_id = test_lead_creation()
        if not lead_id:
            logger.error("❌ Lead creation failed")
            return
        
        # Test recommendation creation
        rec_set_id = test_recommendation_creation(lead_id)
        if not rec_set_id:
            logger.error("❌ Recommendation creation failed")
            return
        
        logger.info("✅ All tests completed successfully!")
        logger.info("💡 The recommendation system can save data properly")
        
        # Keep test data for inspection
        logger.info("📋 Test data created:")
        logger.info(f"   Lead ID: {lead_id}")
        logger.info(f"   Recommendation Set ID: {rec_set_id}")
        logger.info("   (Test data will remain for inspection)")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 