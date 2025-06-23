#!/usr/bin/env python3
"""
Fix Elasticsearch mapping issues by recreating indices with correct mappings.
This script addresses the form_factor field type mismatch error.
"""

import asyncio
import logging
from services.elasticsearch_service import get_elasticsearch_service

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Fix Elasticsearch mapping issues"""
    try:
        logger.info("🚀 Starting Elasticsearch mapping fix...")
        
        # Get elasticsearch service
        es_service = get_elasticsearch_service()
        
        # Test connection first
        if not await es_service.test_connection():
            logger.error("❌ Cannot connect to Elasticsearch. Please ensure it's running.")
            return
        
        # Fix mapping issues
        await es_service.fix_mapping_issues()
        
        # Verify the fix
        stats = await es_service.get_product_stats()
        logger.info(f"📊 Final stats: {stats}")
        
        logger.info("✅ Elasticsearch mapping fix completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to fix Elasticsearch mapping: {e}")
        raise
    finally:
        # Close the connection
        if 'es_service' in locals():
            await es_service.close()

if __name__ == "__main__":
    asyncio.run(main()) 