import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from .base import AIProvider, AIMessage, AIResponse
from services.elasticsearch_service import get_elasticsearch_service
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from .function_models import RequirementExtraction, ProductAnalysis
from config import settings

logger = logging.getLogger(__name__)

class RRFHybridFusion:
    """Reciprocal Rank Fusion (RRF) implementation for hybrid search results"""
    
    def __init__(self, k: float = None):
        """
        Initialize RRF with parameter k
        
        Args:
            k: RRF parameter that controls the contribution of lower-ranked results
               Default k=60 is commonly used and provides good balance
        """
        self.k = k or settings.rrf_k
        logger.info(f"RRF Fusion initialized with k={self.k}")
    
    def calculate_rrf_score(self, rank: int) -> float:
        """
        Calculate RRF score for a given rank
        
        Args:
            rank: 1-based rank position (1 = top result)
            
        Returns:
            RRF score (higher is better)
        """
        if rank <= 0:
            return 0.0
        return 1.0 / (self.k + rank)
    
    def fuse_rankings(
        self, 
        elasticsearch_products: List[Dict], 
        vector_products: List[Dict],
        max_results: int = None
    ) -> List[Dict]:
        """
        Fuse product rankings using RRF
        
        Args:
            elasticsearch_products: Products from keyword search with _score
            vector_products: Products from vector search with _similarity_score
            max_results: Maximum number of results to return
            
        Returns:
            Fused and ranked product list
        """
        max_results = max_results or settings.final_result_limit
        
        print(f"🎯 RRF Fusion: Starting with k={self.k}")
        print(f"   Input: {len(elasticsearch_products)} ES products, {len(vector_products)} vector products")
        print(f"   Max results: {max_results}")
        
        # Create product ID to rank mappings
        es_ranks = {}
        vector_ranks = {}
        
        # Build Elasticsearch rank mapping
        for rank, product in enumerate(elasticsearch_products, 1):
            product_id = product.get('id', '')
            if product_id:
                es_ranks[product_id] = rank
                print(f"   📋 ES Rank {rank}: {product.get('name', 'Unknown')} (ID: {product_id})")
        
        # Build vector rank mapping
        for rank, product in enumerate(vector_products, 1):
            product_id = product.get('id', '')
            if product_id:
                vector_ranks[product_id] = rank
                print(f"   🧠 Vector Rank {rank}: {product.get('name', 'Unknown')} (ID: {product_id})")
        
        # Calculate RRF scores for all unique products
        rrf_scores = {}
        all_products = {}
        
        # Process all products from both sources
        for product in elasticsearch_products + vector_products:
            product_id = product.get('id', '')
            if not product_id:
                continue
                
            if product_id not in all_products:
                all_products[product_id] = product.copy()
                rrf_scores[product_id] = 0.0
        
        # Calculate RRF scores with weighted contributions
        for product_id in rrf_scores:
            es_rank = es_ranks.get(product_id)
            vector_rank = vector_ranks.get(product_id)
            
            rrf_score = 0.0
            
            # Add weighted RRF score from Elasticsearch ranking
            if es_rank is not None:
                es_rrf = self.calculate_rrf_score(es_rank) * settings.rrf_elasticsearch_weight
                rrf_score += es_rrf
                print(f"   📊 {product_id}: ES rank {es_rank} → RRF {es_rrf:.4f} (weight: {settings.rrf_elasticsearch_weight})")
            
            # Add weighted RRF score from vector ranking
            if vector_rank is not None:
                vector_rrf = self.calculate_rrf_score(vector_rank) * settings.rrf_semantic_weight
                rrf_score += vector_rrf
                print(f"   📊 {product_id}: Vector rank {vector_rank} → RRF {vector_rrf:.4f} (weight: {settings.rrf_semantic_weight})")
            
            rrf_scores[product_id] = rrf_score
            print(f"   🎯 {product_id}: Total RRF = {rrf_score:.4f}")
        
        # Add metadata to products
        for product_id, product in all_products.items():
            product['rrf_score'] = rrf_scores[product_id]
            product['es_rank'] = es_ranks.get(product_id)
            product['vector_rank'] = vector_ranks.get(product_id)
            
            # Determine search source
            if product_id in es_ranks and product_id in vector_ranks:
                product['search_source'] = 'both'
                product['keyword_score'] = product.get('_score', 0)
                product['semantic_score'] = product.get('_similarity_score', 0)
            elif product_id in es_ranks:
                product['search_source'] = 'elasticsearch'
                product['keyword_score'] = product.get('_score', 0)
                product['semantic_score'] = 0
            else:
                product['search_source'] = 'vector'
                product['keyword_score'] = 0
                product['semantic_score'] = product.get('_similarity_score', 0)
        
        # Sort by RRF score (descending)
        fused_products = list(all_products.values())
        fused_products.sort(key=lambda x: x['rrf_score'], reverse=True)
        
        print(f"🎯 RRF Fusion complete: {len(fused_products)} unique products")
        print(f"   Top 5 RRF results:")
        for i, product in enumerate(fused_products[:5]):
            print(f"     {i+1}. {product.get('name', 'Unknown')} (RRF: {product['rrf_score']:.4f}, Source: {product['search_source']})")
        
        return fused_products[:max_results]

class HybridProductRetrieverAgent(AIProvider):
    """Hybrid product retriever using Elasticsearch for both keyword and semantic search with RRF fusion"""
    
    def __init__(
        self, 
        base_provider: AIProvider,
        azure_embedding_endpoint: str = None,
        azure_embedding_key: str = None,
        rrf_k: float = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.elasticsearch = get_elasticsearch_service()
        
        # Use settings if not provided
        azure_embedding_endpoint = azure_embedding_endpoint or settings.azure_embedding_endpoint
        azure_embedding_key = azure_embedding_key or settings.azure_embedding_api_key
        
        if azure_embedding_endpoint and azure_embedding_key:
            self.vector_service = get_elasticsearch_vector_service(
                azure_embedding_endpoint, 
                azure_embedding_key
            )
        else:
            self.vector_service = None
            logger.warning("Azure embedding credentials not configured - vector search will be disabled")
        
        # Initialize RRF fusion with configurable k
        rrf_k = rrf_k or settings.rrf_k
        self.rrf_fusion = RRFHybridFusion(k=rrf_k)
        logger.info(f"Hybrid Product Retriever initialized with RRF k={rrf_k}")
        
    @property
    def provider_name(self) -> str:
        return f"hybrid_product_retriever_rrf_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured() and self.vector_service is not None
    
    async def initialize(self):
        """Initialize both search services"""
        try:
            if self.vector_service:
                await self.vector_service.initialize()
                logger.info("Hybrid Product Retriever (Elasticsearch Vector + RRF) initialized successfully")
            else:
                logger.warning("Vector service not available - using keyword search only")
        except Exception as e:
            logger.error(f"Failed to initialize Hybrid Product Retriever: {e}")
            raise
    
    async def generate_response(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """This agent doesn't generate conversational responses directly"""
        # Track token usage from base provider
        if hasattr(self.base_provider, 'usage_tracker'):
            self.usage_tracker = self.base_provider.usage_tracker
            
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
        """Extract requirements using the base provider, and auto-fill technical requirements if missing or too generic"""
        
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

            # --- AUTO-FILL TECHNICAL REQUIREMENTS IF MISSING OR TOO GENERIC ---
            tech_reqs = requirements_dict.get('technical_requirements', [])
            generic_terms = {'standard performance', 'basic specifications', 'standard', 'basic', 'default', 'none', ''}
            needs_autofill = (
                not tech_reqs or
                all(str(req).strip().lower() in generic_terms for req in tech_reqs)
            )
            if needs_autofill:
                # Build a prompt to infer technical specs from use case and conversation
                use_case = requirements_dict.get('use_case', '')
                autofill_prompt = f"""You are a technical solutions expert. The user was unable to specify detailed technical requirements. Based on the following use case and conversation, infer the most appropriate technical specifications (CPU, GPU, RAM, storage, PSU, etc.) for a system that would fully satisfy the user's needs. Be as specific as possible.

USE CASE: {use_case or 'Not specified'}

CONVERSATION:
{conversation_text}

Return a bullet list of technical requirements (one per line, e.g., 'GPU: NVIDIA RTX 4080 or better')."""
                print("🤖 Auto-filling technical requirements using LLM...")
                autofill_response = await self.base_provider.generate_response([
                    AIMessage(role="user", content=autofill_prompt)
                ])
                # Parse the response into a list
                import re
                lines = [line.strip('-•* 	') for line in autofill_response.content.split('\n') if line.strip()]
                # Only keep lines that look like specs
                filled_tech_reqs = [line for line in lines if ':' in line or re.search(r'\d', line)]
                if filled_tech_reqs:
                    requirements_dict['technical_requirements'] = filled_tech_reqs
                    requirements_dict['technical_requirements_autofilled'] = True
                    print(f"✅ Auto-filled technical requirements: {filled_tech_reqs}")
                else:
                    print("⚠️ LLM did not return detailed technical requirements. Keeping original.")
                    requirements_dict['technical_requirements_autofilled'] = False
            else:
                requirements_dict['technical_requirements_autofilled'] = False

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
        """Build a comprehensive natural language query for semantic search without category restrictions"""
        
        query_parts = []
        
        # Add use case and business context
        use_case = requirements.get('use_case', '')
        if use_case:
            query_parts.append(use_case)
        
        # Add technical requirements with more detail
        tech_reqs = requirements.get('technical_requirements', [])
        if tech_reqs:
            # Convert to string and add context
            tech_text = ' '.join([str(req) for req in tech_reqs if str(req)])
            if tech_text:
                query_parts.append(f"Technical requirements: {tech_text}")
        
        # Add business requirements
        business_reqs = requirements.get('business_requirements', [])
        if business_reqs:
            business_text = ' '.join([str(req) for req in business_reqs if str(req)])
            if business_text:
                query_parts.append(f"Business needs: {business_text}")
        
        # Add search terms as additional context (not as filters)
        search_terms = requirements.get('search_terms', [])
        if search_terms:
            search_text = ' '.join([str(term) for term in search_terms if str(term)])
            if search_text:
                query_parts.append(f"Looking for: {search_text}")
        
        # Add industry context if available
        industry = requirements.get('industry', '')
        if industry:
            query_parts.append(f"Industry: {industry}")
        
        # Add product categories as context, not filters
        categories = requirements.get('product_categories', [])
        if categories:
            categories_text = ', '.join(categories)
            query_parts.append(f"Product types: {categories_text}")
        
        # Add performance requirements if mentioned
        performance_reqs = requirements.get('performance_requirements', [])
        if performance_reqs:
            perf_text = ' '.join([str(req) for req in performance_reqs if str(req)])
            if perf_text:
                query_parts.append(f"Performance needs: {perf_text}")
        
        # Build comprehensive query
        comprehensive_query = " ".join(query_parts)
        
        # If no specific requirements, create a general business query
        if not comprehensive_query.strip():
            comprehensive_query = "business technology solutions professional enterprise"
        
        print(f"🔍 Built comprehensive semantic query: {comprehensive_query}")
        return comprehensive_query
    
    async def _perform_hybrid_search(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Perform hybrid search using Elasticsearch keyword and vector search with RRF fusion"""
        
        print("🔍 Performing hybrid search (Elasticsearch keyword + vector + RRF)...")
        
        # Check if vector search is available
        if not self.vector_service:
            print("⚠️ Vector service not available - using keyword search only")
            elasticsearch_products = await self._elasticsearch_search(requirements)
            vector_products = []
            vector_solutions = []
        else:
            # Parallel searches for better performance
            elasticsearch_products, vector_products, vector_solutions = await asyncio.gather(
                self._elasticsearch_search(requirements),
                self._elasticsearch_vector_search_products(requirements),
                self._elasticsearch_vector_search_solutions(requirements),
                return_exceptions=True
            )
        
        # Handle exceptions
        if isinstance(elasticsearch_products, Exception):
            print(f"⚠️ Elasticsearch search failed: {elasticsearch_products}")
            elasticsearch_products = []
            
        if isinstance(vector_products, Exception):
            print(f"⚠️ Elasticsearch vector product search failed: {vector_products}")
            vector_products = []
            
        if isinstance(vector_solutions, Exception):
            print(f"⚠️ Elasticsearch vector solution search failed: {vector_solutions}")
            vector_solutions = []
        
        # Debug logging before merge
        print(f"🔍 Pre-merge counts:")
        print(f"   Elasticsearch products: {len(elasticsearch_products)}")
        print(f"   Vector products: {len(vector_products)}")
        print(f"   Vector solutions: {len(vector_solutions)}")
        
        # Merge product results using RRF fusion
        if settings.use_rrf_merging:
            merged_products = self._merge_product_results_rrf(elasticsearch_products, vector_products)
        else:
            # Fallback to simple merge if RRF is disabled
            merged_products = self._merge_product_results_simple(elasticsearch_products, vector_products)
        
        # Track search methods
        search_methods = {
            'elasticsearch_products': len(elasticsearch_products),
            'vector_products': len(vector_products),
            'vector_solutions': len(vector_solutions),
            'merged_products': len(merged_products),
            'fusion_method': 'rrf' if settings.use_rrf_merging else 'simple'
        }
        
        print(f"🎯 Hybrid search complete:")
        print(f"   Final merged products: {len(merged_products)}")
        print(f"   Vector solutions: {len(vector_solutions)}")
        print(f"   Search methods: {search_methods}")
        
        return {
            'products': merged_products,
            'solutions': vector_solutions,
            'search_methods': search_methods
        }
    
    async def _elasticsearch_search(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search using Elasticsearch keyword search"""
        try:
            max_results = settings.max_search_results_per_source
            return await self.elasticsearch.search_products_by_requirements(requirements, size=max_results)
        except Exception as e:
            print(f"❌ Elasticsearch search failed: {e}")
            return []
    
    async def _elasticsearch_vector_search_products(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search products using Elasticsearch vector search with improved relevance"""
        if not self.vector_service:
            return []
            
        try:
            semantic_query = requirements.get('semantic_query', '')
            if not semantic_query:
                return []
            
            # Remove category filtering - let semantic search find relevant products across all categories
            # Instead, use semantic similarity and keyword matching for better relevance
            
            print(f"🧠 Vector search query: {semantic_query}")
            
            max_results = settings.max_search_results_per_source
            
            return await self.vector_service.vector_search_products(
                query=semantic_query,
                size=max_results,
                filters=None,  # No category filters - let semantic search work across all categories
                hybrid_weight=0.2  # Slightly higher hybrid weight for better text matching
            )
            
        except Exception as e:
            print(f"❌ Vector search failed: {e}")
            return []
    
    async def _elasticsearch_vector_search_solutions(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search solutions using Elasticsearch vector search with improved relevance"""
        if not self.vector_service:
            return []
            
        try:
            semantic_query = requirements.get('semantic_query', '')
            if not semantic_query:
                return []
            
            # Remove industry filtering - let semantic search find relevant solutions
            # Industry can be used as context in the query instead of a filter
            
            print(f"🧠 Vector solution search query: {semantic_query}")
            
            max_results = settings.max_search_results_per_source
            
            return await self.vector_service.vector_search_solutions(
                query=semantic_query,
                size=max_results,
                filters=None,  # Remove industry filters
                hybrid_weight=0.2  # Increased text search weight for better keyword matching
            )
        except Exception as e:
            print(f"❌ Elasticsearch vector solution search failed: {e}")
            return []
    
    def _merge_product_results_rrf(
        self, 
        elasticsearch_products: List[Dict], 
        vector_products: List[Dict]
    ) -> List[Dict]:
        """Merge and deduplicate product results using RRF (Reciprocal Rank Fusion)"""
        
        print(f"🔀 Starting RRF merge process...")
        print(f"   Input: {len(elasticsearch_products)} ES products, {len(vector_products)} vector products")
        
        # Use RRF fusion to combine rankings
        fused_products = self.rrf_fusion.fuse_rankings(
            elasticsearch_products=elasticsearch_products,
            vector_products=vector_products,
            max_results=settings.final_result_limit
        )
        
        # Add hybrid_score for backward compatibility (use RRF score)
        for product in fused_products:
            product['hybrid_score'] = product.get('rrf_score', 0)
        
        print(f"🎯 RRF merge complete: {len(fused_products)} unique products")
        print(f"   Top 5 results:")
        for i, product in enumerate(fused_products[:5]):
            print(f"     {i+1}. {product.get('name', 'Unknown')} (RRF: {product.get('rrf_score', 0):.4f}, Source: {product.get('search_source', 'unknown')})")
        
        return fused_products
    
    def _merge_product_results_simple(
        self, 
        elasticsearch_products: List[Dict], 
        vector_products: List[Dict]
    ) -> List[Dict]:
        """Simple merge when RRF is disabled - combine and deduplicate by ID"""
        
        print(f"🔀 Starting simple merge process (RRF disabled)...")
        print(f"   Input: {len(elasticsearch_products)} ES products, {len(vector_products)} vector products")
        
        # Create a dictionary to deduplicate by ID
        merged_dict = {}
        
        # Add Elasticsearch products first
        for product in elasticsearch_products:
            product_id = product.get('id', '')
            if product_id:
                product['search_source'] = 'elasticsearch'
                product['keyword_score'] = product.get('_score', 0)
                product['semantic_score'] = 0
                merged_dict[product_id] = product
        
        # Add vector products, keeping the higher score if duplicate
        for product in vector_products:
            product_id = product.get('id', '')
            if product_id:
                if product_id in merged_dict:
                    # Product exists in both sources
                    existing = merged_dict[product_id]
                    existing['search_source'] = 'both'
                    existing['semantic_score'] = product.get('_similarity_score', 0)
                    # Keep the higher score
                    if product.get('_similarity_score', 0) > existing.get('keyword_score', 0):
                        merged_dict[product_id] = product
                        product['search_source'] = 'both'
                        product['keyword_score'] = existing.get('_score', 0)
                else:
                    # New product from vector search
                    product['search_source'] = 'vector'
                    product['keyword_score'] = 0
                    product['semantic_score'] = product.get('_similarity_score', 0)
                    merged_dict[product_id] = product
        
        # Convert to list and sort by score
        merged_products = list(merged_dict.values())
        merged_products.sort(key=lambda x: max(x.get('keyword_score', 0), x.get('semantic_score', 0)), reverse=True)
        
        # Limit results
        max_results = settings.final_result_limit
        merged_products = merged_products[:max_results]
        
        print(f"🎯 Simple merge complete: {len(merged_products)} unique products")
        print(f"   Top 5 results:")
        for i, product in enumerate(merged_products[:5]):
            score = max(product.get('keyword_score', 0), product.get('semantic_score', 0))
            print(f"     {i+1}. {product.get('name', 'Unknown')} (Score: {score:.2f}, Source: {product.get('search_source', 'unknown')})")
        
        return merged_products
    
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
{json.dumps(products, indent=2)}

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
        """Calculate confidence based on RRF hybrid search results"""
        
        score = 0.0
        
        products = hybrid_results.get('products', [])
        solutions = hybrid_results.get('solutions', [])
        search_methods = hybrid_results.get('search_methods', {})
        fusion_method = search_methods.get('fusion_method', 'unknown')
        
        # Base score for finding results
        if products:
            score += 0.3
        if solutions:
            score += 0.2
        
        # RRF-specific confidence calculation
        if fusion_method == 'rrf':
            # Bonus for hybrid matches (found in both sources) - RRF handles this better
            hybrid_matches = len([p for p in products if p.get('search_source') == 'both'])
            if hybrid_matches > 0:
                score += 0.25 * min(hybrid_matches / 5, 1.0)  # Up to 25% bonus
            
            # Bonus for high RRF scores (indicates strong consensus)
            high_rrf_products = len([p for p in products if p.get('rrf_score', 0) > 0.02])
            if high_rrf_products > 0:
                score += 0.15 * min(high_rrf_products / 3, 1.0)  # Up to 15% bonus
            
            # Bonus for balanced results from both sources
            es_count = search_methods.get('elasticsearch_products', 0)
            vector_count = search_methods.get('vector_products', 0)
            if es_count > 0 and vector_count > 0:
                balance_ratio = min(es_count, vector_count) / max(es_count, vector_count)
                score += 0.1 * balance_ratio  # Up to 10% bonus for balanced results
        else:
            # Simple fusion confidence calculation
            hybrid_matches = len([p for p in products if p.get('search_source') == 'both'])
            if hybrid_matches > 0:
                score += 0.2 * min(hybrid_matches / 5, 1.0)  # Up to 20% bonus
            
            # Bonus for high scores in simple fusion
            high_score_products = len([p for p in products if max(p.get('keyword_score', 0), p.get('semantic_score', 0)) > 5.0])
            if high_score_products > 0:
                score += 0.1 * min(high_score_products / 3, 1.0)  # Up to 10% bonus
        
        # Bonus for high semantic similarity in vector-only results
        high_semantic_products = len([p for p in products if p.get('semantic_score', 0) > 0.8])
        if high_semantic_products > 0:
            score += 0.1 * min(high_semantic_products / 3, 1.0)  # Up to 10% bonus
        
        return min(score, 1.0)
    
    async def retrieve_products(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main interface for hybrid product retrieval using RRF fusion"""
        
        try:
            print(f"🔍 Hybrid Product Retriever (RRF): Starting analysis...")
            
            # Extract requirements
            requirements = await self._extract_requirements_from_conversation(messages, customer_context)
            
            # Perform hybrid search
            hybrid_results = await self._perform_hybrid_search(requirements)
            
            # Calculate confidence
            confidence = self._calculate_hybrid_confidence(hybrid_results, requirements)
            
            # Build RRF parameters for response
            rrf_parameters = {
                'k': self.rrf_fusion.k,
                'elasticsearch_weight': settings.rrf_elasticsearch_weight,
                'semantic_weight': settings.rrf_semantic_weight,
                'description': 'Reciprocal Rank Fusion parameters for hybrid search result merging'
            }
            
            # Return structured response
            retrieval_result = {
                'products': hybrid_results['products'],
                'solutions': hybrid_results['solutions'],
                'requirements': requirements,
                'total_products': len(hybrid_results['products']),
                'total_solutions': len(hybrid_results['solutions']),
                'search_methods': hybrid_results['search_methods'],
                'retrieval_method': 'hybrid_elasticsearch_vector_rrf',
                'fusion_method': hybrid_results['search_methods'].get('fusion_method', 'unknown'),
                'rrf_parameters': rrf_parameters,
                'retrieval_confidence': confidence,
                'success': True
            }
            
            print(f"✅ RRF Hybrid Retriever: Found {len(hybrid_results['products'])} products, {len(hybrid_results['solutions'])} solutions")
            print(f"   Confidence: {confidence:.1%}")
            print(f"   Fusion method: {retrieval_result['fusion_method']}")
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
                'fusion_method': 'none',
                'rrf_parameters': {},
                'retrieval_confidence': 0.0,
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
async def run_async(coro):
    """Helper to run async code"""
    return await coro 