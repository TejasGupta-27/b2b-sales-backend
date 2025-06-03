import json
import logging
from typing import List, Dict, Any, Optional
from .base import AIProvider, AIMessage, AIResponse
from services.elasticsearch_service import get_elasticsearch_service
from services.chroma_service import ChromaDBService
from .function_models import RequirementExtraction, ProductAnalysis

logger = logging.getLogger(__name__)

class HybridProductRetrieverAgent(AIProvider):
    """Hybrid product retriever using both Elasticsearch and ChromaDB"""
    
    def __init__(
        self, 
        base_provider: AIProvider,
        azure_embedding_endpoint: str,
        azure_embedding_key: str,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.elasticsearch = get_elasticsearch_service()
        self.chroma_service = ChromaDBService(azure_embedding_endpoint, azure_embedding_key)
        
    @property
    def provider_name(self) -> str:
        return f"hybrid_product_retriever_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def initialize(self):
        """Initialize both search services"""
        try:
            await self.chroma_service.initialize()
            logger.info("Hybrid Product Retriever initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Hybrid Product Retriever: {e}")
            raise
    
    async def generate_response(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """This agent doesn't generate conversational responses directly"""
        return AIResponse(
            content="Hybrid Product Retriever Agent - use retrieve_products method",
            model="hybrid-retriever-agent",
            provider=self.provider_name,
            usage={}
        )
    
    async def analyze_conversation_and_retrieve(
        self, 
        conversation_messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze conversation and retrieve products using hybrid approach"""
        
        print("🔍 Hybrid Retriever Agent: Starting hybrid analysis...")
        
        # Step 1: Extract requirements
        requirements = await self._extract_requirements_from_conversation(
            conversation_messages, customer_context
        )
        
        # Step 2: Perform hybrid search
        hybrid_results = await self._perform_hybrid_search(requirements)
        
        # Step 3: Analyze and rank results
        analysis = await self._analyze_hybrid_recommendations(
            hybrid_results["products"], 
            hybrid_results["solutions"], 
            requirements
        )
        
        return {
            "requirements": requirements,
            "products": hybrid_results["products"],
            "solutions": hybrid_results["solutions"],
            "analysis": analysis,
            "search_methods": hybrid_results["search_methods"],
            "retrieval_confidence": self._calculate_hybrid_confidence(hybrid_results, requirements)
        }
    
    async def _extract_requirements_from_conversation(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract requirements using the base provider"""
        
        try:
            conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
            
            extraction_prompt = f"""You are an expert B2B technology sales analyst. Extract detailed requirements from this conversation.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT: {customer_context or 'None provided'}

Extract the following information:
1. TECHNICAL REQUIREMENTS: Specific technical needs, specifications, features mentioned
2. BUSINESS REQUIREMENTS: Business goals, use cases, operational needs  
3. PRODUCT CATEGORIES: Types of products/solutions needed (servers, storage, workstations, etc.)
4. SEARCH KEYWORDS: Key terms that should be used to search for products
5. BUDGET/TIMELINE: Any budget or timeline constraints mentioned
6. COMPANY INFO: Industry, size, specific context that affects product selection

Be comprehensive and extract ALL relevant technical terms, business needs, and search keywords."""

            print("🔍 Extracting requirements using Pydantic structured response...")
            
            # Use structured extraction
            requirements = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=extraction_prompt)],
                RequirementExtraction
            )
            
            requirements_dict = requirements.model_dump()
            
            # Build search query for semantic search
            semantic_query = self._build_semantic_search_query(requirements_dict)
            requirements_dict['semantic_query'] = semantic_query
            
            print(f"✅ Extracted requirements: {json.dumps(requirements_dict, indent=2)}")
            return requirements_dict
                
        except Exception as e:
            print(f"⚠️ Requirement extraction failed: {e}")
            return self._fallback_requirement_extraction(
                "\n".join([f"{msg.role}: {msg.content}" for msg in messages]), 
                customer_context
            )
    
    def _build_semantic_search_query(self, requirements: Dict[str, Any]) -> str:
        """Build a natural language query for semantic search"""
        
        query_parts = []
        
        # Add use case
        use_case = requirements.get('use_case', '')
        if use_case:
            query_parts.append(use_case)
        
        # Add technical requirements
        tech_reqs = requirements.get('technical_requirements', [])
        if tech_reqs:
            query_parts.extend([str(req) for req in tech_reqs if str(req)])
        
        # Add business requirements
        business_reqs = requirements.get('business_requirements', [])
        if business_reqs:
            query_parts.extend([str(req) for req in business_reqs if str(req)])
        
        # Add product categories
        categories = requirements.get('product_categories', [])
        if categories:
            query_parts.append(f"Products needed: {', '.join(categories)}")
        
        # Add industry context
        industry = requirements.get('industry', '')
        if industry:
            query_parts.append(f"Industry: {industry}")
        
        return " ".join(query_parts)
    
    async def _perform_hybrid_search(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Perform hybrid search using both Elasticsearch and ChromaDB"""
        
        print("🔍 Performing hybrid search (Elasticsearch + ChromaDB)...")
        
        # Parallel searches
        elasticsearch_products, chroma_products, chroma_solutions = await asyncio.gather(
            self._elasticsearch_search(requirements),
            self._chroma_semantic_search_products(requirements),
            self._chroma_semantic_search_solutions(requirements),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(elasticsearch_products, Exception):
            print(f"⚠️ Elasticsearch search failed: {elasticsearch_products}")
            elasticsearch_products = []
            
        if isinstance(chroma_products, Exception):
            print(f"⚠️ ChromaDB product search failed: {chroma_products}")
            chroma_products = []
            
        if isinstance(chroma_solutions, Exception):
            print(f"⚠️ ChromaDB solution search failed: {chroma_solutions}")
            chroma_solutions = []
        
        # Debug logging before merge
        print(f"🔍 Pre-merge counts:")
        print(f"   Elasticsearch products: {len(elasticsearch_products)}")
        print(f"   ChromaDB products: {len(chroma_products)}")
        print(f"   ChromaDB solutions: {len(chroma_solutions)}")
        
        # Merge and deduplicate results
        merged_products = self._merge_product_results(elasticsearch_products, chroma_products)
        merged_solutions = chroma_solutions  # Only from ChromaDB for now
        
        # Debug logging after merge
        print(f"🔍 Post-merge counts:")
        print(f"   Merged products: {len(merged_products)}")
        print(f"   Final solutions: {len(merged_solutions)}")
        
        search_methods = {
            "elasticsearch_products": len(elasticsearch_products),
            "chroma_products": len(chroma_products),
            "chroma_solutions": len(chroma_solutions),
            "merged_products": len(merged_products)
        }
        
        print(f"🎯 Hybrid search results: {search_methods}")
        
        return {
            "products": merged_products,
            "solutions": merged_solutions,
            "search_methods": search_methods
        }
    
    async def _elasticsearch_search(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search using Elasticsearch"""
        try:
            return await self.elasticsearch.search_products_by_requirements(requirements, size=15)
        except Exception as e:
            print(f"❌ Elasticsearch search failed: {e}")
            return []
    
    async def _chroma_semantic_search_products(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search products using ChromaDB semantic search"""
        try:
            semantic_query = requirements.get('semantic_query', '')
            if not semantic_query:
                return []
            
            # Build category filter if available
            where_filter = None
            categories = requirements.get('product_categories', [])
            if categories:
                where_filter = {"category": {"$in": categories}}
            
            return await self.chroma_service.semantic_search_products(
                query=semantic_query,
                n_results=15,
                where_filter=where_filter
            )
        except Exception as e:
            print(f"❌ ChromaDB product search failed: {e}")
            return []
    
    async def _chroma_semantic_search_solutions(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search solutions using ChromaDB semantic search"""
        try:
            semantic_query = requirements.get('semantic_query', '')
            if not semantic_query:
                return []
            
            # Build industry filter if available
            where_filter = None
            industry = requirements.get('industry', '')
            if industry:
                where_filter = {"industry": {"$contains": industry}}
            
            return await self.chroma_service.semantic_search_solutions(
                query=semantic_query,
                n_results=10,
                where_filter=where_filter
            )
        except Exception as e:
            print(f"❌ ChromaDB solution search failed: {e}")
            return []
    
    def _merge_product_results(
        self, 
        elasticsearch_products: List[Dict], 
        chroma_products: List[Dict]
    ) -> List[Dict]:
        """Merge and deduplicate product results from both sources"""
        
        print(f"🔀 Starting merge process...")
        print(f"   Input: {len(elasticsearch_products)} ES products, {len(chroma_products)} Chroma products")
        
        merged = {}
        
        # Add Elasticsearch results with keyword score
        for i, product in enumerate(elasticsearch_products):
            product_id = product.get('id', '')
            product_name = product.get('name', 'Unknown')
            if product_id:
                product['search_source'] = 'elasticsearch'
                product['keyword_score'] = product.get('_score', 0)
                product['semantic_score'] = 0
                merged[product_id] = product
                print(f"   📋 ES {i+1}: {product_name} (ID: {product_id}, Score: {product.get('_score', 0)})")
        
        # Add ChromaDB results with semantic score
        for i, product in enumerate(chroma_products):
            product_id = product.get('id', '')
            product_name = product.get('name', 'Unknown')
            if product_id:
                similarity_score = product.get('_similarity_score', 0)
                if product_id in merged:
                    # Product found in both sources - combine scores
                    merged[product_id]['search_source'] = 'both'
                    merged[product_id]['semantic_score'] = similarity_score
                    # Calculate combined score
                    keyword_score = merged[product_id].get('keyword_score', 0)
                    merged[product_id]['hybrid_score'] = (keyword_score * 0.4) + (similarity_score * 0.6)
                    print(f"   🔗 Both {i+1}: {product_name} (ID: {product_id}, Combined)")
                else:
                    # Only found in ChromaDB
                    product['search_source'] = 'chroma'
                    product['keyword_score'] = 0
                    product['semantic_score'] = similarity_score
                    product['hybrid_score'] = similarity_score
                    merged[product_id] = product
                    print(f"   🧠 Chroma {i+1}: {product_name} (ID: {product_id}, Score: {similarity_score})")
            else:
                print(f"   ⚠️ Chroma product {i+1} missing ID: {product_name}")
        
        # Convert back to list and sort by hybrid score
        result = list(merged.values())
        result.sort(key=lambda x: x.get('hybrid_score', x.get('_score', 0)), reverse=True)
        
        print(f"🎯 Merge complete: {len(result)} unique products")
        print(f"   Top 5 results:")
        for i, product in enumerate(result[:5]):
            print(f"     {i+1}. {product.get('name', 'Unknown')} (Score: {product.get('hybrid_score', product.get('_score', 0)):.3f})")
        
        return result[:20]  # Top 20 results
    
    async def _analyze_hybrid_recommendations(
        self, 
        products: List[Dict], 
        solutions: List[Dict], 
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze hybrid recommendations using Pydantic function calling"""
        
        analysis_prompt = f"""You are a technical solution architect analyzing hybrid search results from both keyword and semantic search.

CUSTOMER REQUIREMENTS:
{json.dumps(requirements, indent=2)}

HYBRID PRODUCT RESULTS:
{json.dumps(products[:5], indent=2)}

SEMANTIC SOLUTION RESULTS:
{json.dumps(solutions, indent=2)}

Provide detailed analysis considering both keyword relevance and semantic similarity scores."""
        
        try:
            analysis = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=analysis_prompt)],
                ProductAnalysis
            )
            
            return analysis.model_dump()
            
        except Exception as e:
            print(f"⚠️ Hybrid analysis failed: {e}")
            return {
                "recommended_approach": "hybrid",
                "top_recommendations": [],
                "missing_requirements": [],
                "alternative_options": [],
                "total_estimated_value": 0
            }
    
    def _calculate_hybrid_confidence(
        self, 
        hybrid_results: Dict[str, Any], 
        requirements: Dict[str, Any]
    ) -> float:
        """Calculate confidence based on hybrid search results"""
        
        score = 0.0
        
        products = hybrid_results.get('products', [])
        solutions = hybrid_results.get('solutions', [])
        search_methods = hybrid_results.get('search_methods', {})
        
        # Base score for finding results
        if products:
            score += 0.4
        if solutions:
            score += 0.2
        
        # Bonus for hybrid matches (found in both sources)
        hybrid_matches = len([p for p in products if p.get('search_source') == 'both'])
        if hybrid_matches > 0:
            score += 0.3 * min(hybrid_matches / 5, 1.0)  # Up to 30% bonus
        
        # Bonus for high semantic similarity
        high_semantic_products = len([p for p in products if p.get('semantic_score', 0) > 0.8])
        if high_semantic_products > 0:
            score += 0.2 * min(high_semantic_products / 3, 1.0)  # Up to 20% bonus
        
        return min(score, 1.0)
    
    async def retrieve_products(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main interface for hybrid product retrieval"""
        
        try:
            print(f"🔍 Hybrid Product Retriever: Starting analysis...")
            
            # Extract requirements
            requirements = await self._extract_requirements_from_conversation(messages, customer_context)
            
            # Perform hybrid search
            hybrid_results = await self._perform_hybrid_search(requirements)
            
            # Return structured response
            retrieval_result = {
                'products': hybrid_results['products'],
                'solutions': hybrid_results['solutions'],
                'requirements': requirements,
                'total_products': len(hybrid_results['products']),
                'total_solutions': len(hybrid_results['solutions']),
                'search_methods': hybrid_results['search_methods'],
                'retrieval_method': 'hybrid_elasticsearch_chroma',
                'success': True
            }
            
            print(f"✅ Hybrid Retriever: Found {len(hybrid_results['products'])} products, {len(hybrid_results['solutions'])} solutions")
            return retrieval_result
            
        except Exception as e:
            print(f"❌ Hybrid Product Retriever: Error - {str(e)}")
            import traceback
            print(traceback.format_exc())
            
            return {
                'products': [],
                'solutions': [],
                'requirements': {},
                'total_products': 0,
                'total_solutions': 0,
                'search_methods': {},
                'retrieval_method': 'error_fallback',
                'success': False,
                'error': str(e)
            }
    
    def _fallback_requirement_extraction(
        self, 
        conversation_text: str, 
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enhanced fallback requirement extraction"""
        
        text_lower = conversation_text.lower()
        
        # Extract basic requirements using patterns
        technical_requirements = []
        business_requirements = []
        product_categories = []
        
        # Technical patterns
        if 'workstation' in text_lower or 'gaming' in text_lower:
            technical_requirements.append('High-performance workstation')
            product_categories.append('workstation')
        
        if 'server' in text_lower:
            technical_requirements.append('Server infrastructure')
            product_categories.append('server')
        
        if 'storage' in text_lower or 'nas' in text_lower:
            technical_requirements.append('Storage solution')
            product_categories.append('storage')
        
        # Business patterns
        if 'business' in text_lower:
            business_requirements.append('Business use case')
        
        if 'enterprise' in text_lower:
            business_requirements.append('Enterprise requirements')
        
        # Build semantic query
        semantic_query = conversation_text[:500]  # Use first 500 chars
        
        return {
            'technical_requirements': technical_requirements,
            'business_requirements': business_requirements,
            'product_categories': product_categories,
            'search_terms': product_categories + technical_requirements,
            'semantic_query': semantic_query,
            'use_case': 'General business requirements',
            'industry': customer_context.get('industry', '') if customer_context else '',
            'extraction_method': 'fallback'
        }

# Async helper to avoid import issues
import asyncio

async def run_async(coro):
    """Helper to run async code"""
    return await coro 