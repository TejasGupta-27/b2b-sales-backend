import asyncio
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from config import settings

async def test_fixed_search():
    try:
        service = get_elasticsearch_vector_service(
            settings.azure_embedding_endpoint, 
            settings.azure_embedding_api_key
        )
        await service.initialize()
        
        print("🧪 Testing Fixed Elasticsearch Query Generation...")
        
        # Test the query generation directly
        print("\n1. Testing AI Dynamic Query Generation for 'i9 CPU':")
        requirements = {
            'semantic_query': 'i9 CPU',
            'technical_requirements': ['i9 CPU'],
            'industry': 'Technology'
        }
        
        dynamic_query = await service.generate_dynamic_query(requirements, "keyword_only")
        print(f"   Generated Query: {dynamic_query.keyword_query}")
        print(f"   Categories: {dynamic_query.category_filters}")
        print(f"   Confidence: {dynamic_query.confidence:.1%}")
        print(f"   Reasoning: {dynamic_query.reasoning}")
        
        # Test the actual Elasticsearch search
        print("\n2. Testing AI-Enhanced Elasticsearch Search:")
        es_results = await service.elasticsearch_search_with_ai_query(requirements, size=10)
        print(f"   Found {len(es_results)} products:")
        for i, product in enumerate(es_results[:5]):
            name = product.get('name', 'Unknown')
            print(f"   {i+1}. {name}")
        
        await service.close()
        print("\n✅ Test completed successfully")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fixed_search()) 