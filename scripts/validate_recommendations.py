#!/usr/bin/env python3
"""
Validation script for recommendation data integrity
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.database import SessionLocal, engine, test_connection
from db.models import RecommendationSet, ProductRecommendation, Lead, LeadStatus
from models.recommendation import RecommendationSet as PydanticRecommendationSet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_database_schema():
    """Validate database schema and constraints"""
    logger.info("🔍 Validating database schema...")
    
    try:
        # Test connection
        if not test_connection():
            logger.error("❌ Database connection failed")
            return False
        
        with engine.connect() as conn:
            # Check if tables exist
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('recommendation_sets', 'product_recommendations', 'leads')
            """))
            
            tables = [row[0] for row in result.fetchall()]
            
            required_tables = ['recommendation_sets', 'product_recommendations', 'leads']
            missing_tables = [t for t in required_tables if t not in tables]
            
            if missing_tables:
                logger.error(f"❌ Missing tables: {missing_tables}")
                return False
            
            logger.info("✅ All required tables exist")
            
            # Check recommendation_sets structure
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'recommendation_sets'
                ORDER BY ordinal_position
            """))
            
            rec_columns = [(row[0], row[1], row[2]) for row in result.fetchall()]
            logger.info(f"📋 recommendation_sets columns: {rec_columns}")
            
            # Check product_recommendations structure
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'product_recommendations'
                ORDER BY ordinal_position
            """))
            
            prod_columns = [(row[0], row[1], row[2]) for row in result.fetchall()]
            logger.info(f"📋 product_recommendations columns: {prod_columns}")
            
            # Check leads table structure and enums
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'leads'
                ORDER BY ordinal_position
            """))
            
            lead_columns = [(row[0], row[1], row[2]) for row in result.fetchall()]
            logger.info(f"📋 leads columns: {lead_columns}")
            
            # Check enum values for status
            try:
                result = conn.execute(text("""
                    SELECT enumlabel 
                    FROM pg_enum 
                    WHERE enumtypid = (
                        SELECT oid 
                        FROM pg_type 
                        WHERE typname = 'leadstatus'
                    )
                """))
                enum_values = [row[0] for row in result.fetchall()]
                logger.info(f"📋 leadstatus enum values: {enum_values}")
            except Exception as e:
                logger.warning(f"⚠️ Could not get enum values: {e}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Schema validation failed: {e}")
        return False

def validate_recommendation_data():
    """Validate existing recommendation data"""
    logger.info("🔍 Validating recommendation data integrity...")
    
    db = SessionLocal()
    try:
        # Count total records
        rec_count = db.query(RecommendationSet).count()
        prod_count = db.query(ProductRecommendation).count()
        
        logger.info(f"📊 Found {rec_count} recommendation sets, {prod_count} product recommendations")
        
        # Check for orphaned product recommendations
        orphaned = db.execute(text("""
            SELECT pr.id, pr.recommendation_set_id
            FROM product_recommendations pr
            LEFT JOIN recommendation_sets rs ON pr.recommendation_set_id = rs.id
            WHERE rs.id IS NULL
        """)).fetchall()
        
        if orphaned:
            logger.warning(f"⚠️ Found {len(orphaned)} orphaned product recommendations")
            for orphan in orphaned[:5]:  # Show first 5
                logger.warning(f"   Orphaned: {orphan[0]} -> {orphan[1]}")
        else:
            logger.info("✅ No orphaned product recommendations found")
        
        # Check for recommendations with missing required fields
        invalid_recs = db.execute(text("""
            SELECT id, name, product_id, price
            FROM product_recommendations
            WHERE name IS NULL OR name = '' OR product_id IS NULL OR product_id = ''
        """)).fetchall()
        
        if invalid_recs:
            logger.warning(f"⚠️ Found {len(invalid_recs)} recommendations with missing required fields")
            for invalid in invalid_recs[:5]:  # Show first 5
                logger.warning(f"   Invalid: {invalid}")
        else:
            logger.info("✅ All product recommendations have required fields")
        
        # Check JSON field integrity in recommendation_sets (only check 'recommendations' column)
        invalid_json = db.execute(text("""
            SELECT id, recommendations
            FROM recommendation_sets
            WHERE recommendations IS NOT NULL AND NOT (recommendations::text ~ '^\\[.*\\]$' OR recommendations::text = 'null')
        """)).fetchall()
        
        if invalid_json:
            logger.warning(f"⚠️ Found {len(invalid_json)} records with invalid JSON")
        else:
            logger.info("✅ All JSON fields are valid")
        
        logger.info("✅ Data validation completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Data validation failed: {e}")
        return False
    finally:
        db.close()

def test_recommendation_creation():
    """Test creating a sample recommendation"""
    logger.info("🧪 Testing recommendation creation...")
    
    db = SessionLocal()
    try:
        # Create a test lead if needed (using proper enum value)
        test_lead = db.query(Lead).filter(Lead.email == "test@validation.com").first()
        if not test_lead:
            test_lead = Lead(
                id="test-validation-lead",
                company_name="Test Company",
                contact_name="Test Contact",
                email="test@validation.com",
                status=LeadStatus.NEW,  # This should work now
                created_at=datetime.utcnow()
            )
            db.add(test_lead)
            db.commit()
            db.refresh(test_lead)
            logger.info(f"✅ Created test lead with status: {test_lead.status}")
        else:
            logger.info(f"✅ Test lead already exists with status: {test_lead.status}")
        
        # Create test recommendation set
        test_rec_set = RecommendationSet(
            id="test-validation-rec-set",
            lead_id=test_lead.id,
            recommendations=[
                {
                    "product_id": "test-product-1",
                    "name": "Test Product",
                    "description": "Test product description",
                    "price": 100.0,
                    "features": ["Feature 1", "Feature 2"],
                    "benefits": ["Benefit 1", "Benefit 2"],
                    "suitability_score": 0.8
                }
            ],
            created_at=datetime.utcnow(),
            reasoning="Test reasoning",
            next_steps=["Step 1", "Step 2"],
            conversation_state={"test": True},
            current_stage="test"
        )
        
        db.add(test_rec_set)
        
        # Create test product recommendation
        test_prod_rec = ProductRecommendation(
            id="test-validation-prod-rec",
            recommendation_set_id=test_rec_set.id,
            product_id="test-product-1",
            name="Test Product",
            description="Test product description",
            price=100.0,
            features=["Feature 1", "Feature 2"],
            benefits=["Benefit 1", "Benefit 2"],
            suitability_score=0.8
        )
        
        db.add(test_prod_rec)
        db.commit()
        
        logger.info("✅ Test recommendation created successfully")
        
        # Verify the creation
        created_rec_set = db.query(RecommendationSet).filter(RecommendationSet.id == "test-validation-rec-set").first()
        created_prod_rec = db.query(ProductRecommendation).filter(ProductRecommendation.id == "test-validation-prod-rec").first()
        
        if created_rec_set and created_prod_rec:
            logger.info("✅ Test records verified in database")
            logger.info(f"   Rec Set ID: {created_rec_set.id}")
            logger.info(f"   Prod Rec ID: {created_prod_rec.id}")
            logger.info(f"   Lead ID: {created_rec_set.lead_id}")
        else:
            logger.error("❌ Test records not found after creation")
        
        # Clean up
        db.delete(test_prod_rec)
        db.delete(test_rec_set)
        db.delete(test_lead)
        db.commit()
        
        logger.info("✅ Test data cleaned up")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test recommendation creation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        return False
    finally:
        db.close()

def check_missing_data_reasons():
    """Check why there might be no recommendation data"""
    logger.info("🔍 Checking reasons for missing recommendation data...")
    
    db = SessionLocal()
    try:
        # Check if there are any leads at all
        lead_count = db.query(Lead).count()
        logger.info(f"📊 Total leads in database: {lead_count}")
        
        # Check if there are any chat messages
        try:
            chat_count = db.execute(text("SELECT COUNT(*) FROM chat_messages")).scalar()
            logger.info(f"📊 Total chat messages: {chat_count}")
        except Exception as e:
            logger.warning(f"⚠️ Could not count chat messages: {e}")
        
        # Check recent activity
        try:
            recent_leads = db.execute(text("""
                SELECT id, company_name, created_at 
                FROM leads 
                ORDER BY created_at DESC 
                LIMIT 5
            """)).fetchall()
            
            if recent_leads:
                logger.info("📊 Recent leads:")
                for lead in recent_leads:
                    logger.info(f"   - {lead[1]} ({lead[0]}) - {lead[2]}")
            else:
                logger.warning("⚠️ No leads found in database")
        except Exception as e:
            logger.warning(f"⚠️ Could not get recent leads: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking missing data reasons: {e}")
        return False
    finally:
        db.close()

def main():
    """Main validation function"""
    logger.info("🚀 Starting recommendation validation...")
    
    success = True
    
    # Validate schema
    if not validate_database_schema():
        success = False
    
    # Validate data
    if not validate_recommendation_data():
        success = False
    
    # Check missing data reasons
    if not check_missing_data_reasons():
        success = False
    
    # Test creation
    if not test_recommendation_creation():
        success = False
    
    if success:
        logger.info("✅ All validations passed!")
        logger.info("💡 The recommendation system should work properly now")
    else:
        logger.error("❌ Some validations failed!")
        logger.info("💡 This indicates why recommendations aren't being saved properly")

if __name__ == "__main__":
    main() 