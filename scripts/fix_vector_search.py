#!/usr/bin/env python3
"""
Script to diagnose and fix vector search issues in the B2B sales backend.

This script:
1. Analyzes the current data quality
2. Reprocesses products with rich content generation
3. Syncs the vector index with enriched data
4. Tests vector search functionality
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.elasticsearch_service import get_elasticsearch_service
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from config import settings

async def analyze_current_data():
    """Analyze current data quality in both services"""
    print("🔍 Analyzing current data quality...")
    
    es_service = get_elasticsearch_service()
    
    try:
        # Check main elasticsearch service
        await es_service.test_connection()
        
        # Get sample products
        search_body = {"query": {"match_all": {}}, "size": 5}
        response = await es_service.client.search(index=es_service.products_index, body=search_body)
        
        products = [hit["_source"] for hit in response["hits"]["hits"]]
        
        print(f"\n📊 Main Elasticsearch Service:")
        print(f"   Total products: {response['hits']['total']['value']}")
        
        if products:
            sample_product = products[0]
            print(f"\n📄 Sample product structure:")
            print(f"   Name: {sample_product.get('name', 'N/A')}")
            print(f"   Category: {sample_product.get('category', 'N/A')}")
            print(f"   Description: {sample_product.get('description', 'MISSING')[:100]}...")
            print(f"   Features: {sample_product.get('features', 'MISSING')[:100]}...")
            print(f"   Use cases: {sample_product.get('use_cases', 'MISSING')[:100]}...")
            print(f"   Tags: {sample_product.get('tags', 'MISSING')}")
            print(f"   Search text: {sample_product.get('search_text', 'MISSING')[:100]}...")
            
            # Check content richness
            rich_fields = ['description', 'features', 'use_cases', 'tags']
            missing_fields = [field for field in rich_fields if not sample_product.get(field)]
            
            if missing_fields:
                print(f"   ⚠️ Missing fields: {missing_fields}")
            else:
                print(f"   ✅ All rich content fields present")
        
        return {
            "main_service_healthy": True,
            "total_products": response['hits']['total']['value'],
            "sample_product": sample_product if products else None,
            "has_rich_content": not missing_fields if products else False
        }
        
    except Exception as e:
        print(f"❌ Error analyzing main service: {e}")
        return {"main_service_healthy": False, "error": str(e)}

async def analyze_vector_service():
    """Analyze vector service data quality"""
    print("\n🧠 Analyzing vector service...")
    
    try:
        # Initialize vector service with dummy credentials for testing
        vector_service = get_elasticsearch_vector_service(
            azure_embedding_endpoint=settings.azure_openai_endpoint,
            azure_embedding_key=settings.azure_openai_key
        )
        
        await vector_service.test_connection()
        
        # Check vector index
        try:
            response = await vector_service.client.search(
                index=vector_service.products_index, 
                body={"query": {"match_all": {}}, "size": 5}
            )
            
            vector_products = [hit["_source"] for hit in response["hits"]["hits"]]
            
            print(f"📊 Vector Service:")
            print(f"   Total vector products: {response['hits']['total']['value']}")
            
            if vector_products:
                sample_vector_product = vector_products[0]
                print(f"\n📄 Sample vector product:")
                print(f"   Name: {sample_vector_product.get('name', 'N/A')}")
                print(f"   Searchable content: {sample_vector_product.get('searchable_content', 'MISSING')[:200]}...")
                print(f"   Has vector: {'content_vector' in sample_vector_product}")
                
                return {
                    "vector_service_healthy": True,
                    "total_vector_products": response['hits']['total']['value'],
                    "has_searchable_content": bool(sample_vector_product.get('searchable_content')),
                    "has_vectors": 'content_vector' in sample_vector_product
                }
            else:
                print("   ⚠️ No products in vector index")
                return {
                    "vector_service_healthy": True,
                    "total_vector_products": 0,
                    "has_searchable_content": False,
                    "has_vectors": False
                }
                
        except Exception as e:
            print(f"   ⚠️ Vector index not found or empty: {e}")
            return {
                "vector_service_healthy": True,
                "total_vector_products": 0,
                "vector_index_exists": False
            }
            
    except Exception as e:
        print(f"❌ Error analyzing vector service: {e}")
        return {"vector_service_healthy": False, "error": str(e)}

async def reprocess_main_data():
    """Reprocess data in main elasticsearch service with enrichment"""
    print("\n🔄 Reprocessing main elasticsearch data with enrichment...")
    
    es_service = get_elasticsearch_service()
    
    try:
        # Force reload data with new enrichment
        await es_service.reindex_all_data(force_replace=True)
        
        # Wait for indexing to complete
        await asyncio.sleep(2)
        
        # Verify enrichment
        search_body = {"query": {"match_all": {}}, "size": 3}
        response = await es_service.client.search(index=es_service.products_index, body=search_body)
        
        enriched_products = [hit["_source"] for hit in response["hits"]["hits"]]
        
        print(f"✅ Reprocessed {response['hits']['total']['value']} products")
        
        if enriched_products:
            sample = enriched_products[0]
            print(f"\n📄 Sample enriched product:")
            print(f"   Name: {sample.get('name', 'N/A')}")
            print(f"   Description: {sample.get('description', 'MISSING')[:100]}...")
            print(f"   Features: {sample.get('features', 'MISSING')[:100]}...")
            print(f"   Use cases: {sample.get('use_cases', 'MISSING')[:100]}...")
        
        return {"success": True, "products_processed": response['hits']['total']['value']}
        
    except Exception as e:
        print(f"❌ Error reprocessing data: {e}")
        return {"success": False, "error": str(e)}

async def sync_vector_index():
    """Sync vector index with enriched data from main service"""
    print("\n🔄 Syncing vector index with enriched data...")
    
    try:
        vector_service = get_elasticsearch_vector_service(
            azure_embedding_endpoint=settings.azure_openai_endpoint,
            azure_embedding_key=settings.azure_openai_key
        )
        
        await vector_service.initialize()
        
        # Sync with main service
        result = await vector_service.sync_with_main_service()
        
        print(f"✅ Synced {result['synced_products']} products to vector index")
        
        return {"success": True, "synced_products": result['synced_products']}
        
    except Exception as e:
        print(f"❌ Error syncing vector index: {e}")
        return {"success": False, "error": str(e)}

async def test_vector_search():
    """Test vector search functionality"""
    print("\n🧪 Testing vector search functionality...")
    
    try:
        vector_service = get_elasticsearch_vector_service(
            azure_embedding_endpoint=settings.azure_openai_endpoint,
            azure_embedding_key=settings.azure_openai_key
        )
        
        # Test queries
        test_queries = [
            "high performance gaming workstation",
            "enterprise server for database hosting",
            "AMD processor for video editing",
            "storage solution for backup"
        ]
        
        for query in test_queries:
            print(f"\n🔍 Testing query: '{query}'")
            
            try:
                results = await vector_service.vector_search_products(
                    query=query,
                    size=3,
                    hybrid_weight=0.1
                )
                
                print(f"   Found {len(results)} results:")
                for i, result in enumerate(results[:3]):
                    score = result.get('_similarity_score', result.get('_score', 0))
                    print(f"     {i+1}. {result.get('name', 'Unknown')} (Score: {score:.3f})")
                
            except Exception as e:
                print(f"   ❌ Query failed: {e}")
        
        return {"success": True}
        
    except Exception as e:
        print(f"❌ Error testing vector search: {e}")
        return {"success": False, "error": str(e)}

async def main():
    """Main diagnostic and fix routine"""
    print("🚀 Starting vector search diagnostic and fix routine...\n")
    
    # Step 1: Analyze current state
    main_analysis = await analyze_current_data()
    vector_analysis = await analyze_vector_service()
    
    # Step 2: Determine what needs fixing
    needs_main_reprocessing = not main_analysis.get("has_rich_content", False)
    needs_vector_sync = (
        vector_analysis.get("total_vector_products", 0) == 0 or
        not vector_analysis.get("has_searchable_content", False)
    )
    
    print(f"\n📋 Diagnostic Summary:")
    print(f"   Main service healthy: {main_analysis.get('main_service_healthy', False)}")
    print(f"   Vector service healthy: {vector_analysis.get('vector_service_healthy', False)}")
    print(f"   Needs main reprocessing: {needs_main_reprocessing}")
    print(f"   Needs vector sync: {needs_vector_sync}")
    
    # Step 3: Apply fixes
    if needs_main_reprocessing:
        print(f"\n🔧 Applying fix: Reprocessing main data with enrichment...")
        await reprocess_main_data()
    
    if needs_vector_sync:
        print(f"\n🔧 Applying fix: Syncing vector index...")
        await sync_vector_index()
    
    # Step 4: Test functionality
    print(f"\n🧪 Testing vector search after fixes...")
    await test_vector_search()
    
    print(f"\n✅ Vector search diagnostic and fix routine complete!")

if __name__ == "__main__":
    asyncio.run(main()) 