import json
import logging
from typing import List, Dict, Any, Optional
from elasticsearch import AsyncElasticsearch
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)

class ElasticsearchService:
    def __init__(self):
        self.client = AsyncElasticsearch(
            [settings.elasticsearch_url],
            verify_certs=False,
            ssl_show_warn=False,
            # Force API version compatibility
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'}
        )
        self.products_index = settings.elasticsearch_index_products
        self.solutions_index = settings.elasticsearch_index_solutions
    
    async def initialize(self):
        """Initialize Elasticsearch indices and load data"""
        try:
            await self.test_connection()
            await self.create_indices()
            
            # Only load data based on configuration
            if not settings.skip_data_loading:
                if settings.force_reload_data:
                    await self.reindex_all_data()
                else:
                    await self.load_initial_data()
                
            logger.info("Elasticsearch initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch: {e}")
            raise
    
    async def test_connection(self):
        """Test Elasticsearch connection"""
        try:
            info = await self.client.info()
            logger.info(f"Elasticsearch connected: {info.get('cluster_name', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {e}")
            raise
    
    async def create_indices(self):
        """Create Elasticsearch indices with mappings"""
        
        # Products index mapping
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
                    "support_level": {"type": "keyword"}
                }
            }
        }
        
        # Solutions index mapping  
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
                    "requirements": {"type": "text", "analyzer": "standard"}
                }
            }
        }
        
        # Create indices
        try:
            exists = await self.client.indices.exists(index=self.products_index)
            if not exists:
                await self.client.indices.create(index=self.products_index, **products_mapping)
                logger.info(f"Created products index: {self.products_index}")
            else:
                logger.info(f"Products index already exists: {self.products_index}")
        except Exception as e:
            logger.warning(f"Products index creation issue: {e}")
        
        try:
            exists = await self.client.indices.exists(index=self.solutions_index)
            if not exists:
                await self.client.indices.create(index=self.solutions_index, **solutions_mapping)
                logger.info(f"Created solutions index: {self.solutions_index}")
            else:
                logger.info(f"Solutions index already exists: {self.solutions_index}")
        except Exception as e:
            logger.warning(f"Solutions index creation issue: {e}")
    
    async def load_initial_data(self):
        """Load initial product and solution data from JSON files"""
        try:
            # Check if data already exists
            products_count = await self.client.count(index=self.products_index)
            solutions_count = await self.client.count(index=self.solutions_index)
            
            print(f"📊 Current data: {products_count['count']} products, {solutions_count['count']} solutions")
            
            if products_count['count'] > 0 and solutions_count['count'] > 0:
                logger.info(f"Data already exists: {products_count['count']} products, {solutions_count['count']} solutions. Skipping reload.")
                return
            
            # Only load if no data exists
            logger.info("No existing data found, loading initial data...")
            
            # Load products from JSON files
            data_dir = Path("Data/json")
            products_loaded = 0
            
            if data_dir.exists() and any(data_dir.glob("*.json")):
                logger.info(f"Loading products from {data_dir}")
                products_loaded = await self._load_products_from_json(data_dir)
                
                if products_loaded == 0:
                    logger.warning("No products loaded from JSON files, loading sample data")
                    await self._load_sample_products()
                    products_loaded = 3  # Sample products count
                else:
                    logger.info(f"Successfully loaded {products_loaded} products from JSON files")
            else:
                logger.warning(f"Data directory not found or empty: {data_dir}")
                await self._load_sample_products()
                products_loaded = 3  # Sample products count
            
            # Load solutions only if none exist
            solutions_response = await self.client.count(index=self.solutions_index)
            if solutions_response['count'] == 0:
                await self._load_sample_solutions()
            
            # Refresh indices to make data immediately available
            await self.client.indices.refresh(index=self.products_index)
            await self.client.indices.refresh(index=self.solutions_index)
            
            print(f"✅ Data loading complete: {products_loaded} products loaded")
            
        except Exception as e:
            logger.warning(f"Could not load initial data: {e}")
            # Fallback to sample data only if indices are empty
            try:
                products_count = await self.client.count(index=self.products_index)
                if products_count['count'] == 0:
                    await self._load_sample_products()
                
                solutions_count = await self.client.count(index=self.solutions_index)
                if solutions_count['count'] == 0:
                    await self._load_sample_solutions()
                
                # Refresh indices
                await self.client.indices.refresh(index=self.products_index)
                await self.client.indices.refresh(index=self.solutions_index)
            except:
                logger.error("Failed to load any data")
    
    async def _load_sample_products(self):
        """Load sample products for testing"""
        sample_products = [
            {
                "id": "workstation-pro-1",
                "name": "Workstation Pro Professional",
                "category": "workstation",
                "subcategory": "professional",
                "description": "High-performance workstation for professional use",
                "specifications": {
                    "cpu": "Intel Xeon W-2295",
                    "ram": "32GB DDR4",
                    "storage": "1TB NVMe SSD",
                    "gpu": "NVIDIA Quadro RTX 4000"
                },
                "price": 3499.99,
                "currency": "USD",
                "availability": True,
                "tags": ["workstation", "professional", "high-performance"],
                "features": "High-performance CPU, Professional graphics, Fast storage",
                "use_cases": "CAD, 3D modeling, video editing, engineering",
                "target_industries": ["engineering", "media", "architecture"],
                "compatibility": "Windows 11 Pro, Linux",
                "warranty": "3 years",
                "support_level": "enterprise"
            },
            {
                "id": "business-nas-4tb",
                "name": "Business NAS 4TB",
                "category": "storage",
                "subcategory": "network_storage",
                "description": "4TB Network Attached Storage for small business",
                "specifications": {
                    "capacity": "4TB",
                    "raid": "RAID 1",
                    "connectivity": "Gigabit Ethernet",
                    "bays": 2
                },
                "price": 899.99,
                "currency": "USD",
                "availability": True,
                "tags": ["storage", "nas", "business", "backup"],
                "features": "RAID protection, Remote access, Automatic backup",
                "use_cases": "File sharing, backup, remote access",
                "target_industries": ["general", "small_business"],
                "compatibility": "Windows, Mac, Linux",
                "warranty": "2 years",
                "support_level": "standard"
            },
            {
                "id": "server-rack-2u",
                "name": "Enterprise Server 2U Rack",
                "category": "server",
                "subcategory": "rack_server",
                "description": "2U rack-mounted server for enterprise applications",
                "specifications": {
                    "cpu": "Dual Intel Xeon Gold 6248R",
                    "ram": "128GB DDR4 ECC",
                    "storage": "8TB SAS RAID 10",
                    "networking": "Dual 10GbE ports"
                },
                "price": 8999.99,
                "currency": "USD",
                "availability": True,
                "tags": ["server", "enterprise", "rack", "high-availability"],
                "features": "Dual redundant power, Hot-swappable drives, Remote management",
                "use_cases": "Database hosting, virtualization, enterprise applications",
                "target_industries": ["enterprise", "healthcare", "finance"],
                "compatibility": "Windows Server, Linux, VMware",
                "warranty": "5 years",
                "support_level": "enterprise"
            }
        ]
        
        for product in sample_products:
            await self.index_product(product)
        
        logger.info(f"Loaded {len(sample_products)} sample products")
    
    async def _load_sample_solutions(self):
        """Load sample solutions for testing"""
        sample_solutions = [
            {
                "id": "small-office-setup",
                "name": "Small Office Complete Setup",
                "description": "Complete technology solution for small offices (5-15 employees)",
                "use_case": "Small business productivity and collaboration",
                "industry": ["general", "professional_services", "consulting"],
                "company_size": "small",
                "budget_range": "10000-25000",
                "components": [
                    {"type": "workstation", "quantity": 5, "name": "Workstation Pro Professional"},
                    {"type": "storage", "quantity": 1, "name": "Business NAS 4TB"}
                ],
                "total_price": 18399.95,
                "implementation_time": "1-2 weeks",
                "benefits": "Complete productivity suite, secure file sharing, professional support",
                "requirements": "Standard office space, internet connection"
            },
            {
                "id": "enterprise-infrastructure",
                "name": "Enterprise Infrastructure Solution",
                "description": "Scalable enterprise infrastructure for large organizations",
                "use_case": "Enterprise data center and application hosting",
                "industry": ["enterprise", "healthcare", "finance", "government"],
                "company_size": "large",
                "budget_range": "50000-100000",
                "components": [
                    {"type": "server", "quantity": 3, "name": "Enterprise Server 2U Rack"},
                    {"type": "storage", "quantity": 2, "name": "Business NAS 4TB"}
                ],
                "total_price": 28799.95,
                "implementation_time": "2-4 weeks",
                "benefits": "High availability, scalable performance, enterprise support",
                "requirements": "Data center rack space, redundant power, network infrastructure"
            }
        ]
        
        for solution in sample_solutions:
            await self.index_solution(solution)
        
        logger.info(f"Loaded {len(sample_solutions)} sample solutions")
    
    async def _load_products_from_json(self, data_dir: Path) -> int:
        """Load products from JSON files in data directory with enhanced processing"""
        product_files = list(data_dir.glob("*.json"))
        loaded_count = 0
        
        print(f"📁 Found {len(product_files)} JSON files to process")
        
        for file_path in product_files:
            try:
                print(f"📄 Processing file: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                file_loaded = 0
                # Handle different JSON structures
                if isinstance(data, list):
                    for item in data:
                        if self._is_valid_product(item):
                            processed_product = self._process_product_data(item)
                            await self.index_product(processed_product)
                            loaded_count += 1
                            file_loaded += 1
                elif isinstance(data, dict):
                    if self._is_valid_product(data):
                        processed_product = self._process_product_data(data)
                        await self.index_product(processed_product)
                        loaded_count += 1
                        file_loaded += 1
                    elif 'products' in data:
                        # Handle nested structure like {"products": [...]}
                        for item in data['products']:
                            if self._is_valid_product(item):
                                processed_product = self._process_product_data(item)
                                await self.index_product(processed_product)
                                loaded_count += 1
                                file_loaded += 1
                            
                print(f"✅ Loaded {file_loaded} products from {file_path}")
            except Exception as e:
                print(f"❌ Failed to load products from {file_path}: {e}")
        
        print(f"📊 Total products loaded: {loaded_count}")
        return loaded_count

    def _is_valid_product(self, item: Dict[str, Any]) -> bool:
        """Check if item has minimum required fields for a product"""
        required_fields = ['name']  # Minimum requirement
        return all(field in item for field in required_fields)

    def _process_product_data(self, raw_product: Dict[str, Any]) -> Dict[str, Any]:
        """Process and normalize product data for Elasticsearch"""
        
        # Generate ID if missing
        if 'id' not in raw_product:
            raw_product['id'] = self._generate_product_id(raw_product)
        
        # Normalize category
        if 'category' not in raw_product:
            raw_product['category'] = self._infer_category(raw_product)
        
        # Ensure price is float
        if 'price' in raw_product:
            try:
                raw_product['price'] = float(raw_product['price'])
            except (ValueError, TypeError):
                raw_product['price'] = 0.0
        
        # Normalize tags
        if 'tags' not in raw_product:
            raw_product['tags'] = self._generate_tags(raw_product)
        elif isinstance(raw_product['tags'], str):
            raw_product['tags'] = [tag.strip() for tag in raw_product['tags'].split(',')]
        
        # Ensure boolean availability
        if 'availability' not in raw_product:
            raw_product['availability'] = True
        elif isinstance(raw_product['availability'], str):
            raw_product['availability'] = raw_product['availability'].lower() in ['true', 'yes', 'available', '1']
        
        # Generate search-friendly fields
        raw_product['search_text'] = self._build_search_text(raw_product)
        
        return raw_product

    def _generate_product_id(self, product: Dict[str, Any]) -> str:
        """Generate a unique ID for products without one"""
        import hashlib
        name = product.get('name', 'unknown')
        category = product.get('category', 'general')
        text = f"{name}-{category}".lower().replace(' ', '-')
        # Add hash to ensure uniqueness
        hash_suffix = hashlib.md5(str(product).encode()).hexdigest()[:8]
        return f"{text}-{hash_suffix}"

    def _infer_category(self, product: Dict[str, Any]) -> str:
        """Infer product category from name and description"""
        name = product.get('name', '').lower()
        description = product.get('description', '').lower()
        text = f"{name} {description}"
        
        # Category mapping
        category_keywords = {
            'workstation': ['workstation', 'desktop', 'pc', 'computer'],
            'server': ['server', 'rack', 'blade'],
            'storage': ['storage', 'nas', 'san', 'disk', 'drive', 'raid'],
            'networking': ['switch', 'router', 'firewall', 'network', 'ethernet'],
            'monitor': ['monitor', 'display', 'screen'],
            'software': ['software', 'license', 'application', 'program']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                return category
        
        return 'general'

    def _generate_tags(self, product: Dict[str, Any]) -> List[str]:
        """Generate relevant tags for better searchability"""
        tags = []
        
        # Add category as tag
        if 'category' in product:
            tags.append(product['category'])
        
        # Extract from name
        name = product.get('name', '').lower()
        if 'pro' in name or 'professional' in name:
            tags.append('professional')
        if 'enterprise' in name:
            tags.append('enterprise')
        if 'business' in name:
            tags.append('business')
        
        # Extract from specifications
        specs = product.get('specifications', {})
        if isinstance(specs, dict):
            for key, value in specs.items():
                if isinstance(value, str):
                    if 'ssd' in value.lower():
                        tags.append('ssd')
                    if 'raid' in value.lower():
                        tags.append('raid')
                    if 'intel' in value.lower():
                        tags.append('intel')
                    if 'amd' in value.lower():
                        tags.append('amd')
        
        return list(set(tags))  # Remove duplicates

    def _build_search_text(self, product: Dict[str, Any]) -> str:
        """Build comprehensive search text for better matching"""
        search_parts = []
        
        # Core fields
        for field in ['name', 'description', 'features', 'use_cases']:
            if field in product and product[field]:
                search_parts.append(str(product[field]))
        
        # Specifications
        specs = product.get('specifications', {})
        if isinstance(specs, dict):
            for key, value in specs.items():
                search_parts.append(f"{key} {value}")
        
        # Tags
        tags = product.get('tags', [])
        if tags:
            search_parts.extend(tags)
        
        return ' '.join(search_parts).lower()
    
    async def index_product(self, product: Dict[str, Any]):
        """Index a single product"""
        try:
            await self.client.index(
                index=self.products_index,
                id=product.get('id'),
                document=product
            )
        except Exception as e:
            logger.error(f"Failed to index product {product.get('id')}: {e}")
    
    async def index_solution(self, solution: Dict[str, Any]):
        """Index a single solution"""
        try:
            await self.client.index(
                index=self.solutions_index,
                id=solution.get('id'),
                document=solution
            )
        except Exception as e:
            logger.error(f"Failed to index solution {solution.get('id')}: {e}")
    
    async def search_products(self, query: str = "", size: int = 10, category: str = None) -> List[Dict]:
        """Search products with improved handling for empty queries"""
        
        search_body = {
            "size": size,
            "sort": [{"_score": {"order": "desc"}}]
        }
        
        if not query or query.strip() == "":
            # For empty queries, return random sample of products
            search_body["query"] = {"match_all": {}}
            # Add random scoring for variety
            search_body["query"] = {
                "function_score": {
                    "query": {"match_all": {}},
                    "random_score": {},
                    "boost_mode": "replace"
                }
            }
            print(f"🔍 Empty query - returning random sample of {size} products")
        else:
            # For non-empty queries, use multi-match
            search_body["query"] = {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "description^2", "category", "tags", "features"],
                    "fuzziness": "AUTO"
                }
            }
            print(f"🔍 Searching for: '{query}'")
        
        # Add category filter if specified
        if category:
            if "bool" not in search_body["query"]:
                search_body["query"] = {
                    "bool": {
                        "must": [search_body["query"]],
                        "filter": []
                    }
                }
            search_body["query"]["bool"]["filter"].append({
                "term": {"category": category}
            })
        
        try:
            print(f"🔍 Executing search with body: {json.dumps(search_body, indent=2)}")
            response = await self.client.search(index=self.products_index, **search_body)
            
            results = []
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                product["_score"] = hit.get("_score", 0)
                results.append(product)
            
            print(f"✅ Search returned {len(results)} products")
            return results
            
        except Exception as e:
            logger.error(f"Product search failed: {e}")
            print(f"❌ Search failed: {e}")
            return []

    async def get_random_products(self, size: int = 10) -> List[Dict]:
        """Get random products for testing/sampling"""
        try:
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
            
            response = await self.client.search(index=self.products_index, **search_body)
            
            results = []
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                results.append(product)
            
            print(f"✅ Retrieved {len(results)} random products")
            return results
            
        except Exception as e:
            logger.error(f"Random products retrieval failed: {e}")
            return []
    
    async def search_solutions(self, requirements: Dict[str, Any], size: int = 5) -> List[Dict]:
        """Search for solutions based on requirements"""
        search_body = {
            "query": {
                "bool": {
                    "should": []
                }
            },
            "size": size
        }
        
        # Build search based on requirements
        if requirements.get('use_case'):
            search_body["query"]["bool"]["should"].append({
                "match": {"use_case": requirements['use_case']}
            })
        
        if requirements.get('industry'):
            search_body["query"]["bool"]["should"].append({
                "terms": {"industry": [requirements['industry']]}
            })
        
        if requirements.get('company_size'):
            search_body["query"]["bool"]["should"].append({
                "term": {"company_size": requirements['company_size']}
            })
        
        if requirements.get('budget_range'):
            search_body["query"]["bool"]["should"].append({
                "term": {"budget_range": requirements['budget_range']}
            })
        
        # If no specific criteria, do a general search
        if not search_body["query"]["bool"]["should"]:
            search_body["query"] = {"match_all": {}}
        
        try:
            response = await self.client.search(index=self.solutions_index, **search_body)
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Solution search failed: {e}")
            return []
    
    async def close(self):
        """Close Elasticsearch connection"""
        await self.client.close()

    async def get_product_categories(self) -> List[str]:
        """Get all available product categories"""
        try:
            response = await self.client.search(
                index=self.products_index,
                body={
                    "size": 0,
                    "aggs": {
                        "categories": {
                            "terms": {
                                "field": "category",
                                "size": 100
                            }
                        }
                    }
                }
            )
            
            categories = []
            for bucket in response["aggregations"]["categories"]["buckets"]:
                categories.append(bucket["key"])
            
            return categories
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return []

    async def get_product_stats(self) -> Dict[str, Any]:
        """Get statistics about indexed products"""
        try:
            # Get total count
            count_response = await self.client.count(index=self.products_index)
            total_products = count_response['count']
            
            # Get category breakdown
            categories_response = await self.client.search(
                index=self.products_index,
                body={
                    "size": 0,
                    "aggs": {
                        "categories": {
                            "terms": {"field": "category", "size": 20}
                        },
                        "price_stats": {
                            "stats": {"field": "price"}
                        }
                    }
                }
            )
            
            categories = {}
            for bucket in categories_response["aggregations"]["categories"]["buckets"]:
                categories[bucket["key"]] = bucket["doc_count"]
            
            price_stats = categories_response["aggregations"]["price_stats"]
            
            return {
                "total_products": total_products,
                "categories": categories,
                "price_range": {
                    "min": price_stats.get("min", 0),
                    "max": price_stats.get("max", 0),
                    "avg": price_stats.get("avg", 0)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get product stats: {e}")
            return {"total_products": 0, "categories": {}, "price_range": {}}

    async def reindex_all_data(self):
        """Delete and recreate indices with fresh data"""
        try:
            # Delete existing indices
            await self.client.indices.delete(index=self.products_index, ignore=[404])
            await self.client.indices.delete(index=self.solutions_index, ignore=[404])
            
            # Recreate indices
            await self.create_indices()
            
            # Reload data
            await self.load_initial_data()
            
            logger.info("Successfully reindexed all data")
        except Exception as e:
            logger.error(f"Failed to reindex data: {e}")
            raise

    async def search_products_by_requirements(self, requirements: Dict[str, Any], size: int = 20) -> List[Dict]:
        """Search products based on extracted requirements with better fallback"""
        
        print(f"🔍 Elasticsearch: Searching with requirements: {requirements}")
        
        search_body = {
            "query": {
                "bool": {
                    "should": [],
                    "filter": []
                }
            },
            "size": size
        }
        
        # Category filtering
        categories = requirements.get('product_categories', [])
        if categories:
            search_body["query"]["bool"]["filter"].append({
                "terms": {"category": categories}
            })
            print(f"🏷️ Filtering by categories: {categories}")
        
        # Keywords matching - make this more flexible
        keywords = requirements.get('search_keywords', [])
        for keyword in keywords:
            search_body["query"]["bool"]["should"].append({
                "multi_match": {
                    "query": keyword,
                    "fields": ["name^3", "description^2", "tags", "features", "use_cases"],
                    "fuzziness": "AUTO",
                    "minimum_should_match": "50%"
                }
            })
        
        # Technical specs matching - improved
        tech_specs = requirements.get('technical_specs', {})
        if tech_specs:
            for spec_key, spec_value in tech_specs.items():
                # Search in specifications field and other relevant fields
                search_body["query"]["bool"]["should"].append({
                    "multi_match": {
                        "query": f"{spec_key} {spec_value}",
                        "fields": ["specifications.*", "description", "features"],
                        "boost": 2.0
                    }
                })
        
        # Business requirements matching
        business_reqs = requirements.get('business_requirements', {})
        if business_reqs:
            use_case = business_reqs.get('use_case', '')
            if use_case:
                search_body["query"]["bool"]["should"].append({
                    "multi_match": {
                        "query": use_case,
                        "fields": ["use_cases", "description", "features"],
                        "boost": 1.5
                    }
                })
        
        # If no specific criteria, search all products
        if not search_body["query"]["bool"]["should"] and not search_body["query"]["bool"]["filter"]:
            search_body["query"] = {"match_all": {}}
            print("🔍 No specific criteria, searching all products")
        else:
            # Ensure at least some criteria match
            search_body["query"]["bool"]["minimum_should_match"] = 1
        
        try:
            print(f"🔍 Executing search with body: {json.dumps(search_body, indent=2)}")
            response = await self.client.search(index=self.products_index, **search_body)
            results = []
            
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                product["_score"] = hit["_score"]
                results.append(product)
            
            print(f"✅ Elasticsearch returned {len(results)} products")
            return results
            
        except Exception as e:
            logger.error(f"Requirements-based search failed: {e}")
            print(f"❌ Search failed: {e}")
            # Return empty list instead of falling back to samples
            return []

# Global instance
elasticsearch_service = ElasticsearchService() 