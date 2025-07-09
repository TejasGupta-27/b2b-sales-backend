import asyncio
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from config import settings

async def test_query_filtering():
    try:
        service = get_elasticsearch_vector_service(
            settings.azure_embedding_endpoint, 
            settings.azure_embedding_api_key
        )
        await service.initialize()
        
        # Test 1: Search for "i9 CPU" in CPU category
        print("🧪 Test 1: Searching for 'i9 CPU' in CPU category...")
        results1 = await service.vector_search_products(
            query="i9 CPU",
            size=10,
            categories=["cpu"]
        )
        print(f"Results: {len(results1)} products")
        for i, product in enumerate(results1[:5]):
            print(f"  {i+1}. {product.get('name', 'Unknown')} (Category: {product.get('category', 'unknown')})")
        
        # Test 2: Search for "CPU" in CPU category (more general)
        print("\n🧪 Test 2: Searching for 'CPU' in CPU category...")
        results2 = await service.vector_search_products(
            query="CPU",
            size=10,
            categories=["cpu"]
        )
        print(f"Results: {len(results2)} products")
        for i, product in enumerate(results2[:5]):
            print(f"  {i+1}. {product.get('name', 'Unknown')} (Category: {product.get('category', 'unknown')})")
        
        # Test 3: Search for "Intel" in CPU category
        print("\n🧪 Test 3: Searching for 'Intel' in CPU category...")
        results3 = await service.vector_search_products(
            query="Intel",
            size=10,
            categories=["cpu"]
        )
        print(f"Results: {len(results3)} products")
        for i, product in enumerate(results3[:5]):
            print(f"  {i+1}. {product.get('name', 'Unknown')} (Category: {product.get('category', 'unknown')})")
        
        await service.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_query_filtering()) 