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
            # Test connection first
            await self.test_connection()
            
            await self.create_indices()
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
            # Load products from JSON files
            data_dir = Path("Data/json")
            if data_dir.exists():
                await self._load_products_from_json(data_dir)
            else:
                logger.warning(f"Data directory not found: {data_dir}")
                # Load sample data instead
                await self._load_sample_products()
            
            await self._load_sample_solutions()
        except Exception as e:
            logger.warning(f"Could not load initial data: {e}")
            # Continue anyway, we'll load sample data
            await self._load_sample_products()
            await self._load_sample_solutions()
    
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
    
    async def _load_products_from_json(self, data_dir: Path):
        """Load products from JSON files in data directory"""
        product_files = list(data_dir.glob("*.json"))
        
        for file_path in product_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    for item in data:
                        if 'id' in item and 'name' in item:
                            await self.index_product(item)
                elif isinstance(data, dict) and 'id' in data:
                    await self.index_product(data)
                        
                logger.info(f"Loaded products from {file_path}")
            except Exception as e:
                logger.error(f"Failed to load products from {file_path}: {e}")
    
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
    
    async def search_products(self, query: str, filters: Optional[Dict] = None, size: int = 10) -> List[Dict]:
        """Search for products"""
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["name^3", "description^2", "features", "use_cases", "tags"]
                            }
                        }
                    ]
                }
            },
            "size": size
        }
        
        # Add filters
        if filters:
            filter_clauses = []
            for key, value in filters.items():
                if isinstance(value, list):
                    filter_clauses.append({"terms": {key: value}})
                else:
                    filter_clauses.append({"term": {key: value}})
            
            if filter_clauses:
                search_body["query"]["bool"]["filter"] = filter_clauses
        
        try:
            response = await self.client.search(index=self.products_index, **search_body)
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Product search failed: {e}")
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

# Global instance
elasticsearch_service = ElasticsearchService() 