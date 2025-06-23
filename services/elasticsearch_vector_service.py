import json
import logging
from typing import List, Dict, Any, Optional
from elasticsearch import AsyncElasticsearch
from pathlib import Path
from config import settings
import asyncio
from elasticsearch.exceptions import ConnectionError, RequestError
import aiohttp
import numpy as np

logger = logging.getLogger(__name__)

class ElasticsearchVectorService:
    """Enhanced Elasticsearch service with vector search capabilities"""
    
    def __init__(self, azure_embedding_endpoint: str, azure_embedding_key: str):
        self.client = AsyncElasticsearch(
            hosts=[settings.elasticsearch_url],
            verify_certs=False,
            ssl_show_warn=False,
            request_timeout=30,
            retry_on_timeout=True,
            max_retries=3
        )
        self.products_index = f"{settings.elasticsearch_index_products}_vector"
        self.solutions_index = f"{settings.elasticsearch_index_solutions}_vector"
        self.azure_embedding_endpoint = azure_embedding_endpoint
        self.azure_embedding_key = azure_embedding_key
        self.embedding_dimension = 3072  # text-embedding-3-large dimension
        
    async def initialize(self):
        """Initialize Elasticsearch with vector search capabilities"""
        try:
            await self.test_connection()
            await self.create_vector_indices()
            logger.info("Elasticsearch Vector Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch Vector Service: {e}")
            raise
    
    async def test_connection(self):
        """Test Elasticsearch connection"""
        try:
            info = await self.client.info()
            logger.info(f"Elasticsearch connected: {info.get('cluster_name', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {e}")
            return False
    
    async def create_vector_indices(self):
        """Create Elasticsearch indices with vector search mappings"""
        
        # Products index with vector mapping
        products_mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text", "analyzer": "standard"},
                    "category": {"type": "keyword"},
                    "subcategory": {"type": "keyword"},
                    "description": {"type": "text", "analyzer": "standard"},
                    "specifications": {"type": "object"},
                    "price": {"type": "float"},
                    "currency": {"type": "keyword"},
                    "availability": {"type": "boolean"},
                    "tags": {"type": "keyword"},
                    "features": {"type": "text", "analyzer": "standard"},
                    "use_cases": {"type": "text", "analyzer": "standard"},
                    "target_industries": {"type": "keyword"},
                    "compatibility": {"type": "text"},
                    "warranty": {"type": "text"},
                    "support_level": {"type": "keyword"},
                    "form_factor": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword"
                            }
                        }
                    },
                    # Vector fields
                    "content_vector": {
                        "type": "dense_vector",
                        "dims": self.embedding_dimension,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "searchable_content": {"type": "text", "analyzer": "standard"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.knn": True
            }
        }
        
        # Solutions index with vector mapping
        solutions_mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text", "analyzer": "standard"},
                    "description": {"type": "text", "analyzer": "standard"},
                    "use_case": {"type": "text", "analyzer": "standard"},
                    "industry": {"type": "keyword"},
                    "company_size": {"type": "keyword"},
                    "budget_range": {"type": "keyword"},
                    "components": {"type": "nested"},
                    "total_price": {"type": "float"},
                    "implementation_time": {"type": "text"},
                    "benefits": {"type": "text", "analyzer": "standard"},
                    "requirements": {"type": "text", "analyzer": "standard"},
                    # Vector fields
                    "content_vector": {
                        "type": "dense_vector",
                        "dims": self.embedding_dimension,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "searchable_content": {"type": "text", "analyzer": "standard"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.knn": True
            }
        }
        
        # Create products vector index
        try:
            exists = await self.client.indices.exists(index=self.products_index)
            if not exists:
                await self.client.indices.create(index=self.products_index, **products_mapping)
                logger.info(f"Created products vector index: {self.products_index}")
            else:
                logger.info(f"Products vector index already exists: {self.products_index}")
        except Exception as e:
            logger.warning(f"Products vector index creation issue: {e}")
        
        # Create solutions vector index
        try:
            exists = await self.client.indices.exists(index=self.solutions_index)
            if not exists:
                await self.client.indices.create(index=self.solutions_index, **solutions_mapping)
                logger.info(f"Created solutions vector index: {self.solutions_index}")
            else:
                logger.info(f"Solutions vector index already exists: {self.solutions_index}")
        except Exception as e:
            logger.warning(f"Solutions vector index creation issue: {e}")
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from Azure OpenAI"""
        try:
            headers = {
                "Content-Type": "application/json",
                "api-key": self.azure_embedding_key
            }
            
            data = {
                "input": texts,
                "model": "text-embedding-3-large"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.azure_embedding_endpoint}/openai/deployments/text-embedding-3-large/embeddings",
                    headers=headers,
                    json=data,
                    params={"api-version": "2023-05-15"}
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200:
                        logger.error(f"Embedding API error: {result}")
                        raise Exception(f"Failed to get embeddings: {result}")
                    
                    return [item["embedding"] for item in result["data"]]
                    
        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            raise
    
    def _create_searchable_content(self, item: Dict[str, Any], item_type: str = "product") -> str:
        """Create searchable text content for embedding"""
        text_parts = []
        
        if item_type == "product":
            # Product-specific content
            if item.get("name"):
                text_parts.append(f"Product: {item['name']}")
            if item.get("category"):
                text_parts.append(f"Category: {item['category']}")
            if item.get("subcategory"):
                text_parts.append(f"Subcategory: {item['subcategory']}")
            if item.get("description"):
                text_parts.append(f"Description: {item['description']}")
            if item.get("features"):
                text_parts.append(f"Features: {item['features']}")
            if item.get("use_cases"):
                text_parts.append(f"Use cases: {item['use_cases']}")
            if item.get("tags"):
                tags = item["tags"] if isinstance(item["tags"], list) else [item["tags"]]
                text_parts.append(f"Tags: {', '.join(tags)}")
            if item.get("target_industries"):
                industries = item["target_industries"] if isinstance(item["target_industries"], list) else [item["target_industries"]]
                text_parts.append(f"Industries: {', '.join(industries)}")
            
            # Add specifications if they exist
            specs = item.get("specifications", {})
            if specs and isinstance(specs, dict):
                spec_texts = []
                for key, value in specs.items():
                    if value:
                        spec_texts.append(f"{key}: {value}")
                if spec_texts:
                    text_parts.append(f"Specifications: {', '.join(spec_texts)}")
            
            # Add search_text if it exists (from main elasticsearch service)
            if item.get("search_text"):
                text_parts.append(f"Additional info: {item['search_text']}")
                
        else:  # solution
            if item.get("name"):
                text_parts.append(f"Solution: {item['name']}")
            if item.get("description"):
                text_parts.append(f"Description: {item['description']}")
            if item.get("use_case"):
                text_parts.append(f"Use case: {item['use_case']}")
            if item.get("industry"):
                industries = item["industry"] if isinstance(item["industry"], list) else [item["industry"]]
                text_parts.append(f"Industries: {', '.join(industries)}")
            if item.get("benefits"):
                text_parts.append(f"Benefits: {item['benefits']}")
            if item.get("requirements"):
                text_parts.append(f"Requirements: {item['requirements']}")
        
        return " | ".join(text_parts)
    
    async def index_product(self, product: Dict[str, Any]):
        """Index a product with vector embedding"""
        try:
            # Generate searchable content
            searchable_content = self._create_searchable_content(product, "product")
            
            # Get embedding
            embeddings = await self.get_embeddings([searchable_content])
            content_vector = embeddings[0]
            
            # Prepare document
            doc = product.copy()
            doc["content_vector"] = content_vector
            doc["searchable_content"] = searchable_content
            
            # Ensure ID exists
            if not doc.get("id"):
                doc["id"] = f"product_{hash(str(product))}"
            
            # Index document
            await self.client.index(
                index=self.products_index,
                id=doc["id"],
                document=doc
            )
            
            logger.debug(f"Indexed product with vector: {doc.get('name', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to index product: {e}")
            raise
    
    async def index_solution(self, solution: Dict[str, Any]):
        """Index a solution with vector embedding"""
        try:
            # Generate searchable content
            searchable_content = self._create_searchable_content(solution, "solution")
            
            # Get embedding
            embeddings = await self.get_embeddings([searchable_content])
            content_vector = embeddings[0]
            
            # Prepare document
            doc = solution.copy()
            doc["content_vector"] = content_vector
            doc["searchable_content"] = searchable_content
            
            # Ensure ID exists
            if not doc.get("id"):
                doc["id"] = f"solution_{hash(str(solution))}"
            
            # Index document
            await self.client.index(
                index=self.solutions_index,
                id=doc["id"],
                document=doc
            )
            
            logger.debug(f"Indexed solution with vector: {doc.get('name', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to index solution: {e}")
            raise
    
    async def vector_search_products(
        self, 
        query: str, 
        size: int = 10,
        filters: Optional[Dict] = None,
        hybrid_weight: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Perform vector search on products with optional hybrid scoring"""
        try:
            # Get query embedding
            query_embeddings = await self.get_embeddings([query])
            query_vector = query_embeddings[0]
            
            # Build the search query
            search_query = {
                "size": size,
                "query": {
                    "bool": {
                        "should": []
                    }
                },
                "_source": {"excludes": ["content_vector"]}  # Exclude vector from response
            }
            
            # Add vector similarity search
            knn_query = {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'content_vector') + 1.0",
                        "params": {"query_vector": query_vector}
                    }
                }
            }
            
            # Add text search for hybrid approach
            text_query = {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "description^2", "features", "use_cases", "searchable_content"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            }
            
            if hybrid_weight > 0:
                # Hybrid search
                search_query["query"]["bool"]["should"].extend([
                    {"constant_score": {"filter": knn_query, "boost": 1.0 - hybrid_weight}},
                    {"constant_score": {"filter": text_query, "boost": hybrid_weight}}
                ])
            else:
                # Pure vector search
                search_query["query"] = knn_query
            
            # Add filters if provided
            if filters:
                search_query["query"]["bool"]["filter"] = []
                for field, value in filters.items():
                    if isinstance(value, list):
                        search_query["query"]["bool"]["filter"].append({"terms": {field: value}})
                    else:
                        search_query["query"]["bool"]["filter"].append({"term": {field: value}})
            
            # Execute search
            response = await self.client.search(index=self.products_index, body=search_query)
            
            # Process results
            products = []
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                product["_score"] = hit["_score"]
                product["_similarity_score"] = hit["_score"]  # For compatibility
                products.append(product)
            
            logger.info(f"Vector search returned {len(products)} products for query: '{query}'")
            return products
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def vector_search_solutions(
        self, 
        query: str, 
        size: int = 5,
        filters: Optional[Dict] = None,
        hybrid_weight: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Perform vector search on solutions with optional hybrid scoring"""
        try:
            # Get query embedding
            query_embeddings = await self.get_embeddings([query])
            query_vector = query_embeddings[0]
            
            # Build the search query
            search_query = {
                "size": size,
                "query": {
                    "bool": {
                        "should": []
                    }
                },
                "_source": {"excludes": ["content_vector"]}
            }
            
            # Add vector similarity search
            knn_query = {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'content_vector') + 1.0",
                        "params": {"query_vector": query_vector}
                    }
                }
            }
            
            # Add text search for hybrid approach
            text_query = {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "description^2", "use_case", "benefits", "searchable_content"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            }
            
            if hybrid_weight > 0:
                # Hybrid search
                search_query["query"]["bool"]["should"].extend([
                    {"constant_score": {"filter": knn_query, "boost": 1.0 - hybrid_weight}},
                    {"constant_score": {"filter": text_query, "boost": hybrid_weight}}
                ])
            else:
                # Pure vector search
                search_query["query"] = knn_query
            
            # Add filters if provided
            if filters:
                search_query["query"]["bool"]["filter"] = []
                for field, value in filters.items():
                    if isinstance(value, list):
                        search_query["query"]["bool"]["filter"].append({"terms": {field: value}})
                    else:
                        search_query["query"]["bool"]["filter"].append({"term": {field: value}})
            
            # Execute search
            response = await self.client.search(index=self.solutions_index, body=search_query)
            
            # Process results
            solutions = []
            for hit in response["hits"]["hits"]:
                solution = hit["_source"]
                solution["_score"] = hit["_score"]
                solution["_similarity_score"] = hit["_score"]
                solutions.append(solution)
            
            logger.info(f"Vector search returned {len(solutions)} solutions for query: '{query}'")
            return solutions
            
        except Exception as e:
            logger.error(f"Vector solution search failed: {e}")
            return []
    
    async def load_data_from_json(self, max_per_file: int = 50):
        """Load data from JSON files with vector embeddings"""
        try:
            logger.info(f"Loading data into Elasticsearch with vector embeddings...")
            
            data_dir = settings.data_dir
            total_products_indexed = 0
            total_solutions_indexed = 0
            files_processed = 0
            
            # Process all JSON files
            for json_file in data_dir.glob("*.json"):
                try:
                    logger.info(f"Processing file: {json_file.name}")
                    
                    # Extract category from filename
                    category_from_file = self._extract_category_from_filename(json_file.name)
                    
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    file_products = 0
                    file_solutions = 0
                    
                    # Handle different JSON structures
                    if isinstance(data, list):
                        items = data[:max_per_file]
                        for item in items:
                            if self._is_product_data(item):
                                # Process through main elasticsearch service first for enrichment
                                enriched_product = await self._enrich_product_data_with_category(item, category_from_file)
                                await self.index_product(enriched_product)
                                file_products += 1
                            elif self._is_solution_data(item):
                                await self.index_solution(item)
                                file_solutions += 1
                    
                    elif isinstance(data, dict):
                        if 'products' in data:
                            products = data['products'][:max_per_file]
                            for product in products:
                                if self._is_valid_product(product):
                                    # Process through main elasticsearch service first for enrichment
                                    enriched_product = await self._enrich_product_data_with_category(product, category_from_file)
                                    await self.index_product(enriched_product)
                                    file_products += 1
                        
                        if 'solutions' in data:
                            solutions = data['solutions'][:max_per_file]
                            for solution in solutions:
                                if self._is_valid_solution(solution):
                                    await self.index_solution(solution)
                                    file_solutions += 1
                    
                    total_products_indexed += file_products
                    total_solutions_indexed += file_solutions
                    files_processed += 1
                    
                    logger.info(f"✅ {json_file.name}: {file_products} products, {file_solutions} solutions")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to process {json_file.name}: {e}")
                    continue
            
            # Refresh indices - only if they exist and have data
            try:
                if total_products_indexed > 0:
                    await self.client.indices.refresh(index=self.products_index)
                    logger.info(f"✅ Refreshed products index with {total_products_indexed} documents")
            except Exception as e:
                logger.warning(f"Failed to refresh products index: {e}")
            
            try:
                if total_solutions_indexed > 0:
                    await self.client.indices.refresh(index=self.solutions_index)
                    logger.info(f"✅ Refreshed solutions index with {total_solutions_indexed} documents")
                else:
                    logger.info(f"⚠️ No solutions to index - skipping solutions index refresh")
            except Exception as e:
                logger.warning(f"Failed to refresh solutions index (likely doesn't exist): {e}")
            
            logger.info(f"🎯 Vector indexing complete:")
            logger.info(f"   Files processed: {files_processed}")
            logger.info(f"   Products indexed: {total_products_indexed}")
            logger.info(f"   Solutions indexed: {total_solutions_indexed}")
            
            return {
                "files_processed": files_processed,
                "products_indexed": total_products_indexed,
                "solutions_indexed": total_solutions_indexed
            }
            
        except Exception as e:
            logger.error(f"Failed to load data with vectors: {e}")
            raise
    
    def _extract_category_from_filename(self, filename: str) -> str:
        """Extract category from filename more intelligently"""
        # Remove .json extension and convert to lowercase
        name = filename.replace('.json', '').lower()
        
        # Map filename patterns to categories
        if any(term in name for term in ['internal-hard-drive', 'external-hard-drive', 'storage']):
            return 'storage'
        elif any(term in name for term in ['cpu', 'processor']):
            return 'cpu'
        elif any(term in name for term in ['video-card', 'graphics']):
            return 'graphics'
        elif any(term in name for term in ['motherboard']):
            return 'motherboard'
        elif any(term in name for term in ['memory', 'ram']):
            return 'memory'
        elif any(term in name for term in ['monitor', 'display']):
            return 'monitor'
        elif any(term in name for term in ['keyboard', 'mouse', 'headphone', 'speaker']):
            return 'peripheral'
        elif any(term in name for term in ['case', 'chassis']):
            return 'case'
        elif any(term in name for term in ['power-supply', 'psu']):
            return 'power'
        elif any(term in name for term in ['cpu-cooler', 'fan', 'thermal']):
            return 'cooling'
        elif any(term in name for term in ['wireless-network-card', 'wired-network-card']):
            return 'networking'
        elif any(term in name for term in ['sound-card', 'audio']):
            return 'audio'
        elif any(term in name for term in ['optical-drive']):
            return 'optical'
        elif any(term in name for term in ['webcam', 'camera']):
            return 'peripheral'
        elif any(term in name for term in ['ups', 'uninterruptible']):
            return 'power'
        elif any(term in name for term in ['os', 'operating-system']):
            return 'software'
        
        return 'general'
    
    def _is_product_data(self, item: Dict[str, Any]) -> bool:
        """Check if item is product data - improved validation"""
        # Check for required fields that indicate a product
        required_fields = ['name']
        if not all(field in item for field in required_fields):
            return False
        
        # Check for product-specific indicators
        product_indicators = [
            'price', 'capacity', 'type', 'form_factor', 'interface', 
            'cache', 'specifications', 'category'
        ]
        
        # Must have at least 2 product indicators
        indicator_count = sum(1 for indicator in product_indicators if indicator in item)
        return indicator_count >= 2
    
    def _is_solution_data(self, item: Dict[str, Any]) -> bool:
        """Check if item is solution data - improved validation"""
        # Check for required fields that indicate a solution
        required_fields = ['name']
        if not all(field in item for field in required_fields):
            return False
        
        # Check for solution-specific indicators
        solution_indicators = [
            'use_case', 'industry', 'components', 'total_price', 
            'implementation_time', 'benefits', 'requirements'
        ]
        
        # Must have at least 2 solution indicators
        indicator_count = sum(1 for indicator in solution_indicators if indicator in item)
        return indicator_count >= 2
    
    def _is_valid_product(self, product: Dict[str, Any]) -> bool:
        """Validate product data - improved validation"""
        # Must have a name
        if not product.get('name'):
            return False
        
        # Must have at least one of: price, capacity, type, specifications
        core_fields = ['price', 'capacity', 'type', 'specifications']
        if not any(field in product for field in core_fields):
            return False
        
        return True
    
    def _is_valid_solution(self, solution: Dict[str, Any]) -> bool:
        """Validate solution data - improved validation"""
        # Must have a name and description
        if not solution.get('name') or not solution.get('description'):
            return False
        
        return True

    async def _enrich_product_data_with_category(self, raw_product: Dict[str, Any], category: str) -> Dict[str, Any]:
        """Enrich raw product data with explicit category"""
        from services.elasticsearch_service import get_elasticsearch_service
        
        # Get the main elasticsearch service
        es_service = get_elasticsearch_service()
        
        # Set the category explicitly
        raw_product['category'] = category
        
        # Use the main service's data processing logic
        enriched_product = es_service._process_product_data(raw_product.copy(), category)
        
        return enriched_product
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about vector indices"""
        try:
            # Get products stats
            products_count = 0
            try:
                products_stats = await self.client.count(index=self.products_index)
                products_count = products_stats["count"]
            except Exception as e:
                logger.warning(f"Failed to get products stats: {e}")
            
            # Get solutions stats - handle missing index gracefully
            solutions_count = 0
            try:
                solutions_stats = await self.client.count(index=self.solutions_index)
                solutions_count = solutions_stats["count"]
            except Exception as e:
                logger.debug(f"Solutions index not found or empty: {e}")
            
            return {
                "products_count": products_count,
                "solutions_count": solutions_count,
                "status": "healthy",
                "service": "elasticsearch_vector",
                "initialized": True
            }
        except Exception as e:
            logger.error(f"Failed to get vector service stats: {e}")
            return {
                "products_count": 0,
                "solutions_count": 0,
                "status": "error",
                "error": str(e),
                "initialized": False
            }
    
    async def close(self):
        """Close Elasticsearch connection"""
        await self.client.close()

    async def sync_with_main_service(self):
        """Sync vector index with enriched data from main elasticsearch service"""
        try:
            from services.elasticsearch_service import get_elasticsearch_service
            
            logger.info("🔄 Syncing vector index with main elasticsearch service...")
            
            es_service = get_elasticsearch_service()
            
            # Get all products from main service
            search_body = {"query": {"match_all": {}}, "size": 1000}
            response = await es_service.client.search(index=es_service.products_index, body=search_body)
            
            products = [hit["_source"] for hit in response["hits"]["hits"]]
            
            logger.info(f"Found {len(products)} products in main service to sync")
            
            # Index each product with vector embeddings
            synced_count = 0
            for product in products:
                try:
                    await self.index_product(product)
                    synced_count += 1
                except Exception as e:
                    logger.warning(f"Failed to sync product {product.get('id', 'unknown')}: {e}")
            
            # Refresh vector index
            await self.client.indices.refresh(index=self.products_index)
            
            logger.info(f"✅ Successfully synced {synced_count} products to vector index")
            
            return {"synced_products": synced_count}
            
        except Exception as e:
            logger.error(f"Failed to sync with main service: {e}")
            raise

# Global instance
_elasticsearch_vector_service = None

def get_elasticsearch_vector_service(azure_embedding_endpoint: str, azure_embedding_key: str) -> ElasticsearchVectorService:
    """Get singleton Elasticsearch vector service instance"""
    global _elasticsearch_vector_service
    if _elasticsearch_vector_service is None:
        _elasticsearch_vector_service = ElasticsearchVectorService(azure_embedding_endpoint, azure_embedding_key)
    return _elasticsearch_vector_service 