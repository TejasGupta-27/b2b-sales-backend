import json
import logging
from typing import List, Dict, Any, Optional
from elasticsearch import AsyncElasticsearch
from pathlib import Path
from config import settings
import asyncio
from elasticsearch.exceptions import ConnectionError, RequestError

logger = logging.getLogger(__name__)

class ElasticsearchService:
    def __init__(self):
        self.client = AsyncElasticsearch(
            hosts=["http://elasticsearch:9200"],
            verify_certs=False,
            ssl_show_warn=False,
            request_timeout=30,
            retry_on_timeout=True,
            max_retries=3
        )
        self.products_index = settings.elasticsearch_index_products
        self.solutions_index = settings.elasticsearch_index_solutions
        self.health_checked = False
    
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
            logger.warning("Continuing with fallback data due to Elasticsearch initialization failure")
    
    async def test_connection(self):
        """Test Elasticsearch connection"""
        try:
            info = await self.client.info()
            logger.info(f"Elasticsearch connected: {info.get('cluster_name', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {e}")
            return False
    
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
        """Load initial product and solution data from JSON files with better error handling"""
        try:
            # Wait for cluster to be ready before checking data
            await self._wait_for_cluster_ready()
            
            # Check if data already exists
            products_count = await self._safe_count(self.products_index)
            solutions_count = await self._safe_count(self.solutions_index)
            
            print(f"📊 Current data: {products_count} products, {solutions_count} solutions")
            
            if products_count > 0 and solutions_count > 0:
                logger.info(f"Data already exists: {products_count} products, {solutions_count} solutions. Skipping reload.")
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
            solutions_response = await self._safe_count(self.solutions_index)
            if solutions_response == 0:
                await self._load_sample_solutions()
            
            # Refresh indices to make data immediately available
            await self._safe_refresh_indices()
            
            print(f"✅ Data loading complete: {products_loaded} products loaded")
            
        except Exception as e:
            logger.warning(f"Could not load initial data: {e}")
            # Force load sample data as fallback
            try:
                logger.info("Force loading sample data as fallback...")
                await self._force_load_sample_data()
            except Exception as fallback_error:
                logger.error(f"Failed to load fallback data: {fallback_error}")
    
    async def _wait_for_cluster_ready(self, max_attempts: int = 10, delay: float = 2.0):
        """Wait for Elasticsearch cluster to be ready"""
        for attempt in range(max_attempts):
            try:
                # Try a simple cluster health check with short timeout
                health = await self.client.cluster.health(
                    wait_for_status='yellow',
                    timeout='2s',
                    request_timeout=3
                )
                
                if health['status'] in ['green', 'yellow']:
                    logger.info(f"✅ Cluster ready: {health['status']} status")
                    return True
                    
            except Exception as e:
                logger.warning(f"Cluster not ready (attempt {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
        
        logger.warning("Cluster readiness timeout - proceeding anyway")
        return False
    
    async def _safe_count(self, index: str) -> int:
        """Safely count documents with retries and fallbacks"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.count(
                    index=index,
                    request_timeout=5,
                    ignore_unavailable=True
                )
                return response.get('count', 0)
            except Exception as e:
                logger.warning(f"Count attempt {attempt + 1} failed for {index}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"All count attempts failed for {index}")
                    return 0
    
    async def _safe_refresh_indices(self):
        """Safely refresh indices with error handling"""
        try:
            await self.client.indices.refresh(
                index=[self.products_index, self.solutions_index],
                request_timeout=10,
                ignore_unavailable=True
            )
            logger.info("✅ Indices refreshed successfully")
        except Exception as e:
            logger.warning(f"Index refresh failed: {e}")
    
    async def _force_load_sample_data(self):
        """Force load sample data with individual document indexing"""
        logger.info("🔄 Force loading sample products...")
        
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
        
        # Index products one by one with retries
        for product in sample_products:
            await self._force_index_document(self.products_index, product['id'], product)
        
        # Load sample solutions
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
            }
        ]
        
        for solution in sample_solutions:
            await self._force_index_document(self.solutions_index, solution['id'], solution)
        
        logger.info("✅ Force loaded sample data")
    
    async def _handle_readonly_cluster(self):
        """Handle read-only cluster by attempting to clear the restriction"""
        try:
            # Try to disable read-only mode
            await self.client.indices.put_settings(
                index="_all",
                body={
                    "index.blocks.read_only_allow_delete": None
                }
            )
            logger.info("✅ Cleared read-only restriction")
            return True
        except Exception as e:
            logger.warning(f"Could not clear read-only mode: {e}")
            return False

    async def _force_index_document(self, index: str, doc_id: str, document: dict, max_retries: int = 5):
        """Force index a single document with aggressive retries"""
        for attempt in range(max_retries):
            try:
                # Check if cluster is in read-only mode
                cluster_settings = await self.client.cluster.get_settings()
                if cluster_settings.get('persistent', {}).get('cluster', {}).get('blocks', {}).get('read_only_allow_delete'):
                    logger.warning("Cluster is in read-only mode, attempting to clear...")
                    await self._handle_readonly_cluster()
                
                await self.client.index(
                    index=index,
                    id=doc_id,
                    document=document,
                    request_timeout=10,
                    refresh='wait_for'
                )
                logger.info(f"✅ Indexed {doc_id} in {index}")
                return True
            except Exception as e:
                if "read_only_allow_delete" in str(e).lower():
                    logger.warning(f"Read-only mode detected, attempting recovery...")
                    await self._handle_readonly_cluster()
                
                logger.warning(f"Index attempt {attempt + 1} failed for {doc_id}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"Failed to index {doc_id} after {max_retries} attempts")
                    return False
    
    async def ensure_healthy(self):
        """Ensure Elasticsearch is healthy before operations with aggressive retry"""
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                # Try cluster health with very short timeout
                health = await self.client.cluster.health(
                    wait_for_status='yellow',
                    timeout='1s',
                    request_timeout=2
                )
                
                if health['status'] in ['green', 'yellow']:
                    self.health_checked = True
                    return True
                    
            except Exception as e:
                logger.warning(f"Health check attempt {attempt + 1} failed: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1)
        
        # If health checks fail, try to force cluster recovery
        logger.warning("Health checks failed - attempting cluster recovery")
        await self._attempt_cluster_recovery()
        raise Exception("Elasticsearch cluster unhealthy after recovery attempts")
    
    async def _attempt_cluster_recovery(self):
        """Attempt to recover unhealthy cluster"""
        try:
            logger.info("🔄 Attempting cluster recovery...")
            
            # Try to clear any stuck operations
            await self.client.cluster.health(
                wait_for_status='yellow',
                timeout='30s',
                request_timeout=35
            )
            
            logger.info("✅ Cluster recovery successful")
        except Exception as e:
            logger.error(f"Cluster recovery failed: {e}")
    
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
    
    async def check_health(self) -> bool:
        """Check if Elasticsearch is healthy and ready"""
        try:
            health = await self.client.cluster.health(wait_for_status='yellow', timeout='30s')
            self.health_checked = True
            print(f"✅ Elasticsearch health: {health['status']}")
            return health['status'] in ['green', 'yellow']
        except Exception as e:
            print(f"❌ Elasticsearch health check failed: {e}")
            return False
    
    async def search_products(self, query_body: dict, index: str = "products") -> List[Dict]:
        """Search products with better error handling"""
        try:
            await self.ensure_healthy()
            
            # Add timeout and preference for better reliability
            query_body.update({
                "timeout": "30s",
                "_source": True
            })
            
            response = await self.client.search(
                index=index,
                body=query_body,
                request_timeout=30,
                preference="_local"  # Use local shard when possible
            )
            
            hits = response.get('hits', {}).get('hits', [])
            return [hit['_source'] for hit in hits]
            
        except ConnectionError as e:
            print(f"❌ Elasticsearch connection error: {e}")
            return []
        except RequestError as e:
            print(f"❌ Elasticsearch request error: {e}")
            return []
        except Exception as e:
            print(f"❌ Elasticsearch search failed: {e}")
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
        try:
            await self.client.close()
        except Exception as e:
            logger.warning(f"Error closing Elasticsearch connection: {e}")

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

    async def search_products_with_fallback(self, requirements: Dict[str, Any], size: int = 20) -> List[Dict]:
        """Search products with fallback to random products if search fails"""
        
        print(f"🔍 Elasticsearch: Searching with fallback for requirements: {requirements}")
        
        try:
            # First try the requirements-based search
            results = await self.search_products_by_requirements(requirements, size)
            
            if results:
                print(f"✅ Requirements search successful: {len(results)} products")
                return results
            else:
                print("⚠️ Requirements search returned no results, trying fallback...")
                
        except Exception as e:
            print(f"❌ Requirements search failed: {e}, trying fallback...")
        
        # Fallback strategies
        try:
            # Strategy 1: Try category-based search if categories were specified
            categories = requirements.get('product_categories', [])
            if categories:
                print(f"🔄 Fallback: Searching by categories: {categories}")
                results = await self._search_by_categories(categories, size)
                if results:
                    print(f"✅ Category fallback successful: {len(results)} products")
                    return results
            
            # Strategy 2: Try keyword search if keywords were specified
            keywords = requirements.get('search_keywords', [])
            if keywords:
                print(f"🔄 Fallback: Searching by keywords: {keywords}")
                results = await self._search_by_keywords(keywords, size)
                if results:
                    print(f"✅ Keyword fallback successful: {len(results)} products")
                    return results
            
            # Strategy 3: Get random products as last resort
            print("🔄 Final fallback: Getting random products")
            results = await self.get_random_products(min(size, 10))
            if results:
                print(f"✅ Random fallback successful: {len(results)} products")
                return results
            
        except Exception as e:
            print(f"❌ All fallback strategies failed: {e}")
        
        # If everything fails, return empty list
        print("❌ All search strategies failed, returning empty list")
        return []
    
    async def _search_by_categories(self, categories: List[str], size: int = 20) -> List[Dict]:
        """Simple category-based search"""
        try:
            search_body = {
                "query": {
                    "terms": {"category": categories}
                },
                "size": size
            }
            
            response = await self.client.search(index=self.products_index, body=search_body)
            results = []
            
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                product["_score"] = hit["_score"]
                results.append(product)
            
            return results
            
        except Exception as e:
            print(f"❌ Category search failed: {e}")
            return []
    
    async def _search_by_keywords(self, keywords: List[str], size: int = 20) -> List[Dict]:
        """Simple keyword-based search"""
        try:
            search_body = {
                "query": {
                    "multi_match": {
                        "query": " ".join(keywords),
                        "fields": ["name", "description", "tags"],
                        "fuzziness": "AUTO"
                    }
                },
                "size": size
            }
            
            response = await self.client.search(index=self.products_index, body=search_body)
            results = []
            
            for hit in response["hits"]["hits"]:
                product = hit["_source"]
                product["_score"] = hit["_score"]
                results.append(product)
            
            return results
            
        except Exception as e:
            print(f"❌ Keyword search failed: {e}")
            return []
    
    async def search_products_by_requirements(self, requirements: Dict[str, Any], size: int = 20) -> List[Dict]:
        """Search products based on Pydantic-extracted requirements with better relevance"""
        
        print(f"🔍 Elasticsearch: Searching with enhanced requirements: {requirements}")
        
        # Check Elasticsearch health first
        try:
            await self.ensure_healthy()
        except Exception as e:
            print(f"❌ Elasticsearch health check failed: {e}")
            return await self.get_random_products(size)
        
        # Build more precise search query
        search_body = {
            "query": {
                "bool": {
                    "should": [],
                    "must_not": [],
                    "minimum_should_match": 1
                }
            },
            "size": size,
            "timeout": "10s",
            "_source": {
                "excludes": ["search_text"]  # Exclude large text fields from results
            }
        }
        
        # Use cleaned search terms
        search_terms = requirements.get('search_terms', [])
        print(f"🔍 Using enhanced search terms: {search_terms}")
        
        # Create more targeted queries
        for term in search_terms:
            if len(term) > 2:  # Skip very short terms
                # Exact phrase matching with high boost for names
                search_body["query"]["bool"]["should"].append({
                    "match_phrase": {
                        "name": {
                            "query": term,
                            "boost": 5.0
                        }
                    }
                })
                
                # Multi-match with field priorities
                search_body["query"]["bool"]["should"].append({
                    "multi_match": {
                        "query": term,
                        "fields": [
                            "name^4",           # Highest boost for name
                            "category^3",       # High boost for category
                            "subcategory^2",    # Medium boost for subcategory
                            "description^1.5",  # Medium boost for description
                            "tags^2",           # High boost for tags
                            "features^1.2",
                            "use_cases^1.2"
                        ],
                        "type": "best_fields",
                        "fuzziness": "1",
                        "operator": "or"  # Changed from "and" to "or" for better matches
                    }
                })
        
        # Add category filters if specified
        categories = requirements.get('product_categories', [])
        if categories:
            search_body["query"]["bool"]["should"].append({
                "terms": {
                    "category": categories,
                    "boost": 3.0
                }
            })
        
        # Filter out products with zero price (likely incomplete data)
        search_body["query"]["bool"]["must_not"].append({
            "term": {"price": 0}
        })
        
        # Add technical requirements matching (simplified - no nested query)
        tech_reqs = requirements.get('technical_requirements', [])
        for req in tech_reqs:
            if isinstance(req, str) and len(req) > 3:
                search_body["query"]["bool"]["should"].append({
                    "multi_match": {
                        "query": req,
                        "fields": ["description", "features", "name"],
                        "boost": 1.5
                    }
                })
        
        # Exclude obvious noise products by name patterns
        noise_patterns = [
            "sting ray",  # Matches the problematic "Raidmax Sting Ray" products
            "cable",
            "mounting",
            "bracket",
            "screw",
            "adapter"
        ]
        for noise_pattern in noise_patterns:
            search_body["query"]["bool"]["must_not"].append({
                "match_phrase": {"name": noise_pattern}
            })
        
        # If no search criteria, return category-based results
        if not search_body["query"]["bool"]["should"]:
            print("⚠️ No search criteria found, using category fallback")
            return await self._search_by_categories(["workstation", "server", "computer"], size)
        
        try:
            print(f"🔍 Executing enhanced Elasticsearch search...")
            print(f"🔍 Search query: {json.dumps(search_body, indent=2)}")
            
            response = await self.client.search(
                index=self.products_index,
                body=search_body,
                request_timeout=30,
                ignore_unavailable=True
            )
            
            results = []
            hits = response.get('hits', {}).get('hits', [])
            
            for hit in hits:
                product = hit['_source']
                product['_score'] = hit['_score']
                
                # Add relevance explanation for debugging
                if hit.get('_explanation'):
                    product['_explanation'] = hit['_explanation']
                
                results.append(product)
            
            print(f"✅ Enhanced Elasticsearch returned {len(results)} products")
            
            # Debug: Show top results before filtering
            if results:
                print("🔍 Top search results before filtering:")
                for i, product in enumerate(results[:5]):
                    print(f"  {i+1}. {product.get('name')} (Category: {product.get('category')}, Price: {product.get('price')}, Score: {product.get('_score', 0):.2f})")
            
            # If still no results, try broader search
            if not results:
                print("🔄 No results found, trying broader search...")
                results = await self._broader_fallback_search(search_terms, size)
            
            return results
            
        except Exception as e:
            print(f"❌ Enhanced Elasticsearch search failed: {e}")
            import traceback
            print(traceback.format_exc())
            return await self.get_random_products(size)

    async def _broader_fallback_search(self, search_terms: List[str], size: int) -> List[Dict]:
        """Broader fallback search when precise search returns no results"""
        try:
            # Try with just the most important terms
            important_terms = [term for term in search_terms if term.lower() in [
                'workstation', 'gaming', 'server', 'desktop', 'gpu', 'graphics', 'cpu', 'processor'
            ]]
            
            if important_terms:
                search_body = {
                    "query": {
                        "multi_match": {
                            "query": " ".join(important_terms),
                            "fields": ["name", "category", "description"],
                            "fuzziness": "AUTO",
                            "operator": "or"
                        }
                    },
                    "size": size
                }
                
                response = await self.client.search(
                    index=self.products_index,
                    body=search_body,
                    ignore_unavailable=True
                )
                
                results = []
                for hit in response.get('hits', {}).get('hits', []):
                    product = hit['_source']
                    if product.get('price', 0) > 0:  # Only include products with prices
                        product['_score'] = hit['_score']
                        results.append(product)
                
                print(f"✅ Broader search found {len(results)} products")
                return results
            
            return []
            
        except Exception as e:
            print(f"❌ Broader fallback search failed: {e}")
            return []

# Create a function to get the service instance instead of creating it at module level
def get_elasticsearch_service() -> ElasticsearchService:
    """Get Elasticsearch service instance"""
    return ElasticsearchService()

# Don't create the instance at module level to avoid initialization errors
# elasticsearch_service = ElasticsearchService() 