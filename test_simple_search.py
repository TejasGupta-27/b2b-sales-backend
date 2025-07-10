import asyncio
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from config import settings

async def test_simple_search():
    try:
        service = get_elasticsearch_vector_service(
            settings.azure_embedding_endpoint, 
            settings.azure_embedding_api_key
        )
        await service.initialize()
        
        print("🧪 Testing fixed vector search...")
        
        # Test 1: Search for "Intel i9" specifically
        print("\n1. Searching for 'Intel i9' in CPU category:")
        results1 = await service.vector_search_products(
            query="Intel i9",
            size=5,
            categories=["cpu"]
        )
        print(f"   Found {len(results1)} products:")
        for i, product in enumerate(results1):
            name = product.get('name', 'Unknown')
            print(f"   {i+1}. {name}")
        
        # Test 2: Search for "AMD Ryzen" specifically  
        print("\n2. Searching for 'AMD Ryzen' in CPU category:")
        results2 = await service.vector_search_products(
            query="AMD Ryzen",
            size=5,
            categories=["cpu"]
        )
        print(f"   Found {len(results2)} products:")
        for i, product in enumerate(results2):
            name = product.get('name', 'Unknown')
            print(f"   {i+1}. {name}")
            
        # Test 3: Search for "gaming" more generally
        print("\n3. Searching for 'gaming' in CPU category:")
        results3 = await service.vector_search_products(
            query="gaming",
            size=5,
            categories=["cpu"]
        )
        print(f"   Found {len(results3)} products:")
        for i, product in enumerate(results3):
            name = product.get('name', 'Unknown')
            print(f"   {i+1}. {name}")
        
        await service.close()
        print("\n✅ Test completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_search()) 