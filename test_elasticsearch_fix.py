import asyncio
import logging
from services.elasticsearch_service import ElasticsearchService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_elasticsearch_service():
    """Test the fixed Elasticsearch service"""
    
    print("🧪 Testing Elasticsearch service fixes...")
    
    try:
        # Get service instance
        es_service = ElasticsearchService()
        
        # Test basic connection
        print("🔍 Testing connection...")
        connected = await es_service.test_connection()
        print(f"Connection test: {'✅ Success' if connected else '❌ Failed'}")
        
        # Test health check
        print("🔍 Testing health check...")
        healthy = await es_service.check_health()
        print(f"Health check: {'✅ Healthy' if healthy else '❌ Unhealthy'}")
        
        # Test count operations (the main problematic area)
        print("🔍 Testing count operations...")
        products_count = await es_service._safe_count_with_retries("products")
        solutions_count = await es_service._safe_count_with_retries("solutions")
        print(f"Products count: {products_count}")
        print(f"Solutions count: {solutions_count}")
        
        # Test search operations
        print("🔍 Testing search operations...")
        random_products = await es_service.get_random_products(5)
        print(f"Random products retrieved: {len(random_products)}")
        
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        try:
            await es_service.close()
            print("🔄 Elasticsearch connection closed")
        except Exception as e:
            print(f"⚠️ Error closing connection: {e}")

if __name__ == "__main__":
    asyncio.run(test_elasticsearch_service()) 