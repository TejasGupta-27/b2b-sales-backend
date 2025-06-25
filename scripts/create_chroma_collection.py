import json
from pathlib import Path
from models.catalog import Product, ProductCategory
from services.chroma_service import ChromaDBService
from config import settings
import asyncio

def map_raw_product_to_model(raw):
    features = []
    for k, v in raw.items():
        if k not in {"name", "price"}:
            features.append(f"{k.replace('_', ' ').title()}: {v}")

    return {
        "id": raw.get("id", raw.get("name", "").lower().replace(" ", "_")),  # Fallback ID if missing
        "name": raw.get("name", ""),
        "category": ProductCategory.SOFTWARE,  # You can improve inference if needed
        "description": f"{raw.get('name', '')} with specs: {', '.join(features)}.",
        "features": features,
        "benefits": ["High quality", "Reliable", "Popular choice"],
        "pricing_tiers": [{"tier": "Standard", "price": raw.get("price", 0)}],
        "implementation_time": "Immediate",
        "support_level": "Standard",
        "ideal_for": ["general", "consumer", "performance"],
    }

async def main():
    chroma_service = ChromaDBService(
        azure_embedding_endpoint=settings.azure_embedding_endpoint,
        azure_embedding_key=settings.azure_embedding_api_key
    )
    await chroma_service.initialize()

    data_dir = settings.data_dir
    products_indexed = 0

    for json_file in data_dir.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and "products" in data:
            items = data["products"]
        else:
            items = [data]

        for item in items:
            try:
                model_ready = map_raw_product_to_model(item)  # ✅ MAPPING APPLIED
                product = Product(**model_ready)
                await chroma_service.index_product(product.dict())
                products_indexed += 1
            except Exception as e:
                print(f"Skipping invalid product: {e}")

    print(f"✅ Inserted {products_indexed} products into ChromaDB 'products' collection.")

if __name__ == "__main__":
    asyncio.run(main())
