import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from .base import AIProvider, AIMessage, AIResponse
from services.elasticsearch_service import get_elasticsearch_service
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from .function_models import RequirementExtraction, ProductAnalysis

logger = logging.getLogger(__name__)

class HybridProductRetrieverAgent(AIProvider):
    """Hybrid product retriever using Elasticsearch for both keyword and semantic search"""
    
    def __init__(
        self, 
        base_provider: AIProvider,
        azure_embedding_endpoint: str,
        azure_embedding_key: str,
        rrf_k: int = 60,  # RRF parameter - lower values favor top-ranked results more
        rrf_weights: Dict[str, float] = None,  # Optional weights for different search methods
        **kwargs
    ):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.elasticsearch = get_elasticsearch_service()
        self.vector_service = get_elasticsearch_vector_service(
            azure_embedding_endpoint, 
            azure_embedding_key
        )
        self.rrf_k = rrf_k
        self.rrf_weights = rrf_weights or {"elasticsearch": 1.0, "vector": 1.0}
        
    @property
    def provider_name(self) -> str:
        return f"hybrid_product_retriever_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def initialize(self):
        """Initialize both search services"""
        try:
            await self.vector_service.initialize()
            logger.info("Hybrid Product Retriever (Elasticsearch Vector) initialized successfully")
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
        """Analyze conversation and retrieve products using hybrid approach with RRF"""
        
        print("🔍 Hybrid Retriever Agent: Starting hybrid analysis with RRF...")
        
        # Step 1: Extract requirements
        requirements = await self._extract_requirements_from_conversation(
            conversation_messages, customer_context
        )
        
        # Step 2: Perform hybrid search
        hybrid_results = await self._perform_hybrid_search(requirements)
        
        # Step 3: Analyze RRF performance
        rrf_analysis = self.analyze_rrf_performance(hybrid_results["products"])
        rrf_tuning = self.suggest_rrf_tuning(rrf_analysis)
        
        # Step 4: Analyze and rank results
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
            "rrf_analysis": rrf_analysis,
            "rrf_tuning_suggestions": rrf_tuning,
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
        """Perform hybrid search using Elasticsearch keyword and vector search"""
        
        print("🔍 Performing hybrid search (Elasticsearch keyword + vector)...")
        
        # Parallel searches
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
        
        # Merge product results
        merged_products = self._merge_product_results(elasticsearch_products, vector_products)
        
        # Track search methods
        search_methods = {
            'elasticsearch_products': len(elasticsearch_products),
            'vector_products': len(vector_products),
            'vector_solutions': len(vector_solutions),
            'merged_products': len(merged_products)
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
        """Search using Elasticsearch"""
        try:
            return await self.elasticsearch.search_products_by_requirements(requirements, size=15)
        except Exception as e:
            print(f"❌ Elasticsearch search failed: {e}")
            return []
    
    async def _elasticsearch_vector_search_products(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search products using Elasticsearch vector search"""
        try:
            semantic_query = requirements.get('semantic_query', '')
            if not semantic_query:
                return []
            
            # Build category filter if available
            filters = None
            categories = requirements.get('product_categories', [])
            if categories:
                filters = {"category": categories}
            
            return await self.vector_service.vector_search_products(
                query=semantic_query,
                size=15,
                filters=filters,
                hybrid_weight=0.1  # Small weight for text search
            )
        except Exception as e:
            print(f"❌ Elasticsearch vector product search failed: {e}")
            return []
    
    async def _elasticsearch_vector_search_solutions(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search solutions using Elasticsearch vector search"""
        try:
            semantic_query = requirements.get('semantic_query', '')
            if not semantic_query:
                return []
            
            # Build industry filter if available
            filters = None
            industry = requirements.get('industry', '')
            if industry:
                filters = {"industry": [industry] if isinstance(industry, str) else industry}
            
            return await self.vector_service.vector_search_solutions(
                query=semantic_query,
                size=10,
                filters=filters,
                hybrid_weight=0.1  # Small weight for text search
            )
        except Exception as e:
            print(f"❌ Elasticsearch vector solution search failed: {e}")
            return []
    
    def _merge_product_results_with_rrf(
        self, 
        elasticsearch_products: List[Dict], 
        vector_products: List[Dict],
        k: int = None,  # RRF parameter - controls the balance between rank and score
        weights: Dict[str, float] = None  # Optional weights for different search methods
    ) -> List[Dict]:
        """Merge product results using Reciprocal Rank Fusion (RRF) with optional weighting"""
        
        # Use instance defaults if not provided
        k = k or self.rrf_k
        weights = weights or self.rrf_weights
        
        print(f"🔀 Starting RRF merge process...")
        print(f"   Input: {len(elasticsearch_products)} ES products, {len(vector_products)} vector products")
        print(f"   RRF parameter k: {k}")
        print(f"   Weights: ES={weights.get('elasticsearch', 1.0):.2f}, Vector={weights.get('vector', 1.0):.2f}")
        
        # Step 1: Create rank mappings for each search method
        es_ranks = {}  # product_id -> rank (1-based)
        vector_ranks = {}  # product_id -> rank (1-based)
        
        # Build Elasticsearch rank mapping
        for rank, product in enumerate(elasticsearch_products, 1):
            product_id = product.get('id', '')
            if product_id:
                es_ranks[product_id] = rank
                print(f"   📋 ES Rank {rank}: {product.get('name', 'Unknown')} (Score: {product.get('_score', 0):.3f})")
        
        # Build Vector search rank mapping
        for rank, product in enumerate(vector_products, 1):
            product_id = product.get('id', '')
            if product_id:
                vector_ranks[product_id] = rank
                print(f"   🧠 Vector Rank {rank}: {product.get('name', 'Unknown')} (Score: {product.get('_similarity_score', 0):.3f})")
        
        # Step 2: Collect all unique products
        all_products = {}
        
        # Add Elasticsearch products
        for product in elasticsearch_products:
            product_id = product.get('id', '')
            if product_id:
                product_copy = product.copy()
                product_copy['search_source'] = 'elasticsearch'
                product_copy['keyword_score'] = product.get('_score', 0)
                product_copy['semantic_score'] = 0
                product_copy['es_rank'] = es_ranks[product_id]
                product_copy['vector_rank'] = None
                all_products[product_id] = product_copy
        
        # Add/merge Vector products
        for product in vector_products:
            product_id = product.get('id', '')
            if product_id:
                similarity_score = product.get('_similarity_score', product.get('_score', 0))
                
                if product_id in all_products:
                    # Product found in both sources
                    all_products[product_id]['search_source'] = 'both'
                    all_products[product_id]['semantic_score'] = similarity_score
                    all_products[product_id]['vector_rank'] = vector_ranks[product_id]
                    print(f"   🔗 Found in both: {product.get('name', 'Unknown')}")
                else:
                    # Only found in vector search
                    product_copy = product.copy()
                    product_copy['search_source'] = 'vector'
                    product_copy['keyword_score'] = 0
                    product_copy['semantic_score'] = similarity_score
                    product_copy['es_rank'] = None
                    product_copy['vector_rank'] = vector_ranks[product_id]
                    all_products[product_id] = product_copy
        
        # Step 3: Calculate weighted RRF scores
        print(f"\n🧮 Calculating weighted RRF scores (k={k})...")
        
        for product_id, product in all_products.items():
            rrf_score = 0.0
            score_components = []
            
            # Add Elasticsearch contribution with weight
            if product['es_rank'] is not None:
                es_contribution = weights.get('elasticsearch', 1.0) / (k + product['es_rank'])
                rrf_score += es_contribution
                score_components.append(f"ES: {weights.get('elasticsearch', 1.0):.2f}/({k}+{product['es_rank']}) = {es_contribution:.4f}")
            
            # Add Vector search contribution with weight
            if product['vector_rank'] is not None:
                vector_contribution = weights.get('vector', 1.0) / (k + product['vector_rank'])
                rrf_score += vector_contribution
                score_components.append(f"Vector: {weights.get('vector', 1.0):.2f}/({k}+{product['vector_rank']}) = {vector_contribution:.4f}")
            
            product['rrf_score'] = rrf_score
            product['rrf_components'] = score_components
            
            print(f"   📊 {product.get('name', 'Unknown')[:30]}: RRF={rrf_score:.4f} [{', '.join(score_components)}]")
        
        # Step 4: Sort by RRF score and return results
        result = sorted(all_products.values(), key=lambda x: x['rrf_score'], reverse=True)
        
        print(f"\n🎯 RRF merge complete: {len(result)} unique products")
        print(f"   Top 10 RRF results:")
        for i, product in enumerate(result[:10]):
            source_icon = {"elasticsearch": "📋", "vector": "🧠", "both": "🔗"}.get(product['search_source'], "❓")
            print(f"     {i+1}. {source_icon} {product.get('name', 'Unknown')[:40]} (RRF: {product['rrf_score']:.4f})")
        
        return result[:20]  # Top 20 results
    
    def _merge_product_results(
        self, 
        elasticsearch_products: List[Dict], 
        vector_products: List[Dict]
    ) -> List[Dict]:
        """Merge and deduplicate product results using RRF (wrapper for backward compatibility)"""
        return self._merge_product_results_with_rrf(elasticsearch_products, vector_products)
    
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
    
    def analyze_rrf_performance(self, merged_results: List[Dict]) -> Dict[str, Any]:
        """Analyze the performance and distribution of RRF results"""
        
        if not merged_results:
            return {"error": "No results to analyze"}
        
        # Count by search source
        source_counts = {"elasticsearch": 0, "vector": 0, "both": 0}
        rrf_scores = []
        
        for result in merged_results:
            source = result.get('search_source', 'unknown')
            if source in source_counts:
                source_counts[source] += 1
            rrf_scores.append(result.get('rrf_score', 0))
        
        # Calculate statistics
        avg_rrf_score = sum(rrf_scores) / len(rrf_scores) if rrf_scores else 0
        max_rrf_score = max(rrf_scores) if rrf_scores else 0
        min_rrf_score = min(rrf_scores) if rrf_scores else 0
        
        # Calculate diversity (how well RRF is combining different sources)
        diversity_score = source_counts['both'] / len(merged_results) if merged_results else 0
        
        analysis = {
            "total_results": len(merged_results),
            "source_distribution": source_counts,
            "diversity_score": diversity_score,  # Higher is better (more overlap)
            "rrf_score_stats": {
                "average": avg_rrf_score,
                "max": max_rrf_score,
                "min": min_rrf_score,
                "range": max_rrf_score - min_rrf_score
            },
            "top_3_results": [
                {
                    "name": result.get('name', 'Unknown'),
                    "source": result.get('search_source'),
                    "rrf_score": result.get('rrf_score', 0),
                    "es_rank": result.get('es_rank'),
                    "vector_rank": result.get('vector_rank')
                }
                for result in merged_results[:3]
            ]
        }
        
        return analysis
    
    def suggest_rrf_tuning(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest RRF parameter tuning based on performance analysis"""
        
        suggestions = []
        
        diversity_score = analysis.get('diversity_score', 0)
        source_dist = analysis.get('source_distribution', {})
        
        # Analyze diversity
        if diversity_score < 0.1:
            suggestions.append({
                "issue": "Low diversity - results mostly from single source",
                "suggestion": "Consider adjusting search parameters or RRF weights to get more overlap",
                "current_k": self.rrf_k,
                "suggested_k": max(30, self.rrf_k - 20)  # Lower k gives more weight to top results
            })
        elif diversity_score > 0.8:
            suggestions.append({
                "issue": "Very high overlap - might be missing unique results",
                "suggestion": "Consider increasing search size or adjusting filters",
                "current_k": self.rrf_k,
                "suggested_k": min(100, self.rrf_k + 20)  # Higher k spreads weight more evenly
            })
        
        # Analyze source balance
        total_results = analysis.get('total_results', 0)
        if total_results > 0:
            es_ratio = source_dist.get('elasticsearch', 0) / total_results
            vector_ratio = source_dist.get('vector', 0) / total_results
            
            if es_ratio > 0.7:
                suggestions.append({
                    "issue": "Elasticsearch results dominating",
                    "suggestion": "Increase vector search weight",
                    "current_weights": self.rrf_weights,
                    "suggested_weights": {
                        "elasticsearch": max(0.5, self.rrf_weights.get('elasticsearch', 1.0) - 0.3),
                        "vector": min(2.0, self.rrf_weights.get('vector', 1.0) + 0.5)
                    }
                })
            elif vector_ratio > 0.7:
                suggestions.append({
                    "issue": "Vector search results dominating",
                    "suggestion": "Increase elasticsearch search weight",
                    "current_weights": self.rrf_weights,
                    "suggested_weights": {
                        "elasticsearch": min(2.0, self.rrf_weights.get('elasticsearch', 1.0) + 0.5),
                        "vector": max(0.5, self.rrf_weights.get('vector', 1.0) - 0.3)
                    }
                })
        
        return {
            "suggestions": suggestions,
            "current_config": {
                "rrf_k": self.rrf_k,
                "rrf_weights": self.rrf_weights
            }
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
        
        # Base score for finding results
        if products:
            score += 0.3
        if solutions:
            score += 0.1
        
        if products:
            # Analyze RRF performance
            rrf_analysis = self.analyze_rrf_performance(products)
            
            # Bonus for diversity (products found in both sources)
            diversity_score = rrf_analysis.get('diversity_score', 0)
            score += 0.3 * diversity_score
            
            # Bonus for high RRF scores (indicates strong ranking agreement)
            avg_rrf_score = rrf_analysis.get('rrf_score_stats', {}).get('average', 0)
            if avg_rrf_score > 0.02:  # Threshold for "good" RRF scores
                score += 0.2 * min(avg_rrf_score / 0.05, 1.0)  # Up to 20% bonus
            
            # Bonus for balanced source distribution
            source_dist = rrf_analysis.get('source_distribution', {})
            total_results = rrf_analysis.get('total_results', 0)
            if total_results > 0:
                # Calculate balance score (closer to 0.5 is better for each source)
                es_ratio = source_dist.get('elasticsearch', 0) / total_results
                vector_ratio = source_dist.get('vector', 0) / total_results
                both_ratio = source_dist.get('both', 0) / total_results
                
                # Reward balanced distribution
                balance_score = 1.0 - abs(es_ratio - vector_ratio)
                score += 0.1 * balance_score * both_ratio  # Weighted by overlap
        
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
                'retrieval_method': 'hybrid_elasticsearch_vector',
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
async def run_async(coro):
    """Helper to run async code"""
    return await coro 