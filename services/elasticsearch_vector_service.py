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
    "laptop": [
        "title", "brand", "series", "item model number", "price", "ram", "computer memory type", "hard drive", "operating system", "processor", "chipset brand", "graphics coprocessor", "screen resolution", "max screen resolution", "standing screen display size", "item weight", "item dimensions  lxwxh", "color", "number of processors", "number of usb 3.0 ports", "wireless type", "tags", "url", "images", "customer reviews", "best sellers rank", "hard drive interface", "processor brand", "product dimensions"
    ],
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
    "laptop": "laptop_vector",
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

class DynamicQueryGeneration(BaseModel):
    """AI-powered dynamic query generation based on data structure and categories"""
    semantic_query: str = Field(
        description="Optimized semantic search query for vector search"
    )
    keyword_query: Dict[str, Any] = Field(
        description="Structured keyword query for Elasticsearch with field boosting",
        default_factory=lambda: {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"name": {"query": "product", "boost": 4.0}}},
                        {"match": {"description": {"query": "product", "boost": 3.0}}},
                        {"match": {"features": {"query": "product", "boost": 2.0}}},
                        {"match": {"category": {"query": "product", "boost": 1.5}}}
                    ]
                }
            },
            "size": 20
        }
    )
    category_filters: List[str] = Field(
        description="Relevant product categories to search in",
        default_factory=list
    )
    field_priorities: Dict[str, float] = Field(
        description="Field-specific boost values for keyword search",
        default_factory=lambda: {
            "name": 4.0,
            "description": 3.0,
            "features": 2.0,
            "category": 1.5
        }
    )
    search_strategy: str = Field(
        description="Search strategy: 'hybrid', 'vector_only', 'keyword_only', 'category_specific'",
        default="hybrid"
    )
    confidence: float = Field(
        description="Confidence in query generation (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
        default=0.5
    )
    reasoning: str = Field(
        description="Explanation of why this query structure was chosen",
        default="AI-generated query based on requirements analysis"
    )
    suggested_filters: Dict[str, Any] = Field(
        description="Suggested filters based on requirements",
        default_factory=dict
    )

class DataStructureInfo(BaseModel):
    """Information about our data structure for AI query generation"""
    available_categories: List[str] = Field(
        description="All available product categories"
    )
    category_fields: Dict[str, List[str]] = Field(
        description="Fields available for each category"
    )
    searchable_fields: List[str] = Field(
        description="All searchable fields across categories"
    )
    field_importance: Dict[str, float] = Field(
        description="Default importance/boost values for fields"
    )
    index_mapping: Dict[str, str] = Field(
        description="Category to index mapping"
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
        
        # Dynamically generate products mapping from FIELD_MAP
        all_fields = set()
        for fields in FIELD_MAP.values():
            all_fields.update(fields)
        
        # Add standard fields that all products should have
        standard_fields = {
            "id", "name", "title", "category", "subcategory", "description", 
            "specifications", "price", "currency", "availability", "tags", 
            "features", "use_cases", "target_industries", "compatibility", 
            "warranty", "support_level", "content_vector", "searchable_content"
        }
        all_fields.update(standard_fields)
        
        # Build dynamic properties mapping
        properties = {
            "id": {"type": "keyword"},
            "name": {"type": "text", "analyzer": "standard"},
            "title": {"type": "text", "analyzer": "standard"},
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
            
            # Vector fields
            "content_vector": {
                "type": "dense_vector",
                "dims": self.embedding_dimension,
                "index": True,
                "similarity": "cosine"
            },
            "searchable_content": {"type": "text", "analyzer": "standard"}
        }
        
        # Add all fields from FIELD_MAP as text fields
        for field in all_fields:
            if field not in properties:
                # Normalize field names (replace spaces with underscores)
                normalized_field = field.replace(" ", "_").replace("-", "_")
                properties[normalized_field] = {"type": "text", "analyzer": "standard"}
        
        # Products index with dynamic vector mapping
        products_mapping = {
            "mappings": {
                "properties": properties
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
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
                "number_of_replicas": 0
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
        """Perform vector search on products with optional category filtering and balanced results"""
        try:
            logger.info(f"🔍 Vector search called with query: '{query}', categories: {categories}")
            
            # Get query embedding
            query_embeddings = await self.get_embeddings([query])
            query_vector = query_embeddings[0]
            
            # Determine which indices to search - be more restrictive when categories are specified
            if categories and len(categories) > 0:
                # Search ONLY in specified category indices
                index_names = []
                for category in categories:
                    index_name = CATEGORY_INDEX_MAP.get(category, DEFAULT_PRODUCTS_INDEX)
                    index_names.append(index_name)
                # Remove duplicates
                index_names = list(set(index_names))
                
                logger.info(f"🎯 Searching ONLY in specified category indices: {index_names}")
            else:
                # Search in all category indices
                index_names = list(CATEGORY_INDEX_MAP.values()) + [DEFAULT_PRODUCTS_INDEX]
                logger.info(f"🌐 Searching in all indices: {len(index_names)} indices")
            
            # Use proper KNN search instead of script_score
            search_query = {
                "size": size * 2,  # Get more results to allow for better filtering
                "knn": {
                    "field": "content_vector",
                    "query_vector": query_vector,
                    "k": size * 2,
                    "num_candidates": size * 5
                },
                "query": {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "name^4",
                                        "description^3", 
                                        "features^2",
                                        "searchable_content^1.5"
                                    ],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO"
                                }
                            },
                            {
                                "match_phrase": {
                                    "name": {
                                        "query": query,
                                        "boost": 5.0
                                    }
                                }
                            }
                        ]
                    }
                },
                "_source": {"excludes": ["content_vector"]}
            }
            
            # Add filters if provided
            if filters:
                if "filter" not in search_query["query"]["bool"]:
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
                product["_similarity_score"] = hit["_score"]
                product["_index"] = hit["_index"]
                products.append(product)
            
            # Apply strict category filtering if categories are specified
            if categories and len(categories) > 0:
                # Only include products from specified categories
                filtered_products = []
                for product in products:
                    product_category = product.get('category', '').lower()
                    if product_category in [cat.lower() for cat in categories]:
                        filtered_products.append(product)
                
                products = filtered_products
                logger.info(f"🎯 Strict category filtering: {len(products)} products from specified categories")
            
            # Apply query-specific filtering to prioritize products containing the query
            if query and len(query.strip()) > 0:
                exact_match_products = []
                partial_match_products = []
                other_products = []
                
                query_lower = query.lower()
                query_words = [word.strip() for word in query_lower.split() if len(word.strip()) > 2]
                
                for product in products:
                    product_name = product.get('name', '').lower()
                    product_desc = product.get('description', '').lower()
                    product_content = product.get('searchable_content', '').lower()
                    
                    # Check for exact phrase match
                    if query_lower in product_name:
                        exact_match_products.append(product)
                    # Check for all query words present
                    elif all(word in product_name or word in product_desc for word in query_words):
                        partial_match_products.append(product)
                    # Check for any query words present
                    elif any(word in product_name or word in product_desc or word in product_content for word in query_words):
                        other_products.append(product)
                    else:
                        # No query match, but might be semantically similar
                        other_products.append(product)
                
                # Prioritize: exact matches first, then partial matches, then others
                products = exact_match_products + partial_match_products + other_products
                
                logger.info(f"🎯 Query filtering: {len(exact_match_products)} exact matches, {len(partial_match_products)} partial matches, {len(other_products)} others")
            
            # Limit to requested size
            products = products[:size]
            
            logger.info(f"🔍 Vector search returned {len(products)} products for query: '{query}'")
            if products:
                # Log product names for debugging
                product_names = [p.get('name', 'Unknown')[:50] for p in products[:3]]
                logger.info(f"   Top 3 products: {product_names}")
            
            return products
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def _balanced_category_search(
        self, 
        query_vector: List[float], 
        query: str, 
        categories: List[str], 
        total_size: int, 
        filters: Optional[Dict] = None,
        hybrid_weight: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Perform balanced search across multiple categories to ensure diverse results"""
        try:
            # Calculate how many results to get from each category
            results_per_category = max(2, total_size // len(categories))  # At least 2 per category
            remainder = total_size % len(categories)
            
            logger.info(f"🎯 Balanced search: {results_per_category} products per category + {remainder} extra")
            
            all_products = []
            category_results = {}
            
            # Search each category separately
            for i, category in enumerate(categories):
                # Get index name for this category
                index_name = CATEGORY_INDEX_MAP.get(category, DEFAULT_PRODUCTS_INDEX)
                
                # Check if this category should get extra results
                category_size = results_per_category
                if i < remainder:
                    category_size += 1
                
                try:
                    # Build the search query for this specific category
                    search_query = {
                        "size": category_size,
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
                            "fields": [
                                "name^4",                    
                                "description^3",             
                                "features^2",                
                                "use_cases^2",               
                                "tags^2",                    
                                "category^1.5",              
                                "searchable_content^1.5"     
                            ],
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                            "operator": "or"
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
                    
                    # Execute search for this category
                    response = await self.client.search(index=index_name, body=search_query)
                    
                    # Process results for this category
                    category_products = []
                    for hit in response["hits"]["hits"]:
                        product = hit["_source"]
                        product["_score"] = hit["_score"]
                        product["_similarity_score"] = hit["_score"]
                        product["_index"] = hit["_index"]
                        product["_category_search"] = category  # Mark which category search this came from
                        category_products.append(product)
                    
                    category_results[category] = len(category_products)
                    all_products.extend(category_products)
                    
                    logger.info(f"   📦 {category}: {len(category_products)} products from {index_name}")
                    
                except Exception as e:
                    logger.warning(f"Failed to search category {category} ({index_name}): {e}")
                    category_results[category] = 0
            
            # Sort all results by similarity score to maintain quality ranking
            all_products.sort(key=lambda x: x.get('_similarity_score', 0), reverse=True)
            
            # Limit to requested total size
            final_products = all_products[:total_size]
            
            logger.info(f"🎯 Balanced search complete: {len(final_products)} total products")
            logger.info(f"   Category breakdown: {category_results}")
            
            # Log final diversity
            if final_products:
                final_categories = [p.get('category', 'unknown') for p in final_products]
                category_counts = {cat: final_categories.count(cat) for cat in set(final_categories)}
                logger.info(f"   Final category distribution: {category_counts}")
            
            return final_products
            
        except Exception as e:
            logger.error(f"Balanced category search failed: {e}")
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
            
            # Add a more precise query for exact term matching
            exact_query = {
                "bool": {
                    "should": [
                        {"match_phrase": {"name": {"query": query, "boost": 5.0}}},
                        {"match_phrase": {"description": {"query": query, "boost": 3.0}}},
                        {"match_phrase": {"searchable_content": {"query": query, "boost": 2.0}}}
                    ]
                }
            }
            
            if hybrid_weight > 0:
                # Hybrid search with both exact and fuzzy matching
                search_query["query"]["bool"]["should"].extend([
                    {"constant_score": {"filter": knn_query, "boost": 1.0 - hybrid_weight}},
                    {"constant_score": {"filter": exact_query, "boost": hybrid_weight * 2}},  # Higher boost for exact matches
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
            data_dir = Path(settings.data_dir)
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
        
        try:
            # Use LLM-powered category extraction
            logger.info("🧠 Attempting LLM-powered category analysis...")
            categories = await self._extract_categories_with_llm(requirements)
            
            # If no categories found, try the fallback method
            if not categories:
                logger.info("🔄 LLM analysis returned no categories, using enhanced fallback...")
                categories = await self._extract_categories_fallback(requirements)
            
        except Exception as e:
            logger.warning(f"LLM-powered category extraction failed: {e}")
            logger.info("🔄 Using enhanced fallback category analysis...")
            categories = await self._extract_categories_fallback(requirements)
        
        # If still no categories, default to core categories based on common use cases
        if not categories and not settings.disable_automatic_category_defaults:
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
                logger.info("🎯 Applied workstation default categories")
            elif any(term in combined_text for term in ['gaming', 'game', 'fps']):
                categories = ['video-card', 'cpu', 'memory', 'monitor']
                logger.info("🎯 Applied gaming default categories")
            elif any(term in combined_text for term in ['storage', 'nas', 'file']):
                categories = ['internal-hard-drive', 'external-hard-drive']
                logger.info("🎯 Applied storage default categories")
            elif any(term in combined_text for term in ['office', 'business', 'productivity']):
                categories = ['cpu', 'memory', 'monitor']
                logger.info("🎯 Applied office default categories")
            else:
                # Default to most common categories
                categories = ['cpu', 'memory', 'internal-hard-drive']
                logger.info("🎯 Applied general default categories")
        elif not categories and settings.disable_automatic_category_defaults:
            logger.info("ℹ️ Automatic category defaults disabled (DISABLE_AUTOMATIC_CATEGORY_DEFAULTS=true)")
            return []  # Return empty list instead of None
        
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
                
                # Try to extract categories if available (FIX: Add await)
                categories = await self._extract_categories_from_requirements(query_body)
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

    def _get_data_structure_info(self) -> DataStructureInfo:
        """Get comprehensive data structure information for AI query generation"""
        return DataStructureInfo(
            available_categories=list(FIELD_MAP.keys()),
            category_fields=FIELD_MAP,
            searchable_fields=[
                "name", "description", "category", "features", "use_cases", 
                "tags", "specifications", "compatibility", "warranty"
            ],
            field_importance={
                "name": 4.0,
                "description": 3.0,
                "features": 2.0,
                "use_cases": 2.0,
                "tags": 2.0,
                "category": 1.5,
                "searchable_content": 1.5
            },
            index_mapping=CATEGORY_INDEX_MAP
        )

    async def generate_dynamic_query(
        self, 
        requirements: Dict[str, Any],
        search_type: str = "hybrid"
    ) -> DynamicQueryGeneration:
        """Generate dynamic queries using AI based on data structure and requirements"""
        
        if not self.llm_provider:
            logger.warning("No LLM provider available for dynamic query generation")
            return self._fallback_query_generation(requirements, search_type)
        
        try:
            # Get data structure information
            data_structure = self._get_data_structure_info()
            
            # Build context for AI query generation
            context_parts = []
            
            # Add requirements context
            if requirements.get('semantic_query'):
                context_parts.append(f"Semantic Query: {requirements['semantic_query']}")
            
            if requirements.get('use_case'):
                context_parts.append(f"Use Case: {requirements['use_case']}")
            
            if requirements.get('technical_requirements'):
                tech_reqs = requirements['technical_requirements']
                if isinstance(tech_reqs, list):
                    context_parts.append(f"Technical Requirements: {', '.join(str(req) for req in tech_reqs)}")
                else:
                    context_parts.append(f"Technical Requirements: {tech_reqs}")
            
            if requirements.get('business_requirements'):
                business_reqs = requirements['business_requirements']
                if isinstance(business_reqs, list):
                    context_parts.append(f"Business Requirements: {', '.join(str(req) for req in business_reqs)}")
                else:
                    context_parts.append(f"Business Requirements: {business_reqs}")
            
            if requirements.get('search_terms'):
                search_terms = requirements['search_terms']
                if isinstance(search_terms, list):
                    context_parts.append(f"Search Terms: {', '.join(str(term) for term in search_terms)}")
                else:
                    context_parts.append(f"Search Terms: {search_terms}")
            
            requirements_text = "\n".join(context_parts)
            
            # Create AI prompt for dynamic query generation
            query_generation_prompt = f"""You are an expert search query optimizer for a B2B technology product database. Generate optimized search queries based on the customer requirements and our data structure.

CUSTOMER REQUIREMENTS:
{requirements_text}

DATA STRUCTURE INFORMATION:
Available Categories: {', '.join(data_structure.available_categories)}
Searchable Fields: {', '.join(data_structure.searchable_fields)}

SEARCH STRATEGY: {search_type}

TASK:
Generate a search query strategy with these components:

1. SEMANTIC_QUERY: Natural language query for vector search (keep simple and clear)
2. KEYWORD_QUERY: Basic Elasticsearch query structure (use simple field matching)
3. CATEGORY_FILTERS: List of most relevant product categories
4. FIELD_PRIORITIES: Basic field boost values (name: 4.0, description: 3.0, etc.)
5. SEARCH_STRATEGY: One of: 'hybrid', 'vector_only', 'keyword_only'
6. CONFIDENCE: Confidence score between 0.0 and 1.0
7. REASONING: Brief explanation of strategy
8. SUGGESTED_FILTERS: Empty object {{}} (no complex filters)

CRITICAL JSON FORMATTING REQUIREMENTS:
- Use ONLY simple string values, no special characters
- Ensure all strings are properly quoted with double quotes
- Use simple field names: name, description, features, category
- Avoid complex nested structures in keyword_query
- Keep all JSON properly formatted and valid

EXAMPLE KEYWORD_QUERY STRUCTURE:
{{
  "query": {{
    "bool": {{
      "should": [
        {{"match": {{"name": {{"query": "gaming", "boost": 4.0}}}}}},
        {{"match": {{"description": {{"query": "gaming", "boost": 3.0}}}}}}
      ]
    }}
  }},
  "size": 20
}}

IMPORTANT: Ensure all JSON is properly formatted with correct quotes and braces. Use simple, clean strings without special characters."""

            try:
                # Use Pydantic function calling for structured response
                logger.info("🧠 Using AI for dynamic query generation...")
                dynamic_query = await self.llm_provider.generate_structured_response(
                    [AIMessage(role="user", content=query_generation_prompt)],
                    DynamicQueryGeneration
                )
                
                logger.info(f"🧠 AI Query Generation:")
                logger.info(f"   Search Strategy: {dynamic_query.search_strategy}")
                logger.info(f"   Categories: {dynamic_query.category_filters}")
                logger.info(f"   Confidence: {dynamic_query.confidence:.1%}")
                logger.info(f"   Reasoning: {dynamic_query.reasoning}")
                
                return dynamic_query
                    
            except Exception as e:
                logger.warning(f"AI query generation failed: {e}")
                logger.info("🔄 Falling back to standard query generation...")
                return self._fallback_query_generation(requirements, search_type)
                
        except Exception as e:
            logger.error(f"Dynamic query generation failed: {e}")
            logger.info("🔄 Using fallback query generation...")
            return self._fallback_query_generation(requirements, search_type)

    def _fallback_query_generation(
        self, 
        requirements: Dict[str, Any], 
        search_type: str
    ) -> DynamicQueryGeneration:
        """Fallback query generation when AI is not available"""
        
        # Build semantic query - preserve exact terms from requirements
        semantic_query = requirements.get('semantic_query', '')
        if not semantic_query:
            # Use technical requirements if available
            tech_reqs = requirements.get('technical_requirements', [])
            if tech_reqs:
                semantic_query = ' '.join([str(req) for req in tech_reqs])
            else:
                use_case = requirements.get('use_case', 'business solution')
                semantic_query = f"{use_case} technology solution"
        
        # Extract the actual search query from semantic_query or technical_requirements
        actual_query = semantic_query
        if not actual_query and requirements.get('technical_requirements'):
            tech_reqs = requirements.get('technical_requirements', [])
            if isinstance(tech_reqs, list):
                actual_query = ' '.join([str(req) for req in tech_reqs])
            else:
                actual_query = str(tech_reqs)
        
        # If still no query, use a fallback
        if not actual_query:
            actual_query = "business solution"
        
        # Create a simple, effective Elasticsearch query that uses the actual search terms
        keyword_query = {
            "query": {
                "bool": {
                    "should": [
                        # Exact phrase matching gets highest boost
                        {"match_phrase": {"name": {"query": actual_query, "boost": 6.0}}},
                        {"match_phrase": {"description": {"query": actual_query, "boost": 4.0}}},
                        # Regular matching with good boosts
                        {"match": {"name": {"query": actual_query, "boost": 4.0}}},
                        {"match": {"description": {"query": actual_query, "boost": 3.0}}},
                        {"match": {"features": {"query": actual_query, "boost": 2.0}}},
                        {"match": {"searchable_content": {"query": actual_query, "boost": 1.5}}}
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": 20
        }
        
        # Get categories from requirements or use defaults
        categories = requirements.get('recommended_categories', [])
        if not categories:
            categories = requirements.get('product_categories', [])
        if not categories:
            # Infer categories from the query content
            query_lower = actual_query.lower()
            if any(term in query_lower for term in ['i9', 'i7', 'i5', 'ryzen', 'cpu', 'processor']):
                categories = ['cpu']
            elif any(term in query_lower for term in ['rtx', 'gtx', 'graphics', 'video card', 'gpu']):
                categories = ['video-card']
            elif any(term in query_lower for term in ['ram', 'memory', 'ddr4', 'ddr5']):
                categories = ['memory']
            elif any(term in query_lower for term in ['monitor', 'display', '4k', '1440p']):
                categories = ['monitor']
            elif any(term in query_lower for term in ['ssd', 'hdd', 'storage', 'drive']):
                categories = ['internal-hard-drive']
            else:
                # Use default categories based on use case
                use_case = requirements.get('use_case', '').lower()
                if 'gaming' in use_case:
                    categories = ['video-card', 'cpu', 'memory']
                elif 'workstation' in use_case:
                    categories = ['cpu', 'video-card', 'memory', 'internal-hard-drive']
                elif 'storage' in use_case:
                    categories = ['internal-hard-drive', 'external-hard-drive']
                else:
                    categories = ['cpu', 'memory', 'internal-hard-drive']
        
        # Determine field priorities based on query content
        field_priorities = {
            "name": 4.0,
            "description": 3.0,
            "features": 2.0,
            "category": 1.5
        }
        
        # Adjust priorities based on query content
        query_lower = actual_query.lower()
        if any(term in query_lower for term in ['i9', 'i7', 'i5', 'ryzen', 'cpu']):
            field_priorities.update({
                "name": 6.0,  # Higher boost for CPU queries
                "core_count": 3.5,
                "core_clock": 3.0,
                "boost_clock": 2.5
            })
        elif any(term in query_lower for term in ['gaming', 'fps']):
            field_priorities.update({
                "chipset": 3.5,
                "core_clock": 3.0,
                "memory": 2.5
            })
        elif any(term in query_lower for term in ['workstation', 'professional']):
            field_priorities.update({
                "core_count": 3.5,
                "capacity": 3.0,
                "speed": 2.5
            })
        elif any(term in query_lower for term in ['storage', 'drive']):
            field_priorities.update({
                "capacity": 4.0,
                "price_per_gb": 3.5,
                "interface": 3.0
            })
        
        return DynamicQueryGeneration(
            semantic_query=semantic_query,
            keyword_query=keyword_query,
            category_filters=categories,
            field_priorities=field_priorities,
            search_strategy=search_type,
            confidence=0.7,  # Higher confidence since we're using exact query terms
            reasoning=f"Using direct query terms '{actual_query}' with category-specific optimization",
            suggested_filters={}
        )

    async def vector_search_products_with_ai_query(
        self, 
        requirements: Dict[str, Any],
        size: int = 10,
        search_type: str = "hybrid"
    ) -> List[Dict[str, Any]]:
        """Perform vector search using AI-generated dynamic queries"""
        
        try:
            # Generate dynamic query using AI
            dynamic_query = await self.generate_dynamic_query(requirements, search_type)
            
            logger.info(f"🧠 AI-Generated Query:")
            logger.info(f"   Semantic Query: {dynamic_query.semantic_query}")
            logger.info(f"   Search Strategy: {dynamic_query.search_strategy}")
            logger.info(f"   Categories: {dynamic_query.category_filters}")
            logger.info(f"   Confidence: {dynamic_query.confidence:.1%}")
            
            # Use the AI-generated semantic query
            query = dynamic_query.semantic_query
            categories = dynamic_query.category_filters if dynamic_query.category_filters else None
            
            # Perform vector search with AI-generated query
            return await self.vector_search_products(
                query=query,
                size=size,
                categories=categories,
                hybrid_weight=0.2  # Default hybrid weight
            )
            
        except Exception as e:
            logger.error(f"AI-powered vector search failed: {e}")
            # Fallback to standard search
            return await self.vector_search_products(
                query=requirements.get('semantic_query', 'business solution'),
                size=size
            )

    async def elasticsearch_search_with_ai_query(
        self, 
        requirements: Dict[str, Any],
        size: int = 20
    ) -> List[Dict[str, Any]]:
        """Perform Elasticsearch search using AI-generated dynamic queries"""
        
        try:
            # Generate dynamic query using AI
            dynamic_query = await self.generate_dynamic_query(requirements, "keyword_only")
            
            logger.info(f"🔍 AI-Generated Elasticsearch Query:")
            logger.info(f"   Search Strategy: {dynamic_query.search_strategy}")
            logger.info(f"   Field Priorities: {dynamic_query.field_priorities}")
            logger.info(f"   Confidence: {dynamic_query.confidence:.1%}")
            
            # Use the AI-generated keyword query
            query = dynamic_query.keyword_query
            query["size"] = size
            
            # Add filters if suggested by AI
            if dynamic_query.suggested_filters:
                if "query" not in query:
                    query["query"] = {}
                if "bool" not in query["query"]:
                    query["query"]["bool"] = {}
                if "filter" not in query["query"]["bool"]:
                    query["query"]["bool"]["filter"] = []
                
                for field, value in dynamic_query.suggested_filters.items():
                    if isinstance(value, list):
                        query["query"]["bool"]["filter"].append({"terms": {field: value}})
                    else:
                        query["query"]["bool"]["filter"].append({"term": {field: value}})
            
            # Perform search using the standard search method
            results = await self.search_products(query)
            
            # Add AI query metadata
            for product in results:
                product['ai_query_generated'] = True
                product['ai_confidence'] = dynamic_query.confidence
                product['ai_search_strategy'] = dynamic_query.search_strategy
            
            return results
            
        except Exception as e:
            logger.error(f"AI-powered Elasticsearch search failed: {e}")
            # Fallback to standard search
            return await self.search_products({
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"name": {"query": "business solution", "boost": 2.0}}},
                            {"match": {"description": {"query": "business solution", "boost": 1.0}}}
                        ]
                    }
                },
                "size": size
            })

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
• laptop: Laptops, portable computers for mobility and convenience

ANALYSIS GUIDELINES:
1. Focus on categories that directly solve the customer's stated needs
2. Consider the primary use case and industry context
3. Prioritize essential components over accessories
4. Consider complementary products that work together

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
        
        # Add LLM context if available
        llm_context = requirements.get('llm_context', {})
        if llm_context.get('primary_need'):
            text_parts.append(str(llm_context['primary_need']))
        if llm_context.get('business_context'):
            text_parts.append(str(llm_context['business_context']))
        if llm_context.get('technical_requirements'):
            if isinstance(llm_context['technical_requirements'], list):
                text_parts.extend([str(req) for req in llm_context['technical_requirements']])
            else:
                text_parts.append(str(llm_context['technical_requirements']))
        
        text = " ".join(text_parts).lower()
        
        logger.info(f"🔍 Fallback category analysis for text: {text[:200]}...")
        
        # Enhanced pattern matching with more specific keywords
        
        # Storage solutions
        if any(word in text for word in ['storage', 'nas', 'file sharing', 'raid', 'backup', 'ssd', 'hdd', 'nvme', 'drive']):
            categories.update(['internal-hard-drive', 'external-hard-drive'])
            logger.info("🗂️ Detected storage needs")
        
        # Gaming and graphics
        if any(word in text for word in ['gaming', '1440p', '4k gaming', 'fps', 'ray tracing', 'gpu', 'graphics', 'rtx', 'radeon']):
            categories.update(['video-card', 'cpu', 'memory', 'monitor'])
            logger.info("🎮 Detected gaming needs")
        
        # Professional workstation
        if any(word in text for word in ['workstation', 'professional', 'video editing', '3d rendering', 'cad', 'autocad', 'blender']):
            categories.update(['video-card', 'cpu', 'memory', 'internal-hard-drive'])
            logger.info("💼 Detected workstation needs")
        
        # AI/ML and compute
        if any(word in text for word in ['ai', 'ml', 'machine learning', 'training', 'dataset', 'tensorflow', 'pytorch', 'cuda']):
            categories.update(['video-card', 'cpu', 'memory', 'internal-hard-drive'])
            logger.info("🤖 Detected AI/ML needs")
        
        # Display and monitors
        if any(word in text for word in ['monitor', 'display', 'screen', '27-inch', '32-inch', '4k', '1440p', 'ultrawide']):
            categories.add('monitor')
            logger.info("🖥️ Detected monitor needs")
        
        # Productivity and office
        if any(word in text for word in ['office', 'productivity', 'business', 'excel', 'word', 'spreadsheet']):
            categories.update(['cpu', 'memory', 'monitor'])
            logger.info("📊 Detected office/productivity needs")
        
        # Input devices
        if any(word in text for word in ['keyboard', 'typing', 'mechanical', 'wireless keyboard']):
            categories.add('keyboard')
            logger.info("⌨️ Detected keyboard needs")
        
        if any(word in text for word in ['mouse', 'pointing', 'trackball', 'wireless mouse']):
            categories.add('mouse')
            logger.info("🖱️ Detected mouse needs")
        
        # Audio devices
        if any(word in text for word in ['headphones', 'headset', 'audio', 'microphone', 'streaming']):
            categories.add('headphones')
            logger.info("🎧 Detected audio needs")
        
        if any(word in text for word in ['speakers', 'sound system', 'multimedia']):
            categories.add('speakers')
            logger.info("🔊 Detected speaker needs")
        
        # Webcam and communication
        if any(word in text for word in ['webcam', 'camera', 'video call', 'conference', 'zoom', 'teams']):
            categories.add('webcam')
            logger.info("📹 Detected webcam needs")
        
        # Networking
        if any(word in text for word in ['wifi', 'wireless', 'network card', 'ethernet', 'networking']):
            categories.update(['wireless-network-card', 'wired-network-card'])
            logger.info("🌐 Detected networking needs")
        
        # Power management
        if any(word in text for word in ['ups', 'backup power', 'power supply', 'psu']):
            categories.add('power-supply')
            if 'ups' in text or 'backup power' in text:
                categories.add('ups')
            logger.info("⚡ Detected power needs")
        
        # System building
        if any(word in text for word in ['build', 'custom', 'system', 'motherboard', 'case', 'cooling']):
            categories.update(['motherboard', 'case', 'cpu-cooler'])
            logger.info("🔧 Detected system building needs")
        
        # Laptops
        if any(word in text for word in ['laptop', 'portable', 'mobile', 'notebook']):
            categories.add('laptop')
            logger.info("💻 Detected laptop needs")
        
        # If no specific categories found, provide sensible defaults based on context
        if not categories:
            logger.info("🔄 No specific categories detected, using default business categories")
            categories.update(['cpu', 'memory', 'internal-hard-drive'])
        
        final_categories = list(categories)
        logger.info(f"🎯 Fallback analysis selected categories: {final_categories}")
        
        return final_categories

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