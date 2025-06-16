#!/usr/bin/env python3
"""
Initialize Elasticsearch Vector Search
This script sets up the vector search indices and loads initial data
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import from services
sys.path.append(str(Path(__file__).parent.parent))

from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from config import settings
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def main():
    """Initialize Elasticsearch Vector Search"""
    try:
        print("🚀 Initializing Elasticsearch Vector Search...")
        
        # Check if Azure embeddings are configured
        if not settings.azure_embedding_endpoint or not settings.azure_embedding_api_key:
            print("❌ Azure embeddings not configured. Please set AZURE_EMBEDDING_ENDPOINT and AZURE_EMBEDDING_API_KEY")
            return
        
        # Initialize vector service
        vector_service = get_elasticsearch_vector_service(
            azure_embedding_endpoint=settings.azure_embedding_endpoint,
            azure_embedding_key=settings.azure_embedding_api_key
        )
        
        print("🔧 Initializing vector service...")
        await vector_service.initialize()
        
        print("📊 Checking current status...")
        stats = await vector_service.get_collection_stats()
        print(f"   Products: {stats['products_count']}")
        print(f"   Solutions: {stats['solutions_count']}")
        
        # Load data if empty
        if stats['products_count'] == 0 and stats['solutions_count'] == 0:
            print("🔄 Loading data from JSON files...")
            result = await vector_service.load_data_from_json(max_per_file=100)
            print(f"✅ Data loading completed: {result}")
            
            # Check stats again
            final_stats = await vector_service.get_collection_stats()
            print(f"📊 Final stats:")
            print(f"   Products: {final_stats['products_count']}")
            print(f"   Solutions: {final_stats['solutions_count']}")
        else:
            print("✅ Vector indices already contain data")
        
        # Perform test search
        print("🔍 Testing vector search...")
        try:
            test_products = await vector_service.vector_search_products(
                query="laptop computer workstation",
                size=3
            )
            print(f"   Found {len(test_products)} products in test search")
            for i, product in enumerate(test_products, 1):
                print(f"     {i}. {product.get('name', 'Unknown')} (Score: {product.get('_score', 0):.3f})")
        except Exception as e:
            print(f"⚠️ Test search failed: {e}")
        
        print("✅ Elasticsearch Vector Search initialization completed!")
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'vector_service' in locals():
            await vector_service.close()

if __name__ == "__main__":
    asyncio.run(main()) 