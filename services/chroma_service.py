import logging
import json
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import asyncio
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)

class ChromaDBService:
    """ChromaDB service for semantic product search using Azure embeddings"""
    
    def __init__(self, azure_embedding_endpoint: str, azure_embedding_key: str):
        self.client = None
        self.products_collection = None
        self.solutions_collection = None
        self.azure_embedding_endpoint = azure_embedding_endpoint
        self.azure_embedding_key = azure_embedding_key
        self.embedding_function = None
        
    async def initialize(self):
        """Initialize ChromaDB with Azure embeddings"""
        try:
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path="./chroma_db",
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Setup Azure OpenAI embedding function with corrected parameters
            self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=self.azure_embedding_key,
                api_base=self.azure_embedding_endpoint,
                api_type="azure",
                api_version="2023-05-15",  # Updated API version
                model_name="text-embedding-3-large",
                deployment_id="text-embedding-3-large"
            )
            
            # Get or create collections
            self.products_collection = self.client.get_or_create_collection(
                name="products",
                embedding_function=self.embedding_function,
                metadata={"description": "Product catalog for semantic search"}
            )
            
            self.solutions_collection = self.client.get_or_create_collection(
                name="solutions", 
                embedding_function=self.embedding_function,
                metadata={"description": "Solutions catalog for semantic search"}
            )
            
            logger.info("ChromaDB initialized successfully with Azure embeddings")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    async def load_limited_data_from_json(self, max_per_file: int = 50):
        """Load limited data directly from JSON files (first 50 from each file)"""
        try:
            logger.info(f"Loading first {max_per_file} items from each JSON file into ChromaDB...")
            
            data_dir = settings.data_dir
            total_products_indexed = 0
            total_solutions_indexed = 0
            files_processed = 0
            
            # Process all JSON files in the data directory
            for json_file in data_dir.glob("*.json"):
                try:
                    logger.info(f"Processing file: {json_file.name}")
                    
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    file_products = 0
                    file_solutions = 0
                    
                    # Handle different JSON structures
                    if isinstance(data, list):
                        # Direct array of items
                        items = data[:max_per_file]  # Take only first 50
                        for item in items:
                            if self._is_product_data(item):
                                await self.index_product(item)
                                file_products += 1
                            elif self._is_solution_data(item):
                                await self.index_solution(item)
                                file_solutions += 1
                                
                    elif isinstance(data, dict):
                        # Handle nested structures
                        if 'products' in data:
                            products = data['products'][:max_per_file]  # Take only first 50
                            for product in products:
                                if self._is_valid_product(product):
                                    processed_product = self._process_product_data(product)
                                    await self.index_product(processed_product)
                                    file_products += 1
                        
                        if 'solutions' in data:
                            solutions = data['solutions'][:max_per_file]  # Take only first 50
                            for solution in solutions:
                                if self._is_valid_solution(solution):
                                    processed_solution = self._process_solution_data(solution)
                                    await self.index_solution(processed_solution)
                                    file_solutions += 1
                        
                        # Handle direct object (single item)
                        if not ('products' in data or 'solutions' in data):
                            if self._is_product_data(data):
                                await self.index_product(data)
                                file_products += 1
                            elif self._is_solution_data(data):
                                await self.index_solution(data)
                                file_solutions += 1
                    
                    total_products_indexed += file_products
                    total_solutions_indexed += file_solutions
                    files_processed += 1
                    
                    logger.info(f"✅ {json_file.name}: {file_products} products, {file_solutions} solutions")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to process {json_file.name}: {e}")
                    continue
            
            logger.info(f"🎯 ChromaDB Population Summary:")
            logger.info(f"   Files processed: {files_processed}")
            logger.info(f"   Products indexed: {total_products_indexed}")
            logger.info(f"   Solutions indexed: {total_solutions_indexed}")
            logger.info(f"   Max per file: {max_per_file}")
            
            return {
                "files_processed": files_processed,
                "products_indexed": total_products_indexed,
                "solutions_indexed": total_solutions_indexed,
                "max_per_file": max_per_file
            }
            
        except Exception as e:
            logger.error(f"Failed to load limited data into ChromaDB: {e}")
            raise
    
    def _is_product_data(self, item: Dict[str, Any]) -> bool:
        """Check if an item is product data"""
        return (
            isinstance(item, dict) and 
            any(key in item for key in ['name', 'product_name', 'title']) and
            any(key in item for key in ['price', 'category', 'description', 'specifications'])
        )
    
    def _is_solution_data(self, item: Dict[str, Any]) -> bool:
        """Check if an item is solution data"""
        return (
            isinstance(item, dict) and 
            any(key in item for key in ['solution_name', 'name', 'title']) and
            any(key in item for key in ['industry', 'use_case', 'benefits', 'requirements'])
        )
    
    def _is_valid_product(self, product: Dict[str, Any]) -> bool:
        """Validate product data structure"""
        return (
            isinstance(product, dict) and
            product.get('name') and
            len(str(product.get('name', '')).strip()) > 0
        )
    
    def _is_valid_solution(self, solution: Dict[str, Any]) -> bool:
        """Validate solution data structure"""
        return (
            isinstance(solution, dict) and
            solution.get('name') and
            len(str(solution.get('name', '')).strip()) > 0
        )
    
    def _process_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Process and standardize product data"""
        processed = product.copy()
        
        # Ensure required fields
        if not processed.get('id'):
            processed['id'] = f"product_{hash(str(product))}"
        
        # Standardize price
        if 'price' in processed and processed['price']:
            try:
                processed['price'] = float(processed['price'])
            except (ValueError, TypeError):
                processed['price'] = 0.0
        
        return processed
    
    def _process_solution_data(self, solution: Dict[str, Any]) -> Dict[str, Any]:
        """Process and standardize solution data"""
        processed = solution.copy()
        
        # Ensure required fields
        if not processed.get('id'):
            processed['id'] = f"solution_{hash(str(solution))}"
        
        return processed

    async def index_product(self, product: Dict[str, Any]):
        """Index a single product in ChromaDB"""
        try:
            # Ensure we have required fields
            product_id = product.get("id") or product.get("name") or f"product_{hash(str(product))}"
            product_name = product.get("name") or product.get("product_name") or "Unknown Product"
            
            # Create searchable text from product data
            searchable_text = self._create_product_searchable_text(product)
            
            # Prepare metadata with string values only (ChromaDB requirement)
            metadata = {
                "id": str(product_id),
                "name": str(product_name),
                "category": str(product.get("category", "")),
                "price": str(product.get("price", 0)),
                "product_data": json.dumps(product, ensure_ascii=False)
            }
            
            # Add to collection with unique ID
            unique_id = f"prod_{hash(str(product_id))}"
            
            self.products_collection.add(
                documents=[searchable_text],
                metadatas=[metadata],
                ids=[unique_id]
            )
            
            logger.debug(f"Indexed product: {product_name} with ID: {unique_id}")
            
        except Exception as e:
            logger.error(f"Failed to index product {product.get('id', 'unknown')}: {e}")
            raise
    
    async def index_solution(self, solution: Dict[str, Any]):
        """Index a single solution in ChromaDB"""
        try:
            # Ensure we have required fields
            solution_id = solution.get("id") or solution.get("name") or f"solution_{hash(str(solution))}"
            solution_name = solution.get("name") or solution.get("solution_name") or "Unknown Solution"
            
            # Create searchable text from solution data
            searchable_text = self._create_solution_searchable_text(solution)
            
            # Prepare metadata with string values only
            metadata = {
                "id": str(solution_id),
                "name": str(solution_name),
                "industry": str(solution.get("industry", [])) if isinstance(solution.get("industry"), list) else str(solution.get("industry", "")),
                "solution_data": json.dumps(solution, ensure_ascii=False)
            }
            
            # Add to collection with unique ID
            unique_id = f"sol_{hash(str(solution_id))}"
            
            self.solutions_collection.add(
                documents=[searchable_text],
                metadatas=[metadata],
                ids=[unique_id]
            )
            
            logger.debug(f"Indexed solution: {solution_name} with ID: {unique_id}")
            
        except Exception as e:
            logger.error(f"Failed to index solution {solution.get('id', 'unknown')}: {e}")
            raise
    
    def _create_product_searchable_text(self, product: Dict[str, Any]) -> str:
        """Create comprehensive searchable text for a product"""
        text_parts = []
        
        # Basic info
        if product.get("name"):
            text_parts.append(f"Product: {product['name']}")
        
        if product.get("category"):
            text_parts.append(f"Category: {product['category']}")
            
        if product.get("subcategory"):
            text_parts.append(f"Subcategory: {product['subcategory']}")
        
        if product.get("description"):
            text_parts.append(f"Description: {product['description']}")
        
        # Specifications
        specs = product.get("specifications", {})
        if isinstance(specs, dict):
            for key, value in specs.items():
                text_parts.append(f"{key}: {value}")
        
        # Features and use cases
        if product.get("features"):
            text_parts.append(f"Features: {product['features']}")
            
        if product.get("use_cases"):
            text_parts.append(f"Use cases: {product['use_cases']}")
        
        # Tags
        if product.get("tags"):
            if isinstance(product["tags"], list):
                text_parts.append(f"Tags: {', '.join(product['tags'])}")
            else:
                text_parts.append(f"Tags: {product['tags']}")
        
        # Target industries
        if product.get("target_industries"):
            if isinstance(product["target_industries"], list):
                text_parts.append(f"Industries: {', '.join(product['target_industries'])}")
        
        return " | ".join(text_parts)
    
    def _create_solution_searchable_text(self, solution: Dict[str, Any]) -> str:
        """Create comprehensive searchable text for a solution"""
        text_parts = []
        
        if solution.get("name"):
            text_parts.append(f"Solution: {solution['name']}")
            
        if solution.get("description"):
            text_parts.append(f"Description: {solution['description']}")
            
        if solution.get("use_case"):
            text_parts.append(f"Use case: {solution['use_case']}")
            
        if solution.get("industry"):
            industries = solution["industry"]
            if isinstance(industries, list):
                text_parts.append(f"Industries: {', '.join(industries)}")
            else:
                text_parts.append(f"Industry: {industries}")
        
        if solution.get("benefits"):
            text_parts.append(f"Benefits: {solution['benefits']}")
            
        if solution.get("requirements"):
            text_parts.append(f"Requirements: {solution['requirements']}")
        
        return " | ".join(text_parts)
    
    async def semantic_search_products(
        self, 
        query: str, 
        n_results: int = 10,
        where_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Perform semantic search on products"""
        try:
            # Convert unsupported operators to supported ones
            processed_filter = self._process_where_filter(where_filter) if where_filter else None
            
            # Check collection count first
            total_products = self.products_collection.count()
            logger.info(f"🗂️ Total products in ChromaDB: {total_products}")
            logger.info(f"🔍 Product search - Query: '{query}', n_results: {n_results}, filter: {processed_filter}")
            
            results = self.products_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=processed_filter
            )
            
            logger.info(f"📊 ChromaDB raw results: {len(results.get('documents', [[]])[0])} documents found")
            if results.get("distances") and results["distances"][0]:
                logger.info(f"📏 Similarity scores (distances): {[1 - d for d in results['distances'][0]]}")
            
            products = []
            if results["documents"] and results["documents"][0]:
                for i, metadata in enumerate(results["metadatas"][0]):
                    try:
                        product_data = json.loads(metadata["product_data"])
                        similarity_score = 1 - results["distances"][0][i]
                        product_data["_similarity_score"] = similarity_score
                        
                        # Ensure ID is present - try multiple sources
                        if not product_data.get('id'):
                            # Try to get ID from metadata first
                            product_data['id'] = metadata.get('id', '')
                            
                            # If still no ID, try other fields
                            if not product_data['id']:
                                product_data['id'] = (
                                    product_data.get('product_id') or 
                                    product_data.get('sku') or 
                                    f"chroma_{hash(product_data.get('name', ''))}"
                                )
                        
                        logger.info(f"📦 Product {i+1}: {product_data.get('name', 'Unknown')} (ID: {product_data.get('id', 'MISSING')}, score: {similarity_score:.3f})")
                        products.append(product_data)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Failed to parse product data: {e}")
                        continue
            else:
                logger.info("❌ No documents returned from ChromaDB query")
            
            logger.info(f"✅ Returning {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"Semantic product search failed: {e}")
            return []
    
    async def semantic_search_solutions(
        self, 
        query: str, 
        n_results: int = 5,
        where_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Perform semantic search on solutions"""
        try:
            # Convert unsupported operators to supported ones
            processed_filter = self._process_where_filter(where_filter) if where_filter else None
            
            # Check collection count first
            total_solutions = self.solutions_collection.count()
            logger.info(f"🗂️ Total solutions in ChromaDB: {total_solutions}")
            logger.info(f"🔍 Solution search - Query: '{query}', n_results: {n_results}, filter: {processed_filter}")
            
            results = self.solutions_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=processed_filter
            )
            
            logger.info(f"📊 ChromaDB raw results: {len(results.get('documents', [[]])[0])} documents found")
            if results.get("distances") and results["distances"][0]:
                logger.info(f"📏 Similarity scores (distances): {[1 - d for d in results['distances'][0]]}")
            
            solutions = []
            if results["documents"] and results["documents"][0]:
                for i, metadata in enumerate(results["metadatas"][0]):
                    try:
                        solution_data = json.loads(metadata["solution_data"])
                        similarity_score = 1 - results["distances"][0][i]
                        solution_data["_similarity_score"] = similarity_score
                        
                        logger.info(f"🏗️ Solution {i+1}: {solution_data.get('name', 'Unknown')} (score: {similarity_score:.3f})")
                        solutions.append(solution_data)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Failed to parse solution data: {e}")
                        continue
            else:
                logger.info("❌ No documents returned from ChromaDB query")
            
            logger.info(f"✅ Returning {len(solutions)} solutions")
            return solutions
            
        except Exception as e:
            logger.error(f"Semantic solution search failed: {e}")
            return []
    
    def _process_where_filter(self, where_filter: Dict) -> Optional[Dict]:
        """Process where filter to convert unsupported operators to supported ones"""
        if not where_filter:
            return None
            
        processed = {}
        
        for key, value in where_filter.items():
            if isinstance(value, dict):
                # Handle operator-based filters
                new_value = {}
                for op, op_value in value.items():
                    if op == "$contains":
                        # Convert $contains to $eq for exact match
                        # ChromaDB doesn't support partial string matching in where clauses
                        logger.warning(f"Converting unsupported $contains operator to $eq for field {key}")
                        new_value["$eq"] = op_value
                    elif op in ["$gt", "$gte", "$lt", "$lte", "$ne", "$eq", "$in", "$nin"]:
                        # Supported operators
                        new_value[op] = op_value
                    else:
                        logger.warning(f"Unsupported operator {op} for field {key}, skipping")
                
                if new_value:
                    processed[key] = new_value
            else:
                # Direct value comparison (implicit $eq)
                processed[key] = value
        
        return processed if processed else None
    
    # Keep the old method for backward compatibility, but modify it
    async def load_products_from_elasticsearch(self, elasticsearch_service):
        """Load limited products from Elasticsearch into ChromaDB (first 50 per source)"""
        logger.info("⚠️ Using limited JSON loading instead of full Elasticsearch sync")
        return await self.load_limited_data_from_json(max_per_file=50)
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about ChromaDB collections"""
        try:
            products_count = self.products_collection.count() if self.products_collection else 0
            solutions_count = self.solutions_collection.count() if self.solutions_collection else 0
            
            return {
                "products_count": products_count,
                "solutions_count": solutions_count,
                "status": "healthy",
                "data_source": "limited_json_files",
                "max_per_file": 50,
                "initialized": bool(self.client and self.products_collection and self.solutions_collection)
            }
        except Exception as e:
            logger.error(f"Failed to get ChromaDB stats: {e}")
            return {
                "products_count": 0,
                "solutions_count": 0,
                "status": "error",
                "error": str(e),
                "initialized": False
            }