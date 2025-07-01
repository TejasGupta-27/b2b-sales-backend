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
import re
import os
from ai_services.base import AIMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Add a field mapping for each product category
FIELD_MAP = {
    "cpu": ["name", "core_count", "core_clock", "boost_clock", "tdp", "graphics", "smt"],
    "monitor": ["name", "screen_size", "resolution", "refresh_rate", "response_time", "panel_type", "aspect_ratio"],
    "memory": ["name", "speed", "modules", "price_per_gb", "color", "first_word_latency", "cas_latency"],
    "motherboard": ["name", "socket", "form_factor", "max_memory", "memory_slots", "color"],
    "case": ["name", "type", "color", "side_panel", "external_volume", "internal_35_bays"],
    "power-supply": ["name", "price", "type", "efficiency", "wattage", "modular", "color"],
    "case-accessory": ["name", "type", "form_factor"],
    "case-fan": ["name", "size", "color", "rpm", "airflow", "noise_level", "pwm"],
    "cpu-cooler": ["name", "rpm", "noise_level", "color", "size"],
    "external-hard-drive": ["name", "type", "interface", "capacity", "price_per_gb", "color"],
    "fan-controller": ["name", "channels", "channel_wattage", "pwm", "form_factor", "color"],
    "headphones": ["name", "type", "frequency_response", "microphone", "wireless", "enclosure_type", "color"],
    "internal-hard-drive": ["name", "capacity", "price_per_gb", "type", "cache", "form_factor", "interface"],
    "keyboard": ["name", "style", "switches", "backlit", "tenkeyless", "connection_type", "color"],
    "mouse": ["name", "tracking_method", "connection_type", "max_dpi", "hand_orientation", "color"],
    "optical-drive": ["name", "bd", "dvd", "cd", "bd_write", "dvd_write", "cd_write"],
    "os": ["name", "mode", "max_memory"],
    "sound-card": ["name", "channels", "digital_audio", "snr", "sample_rate", "chipset", "interface"],
    "speakers": ["name", "configuration", "wattage", "frequency_response", "color"],
    "thermal-paste": ["name", "amount"],
    "ups": ["name", "capacity_w", "capacity_va"],
    "video-card": ["name", "price", "chipset", "memory", "core_clock", "boost_clock", "color", "length"],
    "webcam": ["name", "price", "resolutions", "connection", "focus_type", "os", "fov"],
    "wired-network-card": ["name", "price", "interface", "color"],
    "wireless-network-card": ["name", "price", "protocol", "interface", "color"],
   
}

# Category to index mapping for per-category indices
CATEGORY_INDEX_MAP = {
    "cpu": "cpu_vector",
    "video-card": "gpu_vector", 
    "memory": "memory_vector",
    "monitor": "monitor_vector",
    "motherboard": "motherboard_vector",
    "power-supply": "power_vector",
    "case": "case_vector",
    "case-accessory": "case_accessory_vector",
    "case-fan": "case_fan_vector",
    "cpu-cooler": "cpu_cooler_vector",
    "external-hard-drive": "external_storage_vector",
    "internal-hard-drive": "internal_storage_vector",
    "fan-controller": "fan_controller_vector",
    "headphones": "headphones_vector",
    "keyboard": "keyboard_vector",
    "mouse": "mouse_vector",
    "optical-drive": "optical_drive_vector",
    "os": "os_vector",
    "sound-card": "sound_card_vector",
    "speakers": "speakers_vector",
    "thermal-paste": "thermal_paste_vector",
    "ups": "ups_vector",
    "webcam": "webcam_vector",
    "wired-network-card": "network_wired_vector",
    "wireless-network-card": "network_wireless_vector",
}

# Default index for uncategorized products
DEFAULT_PRODUCTS_INDEX = "other_products_vector"

class CategoryAnalysis(BaseModel):
    """Pydantic model for intelligent category analysis"""
    relevant_categories: List[str] = Field(
        description="List of most relevant product categories (max 5)",
        max_items=5
    )
    primary_use_case: str = Field(
        description="Primary use case or application scenario"
    )
    technical_focus: str = Field(
        description="Main technical focus area (gaming, workstation, storage, office, etc.)"
    )
    confidence: float = Field(
        description="Confidence in category selection (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )
    reasoning: str = Field(
        description="Brief explanation for category selection"
    )
    alternative_categories: List[str] = Field(
        description="Alternative categories to consider if primary search fails",
        default_factory=list
    )

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
        # Remove single index approach - we'll use per-category indices
        self.solutions_index = f"{settings.elasticsearch_index_solutions}_vector"
        self.azure_embedding_endpoint = azure_embedding_endpoint
        self.azure_embedding_key = azure_embedding_key
        self.embedding_dimension = 3072  # text-embedding-3-large dimension
        
        # Add LLM provider for intelligent category detection
        self.llm_provider = None
        
    async def initialize(self):
        """Initialize Elasticsearch with vector search capabilities"""
        try:
            # Wait for Elasticsearch to be healthy before proceeding
            await self._wait_for_elasticsearch_ready()
            await self.test_connection()
            await self.create_vector_indices()
            logger.info("Elasticsearch Vector Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch Vector Service: {e}")
            raise
    
    async def _wait_for_elasticsearch_ready(self, max_attempts: int = 30, delay: float = 2.0):
        """Wait for Elasticsearch to be healthy and ready"""
        logger.info("Waiting for Elasticsearch to be ready...")
        
        for attempt in range(max_attempts):
            try:
                # Test basic connectivity
                info = await self.client.info()
                cluster_name = info.get('cluster_name', 'unknown')
                
                # Check cluster health
                health = await self.client.cluster.health(
                    wait_for_status='yellow',
                    timeout='5s',
                    request_timeout=10
                )
                
                status = health['status']
                if status in ['green', 'yellow']:
                    logger.info(f"✅ Elasticsearch ready: {cluster_name} (status: {status})")
                    return True
                else:
                    logger.info(f"⏳ Elasticsearch status: {status} (attempt {attempt + 1}/{max_attempts})")
                    
            except Exception as e:
                error_msg = str(e)
                if "Connection error" in error_msg or "Cannot connect" in error_msg:
                    logger.info(f"⏳ Waiting for Elasticsearch connection... (attempt {attempt + 1}/{max_attempts})")
                else:
                    logger.info(f"⏳ Elasticsearch not ready... (attempt {attempt + 1}/{max_attempts}): {error_msg[:100]}")
            
            if attempt < max_attempts - 1:
                # Use exponential backoff with max delay of 10 seconds
                current_delay = min(delay * (1.5 ** attempt), 10.0)
                await asyncio.sleep(current_delay)
        
        logger.error(f"❌ Elasticsearch not ready after {max_attempts} attempts")
        raise Exception("Elasticsearch failed to become ready within the timeout period")
    
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
        """Create Elasticsearch indices with vector search mappings - one per category"""
        
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
                    
                    # Dynamic fields that can be strings, numbers, or arrays
                    "form_factor": {"type": "text"},
                    "airflow": {"type": "text"},
                    "noise_level": {"type": "text"},
                    "rpm": {"type": "text"},
                    "size": {"type": "text"},
                    "capacity": {"type": "text"},
                    "speed": {"type": "text"},
                    "modules": {"type": "text"},
                    "core_count": {"type": "text"},
                    "core_clock": {"type": "text"},
                    "boost_clock": {"type": "text"},
                    "tdp": {"type": "text"},
                    "memory": {"type": "text"},
                    "wattage": {"type": "text"},
                    "screen_size": {"type": "text"},
                    "resolution": {"type": "text"},
                    "refresh_rate": {"type": "text"},
                    "response_time": {"type": "text"},
                    "panel_type": {"type": "text"},
                    "aspect_ratio": {"type": "text"},
                    "type": {"type": "text"},
                    "color": {"type": "text"},
                    "interface": {"type": "text"},
                    "efficiency": {"type": "text"},
                    "modular": {"type": "text"},
                    "socket": {"type": "text"},
                    "max_memory": {"type": "text"},
                    "memory_slots": {"type": "text"},
                    "side_panel": {"type": "text"},
                    "external_volume": {"type": "text"},
                    "internal_35_bays": {"type": "text"},
                    "channels": {"type": "text"},
                    "channel_wattage": {"type": "text"},
                    "pwm": {"type": "text"},
                    "frequency_response": {"type": "text"},
                    "microphone": {"type": "text"},
                    "wireless": {"type": "text"},
                    "enclosure_type": {"type": "text"},
                    "style": {"type": "text"},
                    "switches": {"type": "text"},
                    "backlit": {"type": "text"},
                    "tenkeyless": {"type": "text"},
                    "connection_type": {"type": "text"},
                    "tracking_method": {"type": "text"},
                    "max_dpi": {"type": "text"},
                    "hand_orientation": {"type": "text"},
                    "bd": {"type": "text"},
                    "dvd": {"type": "text"},
                    "cd": {"type": "text"},
                    "bd_write": {"type": "text"},
                    "dvd_write": {"type": "text"},
                    "cd_write": {"type": "text"},
                    "mode": {"type": "text"},
                    "digital_audio": {"type": "text"},
                    "snr": {"type": "text"},
                    "sample_rate": {"type": "text"},
                    "chipset": {"type": "text"},
                    "configuration": {"type": "text"},
                    "amount": {"type": "text"},
                    "capacity_w": {"type": "text"},
                    "capacity_va": {"type": "text"},
                    "chipset": {"type": "text"},
                    "length": {"type": "text"},
                    "resolutions": {"type": "text"},
                    "focus_type": {"type": "text"},
                    "os": {"type": "text"},
                    "fov": {"type": "text"},
                    "protocol": {"type": "text"},
                    "price_per_gb": {"type": "text"},
                    "first_word_latency": {"type": "text"},
                    "cas_latency": {"type": "text"},
                    "cache": {"type": "text"},
                    "graphics": {"type": "text"},
                    "smt": {"type": "text"},
                    
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
        
        # Create per-category product indices
        for category, index_name in CATEGORY_INDEX_MAP.items():
            try:
                exists = await self.client.indices.exists(index=index_name)
                if not exists:
                    await self.client.indices.create(index=index_name, **products_mapping)
                    logger.info(f"Created category vector index: {index_name} for category: {category}")
                else:
                    logger.info(f"Category index already exists: {index_name}")
            except Exception as e:
                logger.warning(f"Category vector index creation issue for {index_name}: {e}")
        
        # Create default index for uncategorized products
        try:
            exists = await self.client.indices.exists(index=DEFAULT_PRODUCTS_INDEX)
            if not exists:
                await self.client.indices.create(index=DEFAULT_PRODUCTS_INDEX, **products_mapping)
                logger.info(f"Created default products vector index: {DEFAULT_PRODUCTS_INDEX}")
            else:
                logger.info(f"Default products index already exists: {DEFAULT_PRODUCTS_INDEX}")
        except Exception as e:
            logger.warning(f"Default products vector index creation issue: {e}")

        # Solutions index with vector mapping (keep as single index for now)
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
    
    def _infer_category_from_filename(self, filename: str) -> str:
        """Infer product category from filename with flexible pattern matching"""
        # Remove .json extension
        base_name = filename.replace(".json", "")
        
        # Try to match against known categories in FIELD_MAP
        for category in FIELD_MAP.keys():
            # Handle various separators and formats
            if re.match(rf'^{re.escape(category)}$', base_name, re.IGNORECASE):
                return category
            # Handle underscore variants
            if re.match(rf'^{re.escape(category).replace("-", "_")}$', base_name, re.IGNORECASE):
                return category
            # Handle space variants
            if re.match(rf'^{re.escape(category).replace("-", " ")}$', base_name, re.IGNORECASE):
                return category
        
        # If no exact match, try to normalize and find closest match
        normalized = re.sub(r'[_\s]+', '-', base_name.lower())
        for category in FIELD_MAP.keys():
            if normalized == category:
                return category
        
        # Fallback: return the base name as-is
        return base_name

    def _create_searchable_content(self, item: Dict[str, Any], item_type: str = "product", filename: str = None) -> str:
        """Create searchable text content for embedding, category-aware"""
        text_parts = []
        category = None
        
        if filename:
            category = self._infer_category_from_filename(Path(filename).name)
        
        if item_type == "product" and category and category in FIELD_MAP:
            # Use category-specific field mapping
            text_parts.append(f"Category: {category}")
            for field in FIELD_MAP[category]:
                value = item.get(field)
                if value is not None:
                    text_parts.append(f"{field.replace('_', ' ').capitalize()}: {value}")
        else:
            # Fallback to general field extraction
            text_parts.append(f"Type: {item_type}")
            
            # Add common fields
            common_fields = ['name', 'description', 'category', 'type', 'price', 'features', 'tags']
            for field in common_fields:
                value = item.get(field)
                if value is not None:
                    text_parts.append(f"{field.replace('_', ' ').capitalize()}: {value}")
            
            # Add any other fields that might be useful
            for key, value in item.items():
                if key not in common_fields and value is not None and isinstance(value, (str, int, float)):
                    text_parts.append(f"{key.replace('_', ' ').capitalize()}: {value}")
        
        return " | ".join(text_parts)
    
    async def index_product(self, product: Dict[str, Any], filename: str = None):
        """Index a product with vector embedding into category-specific index"""
        try:
            # Generate searchable content
            searchable_content = self._create_searchable_content(product, "product", filename)
            
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
            
            # Determine which index to use based on category
            category = product.get("category")
            if not category and filename:
                # Try to infer category from filename if not present in product
                category = self._infer_category_from_filename(Path(filename).name)
                doc["category"] = category
            
            # Get the appropriate index for this category
            index_name = CATEGORY_INDEX_MAP.get(category, DEFAULT_PRODUCTS_INDEX)
            
            # Index document into category-specific index
            await self.client.index(
                index=index_name,
                id=doc["id"],
                document=doc
            )
            
            logger.debug(f"Indexed product '{doc.get('name', 'Unknown')}' in category '{category}' to index '{index_name}'")
            
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
        hybrid_weight: float = 0.1,
        categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Perform vector search on products with optional category filtering"""
        try:
            # Get query embedding
            query_embeddings = await self.get_embeddings([query])
            query_vector = query_embeddings[0]
            
            # Determine which indices to search
            if categories:
                # Search only in specified category indices
                index_names = []
                for category in categories:
                    index_name = CATEGORY_INDEX_MAP.get(category, DEFAULT_PRODUCTS_INDEX)
                    index_names.append(index_name)
                # Remove duplicates
                index_names = list(set(index_names))
            else:
                # Search in all category indices
                index_names = list(CATEGORY_INDEX_MAP.values()) + [DEFAULT_PRODUCTS_INDEX]
            
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
            
            # Add text search for hybrid approach with improved field matching
            text_query = {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "name^4",                    # Highest boost for name
                        "description^3",             # High boost for description
                        "features^2",                # Medium boost for features
                        "use_cases^2",               # Medium boost for use cases
                        "tags^2",                    # Medium boost for tags
                        "category^1.5",              # Lower boost for category
                        "searchable_content^1.5"     # Lower boost for searchable content
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "operator": "or"  # Use OR for better recall
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
            
            # Execute search across relevant indices
            response = await self.client.search(index=index_names, body=search_query)
            
            # Process results
            products = []
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                product["_score"] = hit["_score"]
                product["_similarity_score"] = hit["_score"]  # For compatibility
                product["_index"] = hit["_index"]  # Track which index this came from
                products.append(product)
            
            logger.info(f"Vector search returned {len(products)} products for query: '{query}' in indices: {index_names}")
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
            
            # Add text search for hybrid approach with improved field matching
            text_query = {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "name^4",                    # Highest boost for name
                        "description^3",             # High boost for description
                        "features^2",                # Medium boost for features
                        "use_cases^2",               # Medium boost for use cases
                        "tags^2",                    # Medium boost for tags
                        "category^1.5",              # Lower boost for category
                        "searchable_content^1.5"     # Lower boost for searchable content
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "operator": "or"  # Use OR for better recall
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
        """Load data from JSON files with vector embeddings, passing filename for category inference"""
        try:
            # Check if data loading should be skipped
            skip_loading = getattr(settings, 'skip_data_loading', False)
            if skip_loading:
                logger.info("Data loading skipped due to SKIP_DATA_LOADING configuration")
                return {
                    "files_processed": 0,
                    "products_indexed": 0,
                    "solutions_indexed": 0,
                    "skipped": True
                }
            
            # Ensure Elasticsearch is ready before loading data
            await self._wait_for_elasticsearch_ready()
            
            logger.info(f"Loading data into Elasticsearch with vector embeddings...")
            data_dir = settings.data_dir
            total_products_indexed = 0
            total_solutions_indexed = 0
            files_processed = 0
            for json_file in data_dir.glob("*.json"):
                try:
                    logger.info(f"Processing file: {json_file.name}")
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    file_products = 0
                    file_solutions = 0
                    if isinstance(data, list):
                        items = data[:max_per_file]
                        for item in items:
                            if self._is_product_data(item):
                                await self.index_product(item, filename=json_file.name)
                                file_products += 1
                            elif self._is_solution_data(item):
                                await self.index_solution(item)
                                file_solutions += 1
                    elif isinstance(data, dict):
                        if 'products' in data:
                            products = data['products'][:max_per_file]
                            for product in products:
                                if self._is_valid_product(product):
                                    await self.index_product(product, filename=json_file.name)
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
            category_counts = {}
            
            # Refresh category indices that have data
            for category, index_name in CATEGORY_INDEX_MAP.items():
                try:
                    count_response = await self.client.count(index=index_name)
                    count = count_response.get('count', 0)
                    category_counts[category] = count
                    if count > 0:
                        await self.client.indices.refresh(index=index_name)
                        logger.info(f"✅ Refreshed {category} index ({index_name}) with {count} documents")
                except Exception as e:
                    logger.debug(f"Category index {index_name} not found or empty: {e}")
                    category_counts[category] = 0
            
            # Refresh default index if it has data
            try:
                count_response = await self.client.count(index=DEFAULT_PRODUCTS_INDEX)
                default_count = count_response.get('count', 0)
                if default_count > 0:
                    await self.client.indices.refresh(index=DEFAULT_PRODUCTS_INDEX)
                    logger.info(f"✅ Refreshed default products index with {default_count} documents")
            except Exception as e:
                logger.debug(f"Default products index not found or empty: {e}")
                default_count = 0
            
            # Refresh solutions index
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
            
            # Log category breakdown
            logger.info(f"📊 Products by category:")
            for category, count in category_counts.items():
                if count > 0:
                    logger.info(f"   {category}: {count} products")
            if default_count > 0:
                logger.info(f"   other/uncategorized: {default_count} products")
            
            return {
                "files_processed": files_processed,
                "products_indexed": total_products_indexed,
                "solutions_indexed": total_solutions_indexed
            }
            
        except Exception as e:
            logger.error(f"Failed to load data with vectors: {e}")
            raise
    
    def _is_product_data(self, item: Dict[str, Any]) -> bool:
        """Check if item is product data"""
        product_indicators = ['product_name', 'category', 'price', 'specifications']
        return any(key in item for key in product_indicators)
    
    def _is_solution_data(self, item: Dict[str, Any]) -> bool:
        """Check if item is solution data"""
        solution_indicators = ['solution_name', 'use_case', 'industry', 'components']
        return any(key in item for key in solution_indicators)
    
    def _is_valid_product(self, product: Dict[str, Any]) -> bool:
        """Validate product data"""
        return bool(product.get('name') or product.get('product_name'))
    
    def _is_valid_solution(self, solution: Dict[str, Any]) -> bool:
        """Validate solution data"""
        return bool(solution.get('name') or solution.get('solution_name'))
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about vector indices"""
        try:
            # Get products stats across all category indices
            products_count = 0
            category_stats = {}
            
            # Count products in each category index
            for category, index_name in CATEGORY_INDEX_MAP.items():
                try:
                    category_stats_response = await self.client.count(index=index_name)
                    count = category_stats_response["count"]
                    category_stats[category] = count
                    products_count += count
                except Exception as e:
                    logger.debug(f"Failed to get stats for {category} index ({index_name}): {e}")
                    category_stats[category] = 0
            
            # Count products in default index
            try:
                default_stats = await self.client.count(index=DEFAULT_PRODUCTS_INDEX)
                default_count = default_stats["count"]
                category_stats["other"] = default_count
                products_count += default_count
            except Exception as e:
                logger.debug(f"Failed to get stats for default products index: {e}")
                category_stats["other"] = 0

            # Get solutions stats - handle missing index gracefully
            solutions_count = 0
            try:
                solutions_stats = await self.client.count(index=self.solutions_index)
                solutions_count = solutions_stats["count"]
            except Exception as e:
                logger.debug(f"Solutions index not found or empty: {e}")

            return {
                "products_count": products_count,
                "category_breakdown": category_stats,
                "solutions_count": solutions_count,
                "status": "healthy",
                "service": "elasticsearch_vector",
                "initialized": True
            }
        except Exception as e:
            logger.error(f"Failed to get vector service stats: {e}")
            return {
                "products_count": 0,
                "category_breakdown": {},
                "solutions_count": 0,
                "status": "error",
                "error": str(e),
                "initialized": False
            }
    
    async def close(self):
        """Close Elasticsearch connection"""
        await self.client.close()

    async def _extract_categories_from_requirements(self, requirements: Dict[str, Any]) -> List[str]:
        """Extract relevant product categories from requirements using LLM intelligence"""
        
        # Use LLM-powered category extraction
        categories = await self._extract_categories_with_llm(requirements)
        
        # If no categories found, try the fallback method
        if not categories:
            categories = await self._extract_categories_fallback(requirements)
        
        # If still no categories, default to core categories based on common use cases
        if not categories:
            # Check if this looks like a workstation/professional use case
            text_content = []
            for key in ['semantic_query', 'technical_requirements', 'business_requirements']:
                value = requirements.get(key)
                if value:
                    if isinstance(value, list):
                        text_content.extend([str(item) for item in value])
                    else:
                        text_content.append(str(value))
            
            combined_text = " ".join(text_content).lower()
            
            if any(term in combined_text for term in ['workstation', 'professional', 'video', 'ai', 'ml', 'rendering']):
                categories = ['cpu', 'video-card', 'memory', 'internal-hard-drive']
            elif any(term in combined_text for term in ['gaming', 'game', 'fps']):
                categories = ['video-card', 'cpu', 'memory', 'monitor']
            elif any(term in combined_text for term in ['storage', 'nas', 'file']):
                categories = ['internal-hard-drive', 'external-hard-drive']
            elif any(term in combined_text for term in ['office', 'business', 'productivity']):
                categories = ['cpu', 'memory', 'monitor']
            else:
                # Default to most common categories
                categories = ['cpu', 'memory', 'internal-hard-drive']
        
        logger.info(f"🎯 Final categories selected: {categories}")
        return categories

    # ===== COMPATIBILITY METHODS FOR OLD SERVICE INTERFACE =====
    
    async def search_products(self, query_body: dict, index: str = "products") -> List[Dict]:
        """Compatibility method for old service interface - converts to vector search with category awareness"""
        try:
            # Extract query from query_body if it's a string
            if isinstance(query_body, str):
                query = query_body
                categories = None
            elif isinstance(query_body, dict):
                # Try to extract query from various possible structures
                if "query" in query_body:
                    query_part = query_body["query"]
                    if isinstance(query_part, dict) and "multi_match" in query_part:
                        query = query_part["multi_match"]["query"]
                    elif isinstance(query_part, dict) and "match" in query_part:
                        query = query_part["match"].get("name", "")
                    else:
                        query = str(query_part)
                else:
                    query = str(query_body)
                
                # Try to extract categories if available
                categories = self._extract_categories_from_requirements(query_body)
            else:
                query = str(query_body)
                categories = None
            
            # Use vector search with hybrid approach and category filtering
            return await self.vector_search_products(
                query, 
                size=20, 
                hybrid_weight=0.2, 
                categories=categories
            )
            
        except Exception as e:
            logger.error(f"Compatibility search_products failed: {e}")
            return []
    
    async def search_products_by_requirements(self, requirements: Dict[str, Any], size: int = 20) -> List[Dict]:
        """Compatibility method for old service interface - converts requirements to vector search with category filtering"""
        try:
            # Build query from requirements
            search_terms = requirements.get('search_terms', [])
            categories = requirements.get('product_categories', [])
            tech_reqs = requirements.get('technical_requirements', [])
            business_reqs = requirements.get('business_requirements', [])
            
            # Combine all search terms
            all_terms = search_terms + categories + tech_reqs + business_reqs
            query = " ".join([str(term) for term in all_terms if term])
            
            if not query:
                query = "business technology professional enterprise"
            
            # Extract relevant categories from requirements (FIX: Add await)
            relevant_categories = await self._extract_categories_from_requirements(requirements)
            
            # Use vector search with hybrid approach and category filtering
            return await self.vector_search_products(
                query, 
                size=size, 
                hybrid_weight=0.2,
                categories=relevant_categories if relevant_categories else None
            )
            
        except Exception as e:
            logger.error(f"Compatibility search_products_by_requirements failed: {e}")
            return []
    
    async def search_products_with_fallback(self, requirements: Dict[str, Any], size: int = 20) -> List[Dict]:
        """Compatibility method for old service interface - uses vector search with fallback"""
        try:
            results = await self.search_products_by_requirements(requirements, size)
            if results:
                return results
            
            # Fallback to random products
            return await self.get_random_products(size)
            
        except Exception as e:
            logger.error(f"Compatibility search_products_with_fallback failed: {e}")
            return []
    
    async def get_random_products(self, size: int = 10) -> List[Dict]:
        """Compatibility method for old service interface - get random products from all categories"""
        try:
            # Get indices to search
            all_indices = list(CATEGORY_INDEX_MAP.values()) + [DEFAULT_PRODUCTS_INDEX]
            
            search_body = {
                "size": size,
                "query": {
                    "function_score": {
                        "query": {"match_all": {}},
                        "random_score": {},
                        "boost_mode": "replace"
                    }
                }
            }
            
            response = await self.client.search(index=all_indices, body=search_body)
            
            results = []
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                product["_index"] = hit["_index"]  # Track source index
                results.append(product)
            
            logger.info(f"Retrieved {len(results)} random products from all categories")
            return results
            
        except Exception as e:
            logger.error(f"Random products retrieval failed: {e}")
            return []
    
    async def search_solutions(self, requirements: Dict[str, Any], size: int = 5) -> List[Dict]:
        """Compatibility method for old service interface - search solutions"""
        try:
            # Build query from requirements
            use_case = requirements.get('use_case', '')
            industry = requirements.get('industry', '')
            company_size = requirements.get('company_size', '')
            
            query = f"{use_case} {industry} {company_size}".strip()
            if not query:
                query = "business solution"
            
            return await self.vector_search_solutions(query, size=size, hybrid_weight=0.2)
            
        except Exception as e:
            logger.error(f"Solution search failed: {e}")
            return []
    
    async def get_product_categories(self) -> List[str]:
        """Compatibility method for old service interface - get product categories"""
        try:
            # Return available categories based on indices that have data
            categories = []
            for category, index_name in CATEGORY_INDEX_MAP.items():
                try:
                    count_response = await self.client.count(index=index_name)
                    if count_response.get('count', 0) > 0:
                        categories.append(category)
                except Exception:
                    continue  # Index doesn't exist or is empty
            
            return categories
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return []
    
    async def get_product_stats(self) -> Dict[str, Any]:
        """Compatibility method for old service interface - get product statistics"""
        try:
            total_products = 0
            categories = {}
            price_stats = {"min": None, "max": None, "avg": None}
            
            # Get stats from each category index
            for category, index_name in CATEGORY_INDEX_MAP.items():
                try:
                    # Get count
                    count_response = await self.client.count(index=index_name)
                    count = count_response.get('count', 0)
                    if count > 0:
                        categories[category] = count
                        total_products += count
                        
                        # Get price stats for this category
                        price_agg_response = await self.client.search(
                            index=index_name,
                            body={
                                "size": 0,
                                "aggs": {
                                    "price_stats": {
                                        "stats": {"field": "price"}
                                    }
                                }
                            }
                        )
                        
                        if "aggregations" in price_agg_response:
                            category_price_stats = price_agg_response["aggregations"]["price_stats"]
                            if category_price_stats.get("count", 0) > 0:
                                min_price = category_price_stats.get("min")
                                max_price = category_price_stats.get("max")
                                
                                if min_price is not None:
                                    if price_stats["min"] is None or min_price < price_stats["min"]:
                                        price_stats["min"] = min_price
                                
                                if max_price is not None:
                                    if price_stats["max"] is None or max_price > price_stats["max"]:
                                        price_stats["max"] = max_price
                        
                except Exception as e:
                    logger.debug(f"Failed to get stats for {category}: {e}")
                    continue
            
            # Check default index
            try:
                count_response = await self.client.count(index=DEFAULT_PRODUCTS_INDEX)
                default_count = count_response.get('count', 0)
                if default_count > 0:
                    categories["other"] = default_count
                    total_products += default_count
            except Exception:
                pass
            
            # Calculate average price (simplified)
            if price_stats["min"] is not None and price_stats["max"] is not None:
                price_stats["avg"] = (price_stats["min"] + price_stats["max"]) / 2
            
            return {
                "total_products": total_products,
                "categories": categories,
                "price_range": price_stats
            }
        except Exception as e:
            logger.error(f"Failed to get product stats: {e}")
            return {"total_products": 0, "categories": {}, "price_range": {}}
    
    async def reindex_all_data(self, force_replace: bool = False):
        """Compatibility method for old service interface - reindex all data"""
        try:
            logger.info("Reindexing all data with vector embeddings...")
            await self.load_data_from_json(max_per_file=50)
            logger.info("Successfully reindexed all data with vectors")
        except Exception as e:
            logger.error(f"Failed to reindex data: {e}")
            raise
    
    async def get_cluster_health(self) -> Dict[str, Any]:
        """Compatibility method for old service interface - get cluster health"""
        try:
            health = await self.client.cluster.health()
            return {
                "status": health["status"],
                "number_of_nodes": health["number_of_nodes"],
                "active_primary_shards": health["active_primary_shards"],
                "active_shards": health["active_shards"]
            }
        except Exception as e:
            logger.error(f"Failed to get cluster health: {e}")
            return {"status": "red", "error": str(e)}
    
    async def _safe_count(self, index: str) -> int:
        """Compatibility method for old service interface - safe count"""
        try:
            response = await self.client.count(index=index)
            return response.get('count', 0)
        except Exception as e:
            logger.error(f"Count failed for {index}: {e}")
            return 0
    
    async def _wait_for_cluster_ready(self, max_attempts: int = 10, delay: float = 2.0):
        """Compatibility method for old service interface - wait for cluster"""
        for attempt in range(max_attempts):
            try:
                health = await self.client.cluster.health(
                    wait_for_status='yellow',
                    timeout='2s',
                    request_timeout=3
                )
                
                if health['status'] in ['green', 'yellow']:
                    logger.info(f"Cluster ready: {health['status']} status")
                    return True
                    
            except Exception as e:
                logger.warning(f"Cluster not ready (attempt {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
        
        logger.warning("Cluster readiness timeout - proceeding anyway")
        return False

    def set_llm_provider(self, llm_provider):
        """Set the LLM provider for intelligent category detection"""
        self.llm_provider = llm_provider
        logger.info("✅ LLM provider set for intelligent category detection")

    async def _extract_categories_with_llm(self, requirements: Dict[str, Any]) -> List[str]:
        """Use LLM with Pydantic function calling to intelligently extract relevant product categories"""
        
        if not self.llm_provider:
            logger.warning("No LLM provider available for category extraction, using fallback")
            return await self._extract_categories_fallback(requirements)
        
        try:
            # Get available categories dynamically
            available_categories = await self._get_active_categories()
            
            if not available_categories:
                logger.warning("No active categories found")
                return []
            
            # Build context for LLM analysis
            context_parts = []
            
            # Add semantic query if available
            if requirements.get('semantic_query'):
                context_parts.append(f"Query: {requirements['semantic_query']}")
            
            # Add technical requirements
            if requirements.get('technical_requirements'):
                tech_reqs = requirements['technical_requirements']
                if isinstance(tech_reqs, list):
                    context_parts.append(f"Technical Requirements: {', '.join(str(req) for req in tech_reqs)}")
                else:
                    context_parts.append(f"Technical Requirements: {tech_reqs}")
            
            # Add business requirements
            if requirements.get('business_requirements'):
                business_reqs = requirements['business_requirements']
                if isinstance(business_reqs, list):
                    context_parts.append(f"Business Requirements: {', '.join(str(req) for req in business_reqs)}")
                else:
                    context_parts.append(f"Business Requirements: {business_reqs}")
            
            # Add use case
            if requirements.get('use_case'):
                context_parts.append(f"Use Case: {requirements['use_case']}")
            
            # Add industry
            if requirements.get('industry'):
                context_parts.append(f"Industry: {requirements['industry']}")
            
            # Add LLM context if available
            llm_context = requirements.get('llm_context', {})
            if llm_context.get('primary_need'):
                context_parts.append(f"Primary Need: {llm_context['primary_need']}")
            if llm_context.get('business_context'):
                context_parts.append(f"Business Context: {llm_context['business_context']}")
            
            requirements_text = "\n".join(context_parts)
            
            # Create intelligent prompt for Pydantic function calling
            category_prompt = f"""You are an expert B2B technology consultant analyzing customer requirements to determine which product categories are most relevant for their needs.

CUSTOMER REQUIREMENTS:
{requirements_text}

AVAILABLE PRODUCT CATEGORIES:
{', '.join(available_categories)}

CATEGORY DESCRIPTIONS:
• cpu: Processors, CPUs for workstations, servers, gaming systems
• video-card: Graphics cards, GPUs for gaming, AI/ML, rendering, professional workstations  
• memory: RAM, system memory, DDR4/DDR5 modules for performance
• monitor: Displays, screens, monitors for professional work, gaming, content creation
• internal-hard-drive: Internal storage drives, SSDs, HDDs, NVMe drives for data storage
• external-hard-drive: External storage, portable drives, backup storage solutions
• motherboard: System boards, platforms, chipsets - foundation of any system
• power-supply: Power supplies, PSUs for stable system operation
• case: Computer cases, enclosures, chassis for housing components
• cpu-cooler: CPU cooling solutions, thermal management for performance
• keyboard: Input devices, mechanical keyboards, wireless keyboards
• mouse: Pointing devices, gaming mice, professional mice for productivity
• headphones: Audio devices, headsets, professional audio equipment
• speakers: Audio output, sound systems for multimedia
• webcam: Video devices, conferencing cameras for communication
• optical-drive: CD/DVD/Blu-ray drives for legacy media
• ups: Uninterruptible power supplies, backup power for critical systems
• wireless-network-card: WiFi adapters, wireless networking solutions
• wired-network-card: Ethernet adapters, wired networking for reliability

ANALYSIS GUIDELINES:
1. Focus on categories that directly solve the customer's stated needs
2. Consider the primary use case and industry context
3. Prioritize essential components over accessories
4. Limit to 3-5 most relevant categories for focused search
5. Consider complementary products that work together

COMMON USE CASE PATTERNS:
• Gaming: video-card, cpu, memory, monitor
• Workstation/Professional: cpu, video-card, memory, internal-hard-drive
• AI/ML Training: video-card, cpu, memory, internal-hard-drive  
• Office/Productivity: cpu, memory, monitor, keyboard, mouse
• Storage/NAS: internal-hard-drive, external-hard-drive
• Content Creation: video-card, cpu, memory, monitor

Analyze the requirements and provide structured category recommendations."""

            try:
                # Use Pydantic function calling for structured response
                logger.info("🧠 Using Pydantic function calling for category analysis...")
                category_analysis = await self.llm_provider.generate_structured_response(
                    [AIMessage(role="user", content=category_prompt)],
                    CategoryAnalysis
                )
                
                # Validate that returned categories are in available categories
                valid_categories = [
                    cat for cat in category_analysis.relevant_categories 
                    if cat in available_categories
                ]
                
                logger.info(f"🧠 LLM Category Analysis:")
                logger.info(f"   Primary Use Case: {category_analysis.primary_use_case}")
                logger.info(f"   Technical Focus: {category_analysis.technical_focus}")
                logger.info(f"   Selected Categories: {valid_categories}")
                logger.info(f"   Confidence: {category_analysis.confidence:.1%}")
                logger.info(f"   Reasoning: {category_analysis.reasoning}")
                
                if category_analysis.alternative_categories:
                    valid_alternatives = [
                        cat for cat in category_analysis.alternative_categories 
                        if cat in available_categories
                    ]
                    logger.info(f"   Alternative Categories: {valid_alternatives}")
                
                return valid_categories[:5]  # Limit to 5 categories max
                    
            except Exception as e:
                logger.warning(f"Pydantic function calling failed: {e}")
                return await self._extract_categories_fallback(requirements)
                
        except Exception as e:
            logger.error(f"LLM category extraction failed: {e}")
            return await self._extract_categories_fallback(requirements)

    async def _extract_categories_fallback(self, requirements: Dict[str, Any]) -> List[str]:
        """Fallback category extraction using pattern matching"""
        
        categories = set()
        
        # Get text to analyze
        text_parts = []
        
        for key in ['semantic_query', 'technical_requirements', 'business_requirements', 'use_case']:
            value = requirements.get(key)
            if value:
                if isinstance(value, list):
                    text_parts.extend([str(item) for item in value])
                else:
                    text_parts.append(str(value))
        
        text = " ".join(text_parts).lower()
        
        # Simple pattern matching as fallback
        if any(word in text for word in ['storage', 'nas', 'file sharing', 'raid', 'backup']):
            categories.update(['internal-hard-drive', 'external-hard-drive'])
        
        if any(word in text for word in ['gaming', '1440p', 'fps', 'ray tracing', 'gpu', 'graphics']):
            categories.update(['video-card', 'cpu', 'memory'])
        
        if any(word in text for word in ['workstation', 'professional', 'video editing', '3d rendering']):
            categories.update(['video-card', 'cpu', 'memory', 'internal-hard-drive'])
        
        if any(word in text for word in ['ai', 'ml', 'machine learning', 'training', 'dataset']):
            categories.update(['video-card', 'cpu', 'memory', 'internal-hard-drive'])
        
        if any(word in text for word in ['monitor', 'display', 'screen', '27-inch', '4k']):
            categories.add('monitor')
        
        if any(word in text for word in ['office', 'productivity', 'business']):
            categories.update(['cpu', 'memory', 'monitor'])
        
        return list(categories)

    async def _get_active_categories(self) -> List[str]:
        """Get categories that actually have data"""
        active_categories = []
        
        for category, index_name in CATEGORY_INDEX_MAP.items():
            try:
                count_response = await self.client.count(index=index_name)
                if count_response.get('count', 0) > 0:
                    active_categories.append(category)
            except:
                continue
                
        return active_categories

# Global instance
_elasticsearch_vector_service = None

def get_elasticsearch_vector_service(azure_embedding_endpoint: str, azure_embedding_key: str) -> ElasticsearchVectorService:
    """Get singleton Elasticsearch vector service instance"""
    global _elasticsearch_vector_service
    if _elasticsearch_vector_service is None:
        _elasticsearch_vector_service = ElasticsearchVectorService(azure_embedding_endpoint, azure_embedding_key)
    return _elasticsearch_vector_service

# Compatibility wrapper for drop-in replacement
def get_elasticsearch_service() -> ElasticsearchVectorService:
    """Compatibility function to replace the old service - uses vector service with default Azure credentials"""
    from config import settings
    
    # Use the same Azure credentials as the main AI service
    azure_embedding_endpoint = settings.azure_embedding_endpoint
    azure_embedding_key = settings.azure_embedding_api_key
    
    if not azure_embedding_endpoint or not azure_embedding_key:
        raise ValueError("Azure embedding credentials not configured. Please set AZURE_EMBEDDING_ENDPOINT and AZURE_OPENAI_API_KEY environment variables.")
    
    return get_elasticsearch_vector_service(azure_embedding_endpoint, azure_embedding_key) 