#!/usr/bin/env python3
"""
Elasticsearch Data Management Script
Use this to check, clear, or reload Elasticsearch data
"""

import asyncio
import argparse
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.elasticsearch_service import ElasticsearchService
from config import settings


async def check_data():
    """Check current Elasticsearch data"""
    es = ElasticsearchService()
    try:
        await es.test_connection()
        
        products_count = await es._safe_count_with_retries(es.products_index)
        solutions_count = await es._safe_count_with_retries(es.solutions_index)
        
        print(f"📊 Current Elasticsearch Data:")
        print(f"   Products: {products_count}")
        print(f"   Solutions: {solutions_count}")
        
        if products_count > 0 or solutions_count > 0:
            print("✅ Data exists - container restarts should skip reloading")
        else:
            print("📝 No data found - next startup will load initial data")
            
    except Exception as e:
        print(f"❌ Error checking data: {e}")
    finally:
        await es.close()


async def clear_data():
    """Clear all Elasticsearch data"""
    es = ElasticsearchService()
    try:
        await es.test_connection()
        
        print("🗑️ Clearing Elasticsearch data...")
        await es.client.indices.delete(index=es.products_index, ignore=[404])
        await es.client.indices.delete(index=es.solutions_index, ignore=[404])
        
        print("✅ Data cleared successfully")
        print("📝 Next container startup will reload all data")
        
    except Exception as e:
        print(f"❌ Error clearing data: {e}")
    finally:
        await es.close()


async def reload_data():
    """Force reload all data"""
    es = ElasticsearchService()
    try:
        await es.test_connection()
        
        print("🔄 Force reloading all data...")
        await es.reindex_all_data(force_replace=True)
        
        # Check final counts
        products_count = await es._safe_count_with_retries(es.products_index)
        solutions_count = await es._safe_count_with_retries(es.solutions_index)
        
        print(f"✅ Data reloaded successfully:")
        print(f"   Products: {products_count}")
        print(f"   Solutions: {solutions_count}")
        
    except Exception as e:
        print(f"❌ Error reloading data: {e}")
    finally:
        await es.close()


def main():
    parser = argparse.ArgumentParser(description="Manage Elasticsearch data")
    parser.add_argument('action', choices=['check', 'clear', 'reload'], 
                      help='Action to perform')
    
    args = parser.parse_args()
    
    if args.action == 'check':
        asyncio.run(check_data())
    elif args.action == 'clear':
        confirm = input("⚠️ Are you sure you want to clear all data? (y/N): ")
        if confirm.lower() == 'y':
            asyncio.run(clear_data())
        else:
            print("❌ Cancelled")
    elif args.action == 'reload':
        confirm = input("⚠️ Are you sure you want to reload all data? (y/N): ")
        if confirm.lower() == 'y':
            asyncio.run(reload_data())
        else:
            print("❌ Cancelled")


if __name__ == "__main__":
    main() 