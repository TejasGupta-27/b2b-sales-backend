import asyncio
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from config import settings

async def test_collection_stats():
    try:
        service = get_elasticsearch_vector_service(
            settings.azure_embedding_endpoint, 
            settings.azure_embedding_api_key
        )
        await service.initialize()
        stats = await service.get_collection_stats()
        print('Collection stats:', stats)
        await service.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_collection_stats()) 