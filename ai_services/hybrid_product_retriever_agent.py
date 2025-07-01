import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .base import AIProvider, AIMessage, AIResponse
from services.elasticsearch_vector_service import get_elasticsearch_service
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from .function_models import RequirementExtraction, ProductAnalysis
from config import settings

logger = logging.getLogger(__name__)

class ContextAnalysis(BaseModel):
    """LLM-powered context analysis for better product retrieval"""
    primary_need: str = Field(description="The main problem or need the customer is trying to solve")
    business_context: str = Field(description="Business context and industry considerations")
    technical_requirements: List[str] = Field(description="Technical requirements or constraints")
    budget_indicator: str = Field(description="Budget level indication (low/medium/high/enterprise)")
    timeline: str = Field(description="Implementation timeline (immediate/short-term/long-term)")
    similar_products: List[str] = Field(description="Similar products or solutions they might be interested in")
    search_keywords: List[str] = Field(description="Keywords to use for product search")
    semantic_queries: List[str] = Field(description="Semantic search queries for better matching")
    recommended_categories: List[str] = Field(description="Recommended product categories based on analysis", default_factory=list)
    category_confidence: float = Field(description="Confidence in category recommendations (0.0 to 1.0)", default=0.0)
    confidence: float = Field(description="Confidence in the analysis (0.0 to 1.0)")

class SimilarProductSearch(BaseModel):
    """LLM-powered similar product search analysis"""
    base_product: str = Field(description="The product they're asking about or similar to")
    search_criteria: List[str] = Field(description="Criteria for finding similar products")
    alternative_approaches: List[str] = Field(description="Alternative approaches or categories to consider")
    complementary_products: List[str] = Field(description="Products that work well together")
    upgrade_paths: List[str] = Field(description="Potential upgrade paths or next steps")

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
        Fuse product rankings using RRF with requirement-based diversity selection
        
        Args:
            elasticsearch_products: Products from keyword search with _score
            vector_products: Products from vector search with _similarity_score
            max_results: Maximum number of results to return
            
        Returns:
            Fused and ranked product list with requirement diversity
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
        
        # Apply requirement-based diversity selection
        fused_products = self._apply_requirement_diversity_selection(all_products, rrf_scores, max_results)
        
        print(f"🎯 RRF Fusion complete: {len(fused_products)} unique products")
        print(f"   Top 5 RRF results:")
        for i, product in enumerate(fused_products[:5]):
            print(f"     {i+1}. {product.get('name', 'Unknown')} (RRF: {product['rrf_score']:.4f}, Source: {product['search_source']})")
        
        return fused_products
    
    def _apply_requirement_diversity_selection(
        self, 
        all_products: Dict[str, Dict], 
        rrf_scores: Dict[str, float], 
        max_results: int
    ) -> List[Dict]:
        """Apply requirement-based diversity selection to ensure coverage of different needs"""
        
        print(f"🎯 Applying requirement-based diversity selection for {len(all_products)} products...")
        
        # Convert to list and sort by RRF score
        products_list = list(all_products.values())
        products_list.sort(key=lambda x: x['rrf_score'], reverse=True)
        
        # Define requirement groups based on common patterns
        requirement_groups = self._identify_requirement_groups(products_list)
        
        print(f"📊 Identified {len(requirement_groups)} requirement groups:")
        for group_name, group_products in requirement_groups.items():
            print(f"   {group_name}: {len(group_products)} products")
        
        # Allocate slots to each requirement group
        allocation = self._get_requirement_allocation(requirement_groups, max_results)
        
        print(f"📊 Requirement allocation:")
        for group, allocation_count in allocation.items():
            print(f"   {group}: {allocation_count} products")
        
        # Select products from each requirement group
        selected_products = []
        for group_name, allocation_count in allocation.items():
            if group_name in requirement_groups and allocation_count > 0:
                group_products = requirement_groups[group_name]
                # Take top products from this group
                for i in range(min(allocation_count, len(group_products))):
                    selected_products.append(group_products[i])
                    print(f"   ✅ Selected {group_products[i].get('name', 'Unknown')} from {group_name} (RRF: {group_products[i]['rrf_score']:.4f})")
        
        # If we haven't filled the quota, add remaining high-scoring products
        remaining_slots = max_results - len(selected_products)
        if remaining_slots > 0:
            print(f"📊 Adding {remaining_slots} additional high-scoring products...")
            
            # Get all unselected products
            selected_ids = {p.get('id') for p in selected_products}
            unselected_products = [p for p in products_list if p.get('id') not in selected_ids]
            
            # Add top remaining products
            for i in range(min(remaining_slots, len(unselected_products))):
                selected_products.append(unselected_products[i])
                print(f"   ✅ Added {unselected_products[i].get('name', 'Unknown')} (RRF: {unselected_products[i]['rrf_score']:.4f})")
        
        print(f"🎯 Requirement diversity selection complete: {len(selected_products)} products selected")
        return selected_products
    
    def _identify_requirement_groups(self, products: List[Dict]) -> Dict[str, List[Dict]]:
        """Identify requirement groups based on actual product categories and characteristics"""
        
        requirement_groups = {
            'core_compute': [],         # Most important for any build (CPU, GPU, motherboard)
            'memory_storage': [],       # Essential for performance (RAM, storage)
            'display': [],              # Important for usability (monitors)
            'power_cooling': [],        # Essential for stability (PSU, cooling)
            'input_devices': [],        # Important for usability (keyboard, mouse)
            'networking': [],           # Important for connectivity
            'cases_accessories': [],    # Nice to have (cases, cables)
            'audio_video': [],          # Nice to have (speakers, webcams)
            'other': []                 # Catch-all
        }
        
        # Category to group mapping based on actual product categories
        category_to_group = {
            'cpu': 'core_compute',
            'video-card': 'core_compute', 
            'memory': 'memory_storage',
            'internal-hard-drive': 'memory_storage',
            'external-hard-drive': 'memory_storage',
            'monitor': 'display',
            'keyboard': 'input_devices',
            'mouse': 'input_devices',
            'wireless-network-card': 'networking',
            'wired-network-card': 'networking',
            'power-supply': 'power_cooling',
            'cpu-cooler': 'power_cooling',
            'ups': 'power_cooling',
            'case': 'cases_accessories',
            'case-accessory': 'cases_accessories',
            'case-fan': 'power_cooling',
            'headphones': 'audio_video',
            'speakers': 'audio_video',
            'webcam': 'audio_video',
            'motherboard': 'core_compute',
            'optical-drive': 'other',
            'os': 'other',
            'sound-card': 'audio_video',
            'thermal-paste': 'cases_accessories',
            'fan-controller': 'power_cooling'
        }
        
        # Track categories found for logging
        categories_found = {}
        
        # Group products by their actual category
        for product in products:
            # Get the actual product category from the product data
            category = product.get('category', '').lower()
            
            # Track categories found
            if category:
                categories_found[category] = categories_found.get(category, 0) + 1
            
            # Map category to requirement group
            group_name = category_to_group.get(category, 'other')
            requirement_groups[group_name].append(product)
            
            logger.debug(f"Grouped product '{product.get('name', 'Unknown')}' (category: {category}) into {group_name}")
        
        # Log category diversity for debugging
        print(f"📊 Product categories found: {categories_found}")
        print(f"📊 Requirement groups populated:")
        for group_name, group_products in requirement_groups.items():
            if group_products:
                print(f"   {group_name}: {len(group_products)} products")
        
        # Remove empty groups
        requirement_groups = {k: v for k, v in requirement_groups.items() if v}
        
        return requirement_groups
    
    def _get_product_text(self, product: Dict) -> str:
        """Extract searchable text from product"""
        text_parts = []
        
        # Add name
        if product.get('name'):
            text_parts.append(product['name'])
        
        # Add description
        if product.get('description'):
            text_parts.append(product['description'])
        
        # Add category
        if product.get('category'):
            text_parts.append(product['category'])
        
        # Add brand/manufacturer
        if product.get('brand'):
            text_parts.append(product['brand'])
        elif product.get('manufacturer'):
            text_parts.append(product['manufacturer'])
        
        return ' '.join(text_parts)
    
    def _get_requirement_allocation(self, requirement_groups: Dict[str, List[Dict]], max_results: int) -> Dict[str, int]:
        """Get allocation for requirement groups based on importance and availability"""
        
        # Define group priorities (higher = more important)
        group_priorities = {
            'core_compute': 3,         # Most important for any build (CPU, GPU, motherboard)
            'memory_storage': 3,       # Essential for performance (RAM, storage)
            'display': 2,              # Important for usability (monitors)
            'power_cooling': 2,        # Essential for stability (PSU, cooling)
            'input_devices': 1,        # Important for usability (keyboard, mouse)
            'networking': 1,           # Important for connectivity
            'cases_accessories': 1,    # Nice to have (cases, cables)
            'audio_video': 1,          # Nice to have (speakers, webcams)
            'other': 1                 # Catch-all
        }
        
        # Calculate allocation based on priorities and available products
        total_priority = sum(group_priorities.get(group, 1) for group in requirement_groups.keys())
        
        allocation = {}
        for group_name in requirement_groups.keys():
            priority = group_priorities.get(group_name, 1)
            group_size = len(requirement_groups[group_name])
            
            # Base allocation based on priority
            base_allocation = max(1, int((priority / total_priority) * max_results * 0.7))
            
            # Adjust allocation based on group size (don't allocate more than available)
            group_allocation = min(base_allocation, group_size)
            
            # Ensure high-priority groups get at least 2 products if available
            if priority >= 3 and group_size >= 2:
                group_allocation = max(group_allocation, 2)
            
            allocation[group_name] = group_allocation
        
        # Ensure we don't exceed max_results
        total_allocated = sum(allocation.values())
        if total_allocated > max_results:
            # Reduce allocation proportionally, but preserve high-priority groups
            reduction_factor = max_results / total_allocated
            for group_name in allocation:
                priority = group_priorities.get(group_name, 1)
                if priority >= 3:
                    # Keep high-priority allocations, reduce others more
                    allocation[group_name] = max(1, int(allocation[group_name] * (reduction_factor + 0.2)))
                else:
                    allocation[group_name] = max(1, int(allocation[group_name] * reduction_factor))
        
        # Final check to ensure we don't exceed max_results
        total_allocated = sum(allocation.values())
        if total_allocated > max_results:
            # Remove allocation from lowest priority groups
            sorted_groups = sorted(allocation.items(), key=lambda x: group_priorities.get(x[0], 1))
            while total_allocated > max_results and sorted_groups:
                group_name, current_allocation = sorted_groups.pop(0)
                if current_allocation > 1:
                    allocation[group_name] -= 1
                    total_allocated -= 1
                elif current_allocation == 1:
                    allocation[group_name] = 0
                    total_allocated -= 1
        
        return allocation

    def fuse_rankings_per_category(
        self,
        elasticsearch_products: List[Dict],
        vector_products: List[Dict],
        categories: List[str],
        max_results: int = None
    ) -> List[Dict]:
        """
        Apply RRF fusion within each category and return equal number of products per category.
        """
        max_results = max_results or settings.final_result_limit
        num_categories = len(categories)
        if num_categories == 0:
            return []
        per_category = max_results // num_categories
        remainder = max_results % num_categories
        final_products = []
        used_ids = set()
        for i, category in enumerate(categories):
            n = per_category + (1 if i < remainder else 0)
            es_cat = [p for p in elasticsearch_products if p.get('category') == category]
            vec_cat = [p for p in vector_products if p.get('category') == category]
            fused = self.fuse_rankings(es_cat, vec_cat, max_results=n)
            for prod in fused:
                if prod.get('id') not in used_ids:
                    final_products.append(prod)
                    used_ids.add(prod.get('id'))
        return final_products

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
                # Set the LLM provider for intelligent category detection
                self.vector_service.set_llm_provider(self.base_provider)
                logger.info("✅ Hybrid Product Retriever (Elasticsearch Vector + RRF + LLM) initialized successfully")
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
        """
        Enhanced conversation analysis with LLM-powered context understanding
        """
        print("🧠 Hybrid Product Retriever: Starting LLM-powered context analysis...")
        
        try:
            # Step 1: LLM-powered context analysis
            context_analysis = await self._analyze_conversation_context(conversation_messages, customer_context)
            print(f"✅ Context Analysis: {context_analysis.primary_need}")
            print(f"   Keywords: {context_analysis.search_keywords}")
            print(f"   Semantic Queries: {context_analysis.semantic_queries}")
            print(f"🎯 Category Recommendations: {context_analysis.recommended_categories}")
            print(f"   Category Confidence: {context_analysis.category_confidence:.1%}")
            
            # Step 2: Enhanced requirement extraction with context
            requirements = await self._extract_requirements_with_context(conversation_messages, customer_context, context_analysis)
            
            # Step 3: Similar product analysis if applicable
            similar_products_analysis = None
            if context_analysis.similar_products:
                similar_products_analysis = await self._analyze_similar_products(context_analysis)
                print(f"🔍 Similar Products Analysis: {len(similar_products_analysis.search_criteria)} criteria")
            
            # Step 4: Enhanced hybrid search with LLM insights
            search_results = await self._perform_enhanced_hybrid_search(requirements, context_analysis, similar_products_analysis)
            
            # Step 5: LLM-powered result analysis and ranking
            final_results = await self._analyze_and_rank_results(search_results, context_analysis, requirements)
            
            return final_results
            
        except Exception as e:
            logger.error(f"Enhanced conversation analysis failed: {e}")
            # Fallback to original method
            return await self._fallback_analysis(conversation_messages, customer_context)
    
    async def _analyze_conversation_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> ContextAnalysis:
        """LLM-powered context analysis for better understanding of customer needs"""
        
        conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages[-5:]])  # Last 5 messages
        
        context_prompt = f"""Analyze this conversation to understand the customer's context and needs for better product matching.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT: {customer_context or 'None provided'}

ANALYSIS TASK:
1. Identify the primary problem or need they're trying to solve
2. Understand their business context and industry considerations
3. Extract technical requirements and constraints
4. Determine budget level and timeline indicators
5. Identify similar products or solutions they might be interested in
6. Generate effective search keywords and semantic queries
7. Assess confidence in the analysis

Focus on understanding their real needs, not just what they're asking for. Think about what would be most helpful for them."""

        try:
            # Step 1: Get basic context analysis
            context_analysis = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=context_prompt)],
                ContextAnalysis
            )
            
            # Step 2: Get category recommendations using the vector service's LLM analysis
            # Build requirements dict for category analysis
            requirements_for_categories = {
                'semantic_query': " ".join(context_analysis.semantic_queries),
                'technical_requirements': context_analysis.technical_requirements,
                'business_requirements': [context_analysis.business_context],
                'use_case': context_analysis.primary_need,
                'industry': customer_context.get('industry', '') if customer_context else '',
                'llm_context': {
                    'primary_need': context_analysis.primary_need,
                    'business_context': context_analysis.business_context,
                    'technical_requirements': context_analysis.technical_requirements,
                    'budget_indicator': context_analysis.budget_indicator,
                    'timeline': context_analysis.timeline
                }
            }
            
            categories, category_confidence = await self._get_category_recommendations(requirements_for_categories)
            
            # Update context analysis with category recommendations
            context_analysis.recommended_categories = categories
            context_analysis.category_confidence = category_confidence
            
            logger.info(f"✅ Enhanced Context Analysis:")
            logger.info(f"   Primary Need: {context_analysis.primary_need}")
            logger.info(f"   Technical Focus: {context_analysis.business_context}")
            logger.info(f"   Recommended Categories: {categories}")
            logger.info(f"   Category Confidence: {category_confidence:.1%}")
            logger.info(f"   Search Keywords: {context_analysis.search_keywords}")
            
            return context_analysis
            
        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            # Fallback analysis with empty categories
            return ContextAnalysis(
                primary_need="general business solution",
                business_context="standard business needs",
                technical_requirements=[],
                budget_indicator="medium",
                timeline="short-term",
                similar_products=[],
                search_keywords=["business", "solution"],
                semantic_queries=["business technology solution"],
                recommended_categories=[],
                category_confidence=0.0,
                confidence=0.3
            )
    
    async def _analyze_similar_products(self, context_analysis: ContextAnalysis) -> SimilarProductSearch:
        """LLM-powered analysis for finding similar products"""
        
        similar_prompt = f"""Based on the customer's context, analyze what similar products or solutions they might be interested in.

CONTEXT:
Primary Need: {context_analysis.primary_need}
Business Context: {context_analysis.business_context}
Similar Products Mentioned: {context_analysis.similar_products}

ANALYSIS TASK:
1. Identify the base product or category they're interested in
2. Determine search criteria for finding similar products
3. Suggest alternative approaches or categories
4. Identify complementary products that work well together
5. Suggest potential upgrade paths or next steps

Think broadly about their needs and suggest relevant alternatives."""

        try:
            similar_analysis = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=similar_prompt)],
                SimilarProductSearch
            )
            return similar_analysis
        except Exception as e:
            logger.error(f"Similar products analysis failed: {e}")
            return SimilarProductSearch(
                base_product="general solution",
                search_criteria=["business solution"],
                alternative_approaches=[],
                complementary_products=[],
                upgrade_paths=[]
            )
    
    async def _extract_requirements_with_context(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        context_analysis: ContextAnalysis
    ) -> Dict[str, Any]:
        """Enhanced requirement extraction using LLM context analysis"""
        
        # Use the context analysis to enhance requirement extraction
        enhanced_requirements = await self._extract_requirements_from_conversation(messages, customer_context)
        
        # Enhance with context analysis insights
        enhanced_requirements.update({
            'llm_context': {
                'primary_need': context_analysis.primary_need,
                'business_context': context_analysis.business_context,
                'technical_requirements': context_analysis.technical_requirements,
                'budget_indicator': context_analysis.budget_indicator,
                'timeline': context_analysis.timeline,
                'confidence': context_analysis.confidence,
                'recommended_categories': context_analysis.recommended_categories,
                'category_confidence': context_analysis.category_confidence
            },
            'search_keywords': context_analysis.search_keywords,
            'semantic_queries': context_analysis.semantic_queries,
            'similar_products': context_analysis.similar_products,
            'recommended_categories': context_analysis.recommended_categories,
            'category_confidence': context_analysis.category_confidence
        })
        
        logger.info(f"🔍 Enhanced Requirements with LLM Context:")
        logger.info(f"   Primary Need: {context_analysis.primary_need}")
        logger.info(f"   Recommended Categories: {context_analysis.recommended_categories}")
        logger.info(f"   Category Confidence: {context_analysis.category_confidence:.1%}")
        logger.info(f"   Search Keywords: {context_analysis.search_keywords}")
        
        return enhanced_requirements
    
    async def _perform_enhanced_hybrid_search(
        self,
        requirements: Dict[str, Any],
        context_analysis: ContextAnalysis,
        similar_products_analysis: Optional[SimilarProductSearch]
    ) -> Dict[str, Any]:
        """Perform enhanced hybrid search using LLM insights"""
        
        print("🔍 Enhanced Hybrid Search: Using LLM-powered context analysis...")
        
        # Use LLM-generated search keywords and semantic queries
        search_keywords = context_analysis.search_keywords
        semantic_queries = context_analysis.semantic_queries
        
        # Add similar products to search if available
        if similar_products_analysis:
            search_keywords.extend(similar_products_analysis.search_criteria)
            semantic_queries.extend(similar_products_analysis.alternative_approaches)
        
        # Preserve ALL existing requirements (including categories) and just add new insights
        requirements['search_keywords'] = search_keywords
        requirements['semantic_queries'] = semantic_queries
        
        # Perform the hybrid search with preserved requirements
        return await self._perform_hybrid_search(requirements)
    
    async def _fallback_analysis(
        self,
        conversation_messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback to original analysis method"""
        print("⚠️ Using fallback analysis method...")
        
        # Extract requirements
        requirements = await self._extract_requirements_from_conversation(conversation_messages, customer_context)
        
        # Perform hybrid search
        hybrid_results = await self._perform_hybrid_search(requirements)
        
        # Use per-category fusion for fallback if categories are present
        categories = requirements.get('recommended_categories') or requirements.get('llm_context', {}).get('recommended_categories')
        if categories:
            hybrid_results['products'] = self.rrf_fusion.fuse_rankings_per_category(
                [p for p in hybrid_results['products'] if p.get('search_source') in ('elasticsearch', 'both')],
                [p for p in hybrid_results['products'] if p.get('search_source') in ('vector', 'both')],
                categories,
                max_results=settings.final_result_limit
            )
        
        # Analyze results
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
        """Perform hybrid search combining elasticsearch and vector search with RRF fusion"""
        
        search_methods = {
            "methods": [],
            "fusion_enabled": settings.use_rrf_merging,
            "elasticsearch_weight": settings.rrf_elasticsearch_weight,
            "semantic_weight": settings.rrf_semantic_weight
        }
        
        print("🔍 Performing hybrid search with RRF fusion...")
        
        # Step 1: Elasticsearch keyword search
        print("📋 Step 1: Elasticsearch keyword search...")
        elasticsearch_products = await self._elasticsearch_search(requirements)
        search_methods["methods"].append("elasticsearch_keyword")
        search_methods["elasticsearch_count"] = len(elasticsearch_products)
        print(f"   Found {len(elasticsearch_products)} products via keyword search")
        
        # Step 2: Vector search for products
        vector_products = []
        if self.vector_service:
            print("🧠 Step 2: Vector search for products...")
            vector_products = await self._elasticsearch_vector_search_products(requirements)
            search_methods["methods"].append("vector_semantic")
            search_methods["vector_products_count"] = len(vector_products)
            print(f"   Found {len(vector_products)} products via vector search")
        
        # Step 3: Vector search for solutions
        vector_solutions = []
        if self.vector_service:
            print("🧠 Step 3: Vector search for solutions...")
            vector_solutions = await self._elasticsearch_vector_search_solutions(requirements)
            search_methods["methods"].append("vector_solutions")
            search_methods["vector_solutions_count"] = len(vector_solutions)
            print(f"   Found {len(vector_solutions)} solutions via vector search")
        
        # Step 4: RRF fusion for products
        print("🎯 Step 4: RRF fusion for products...")
        categories = requirements.get('recommended_categories') or requirements.get('llm_context', {}).get('recommended_categories')
        if settings.use_rrf_merging and categories:
            fused_products = self.rrf_fusion.fuse_rankings_per_category(
                elasticsearch_products, 
                vector_products,
                categories,
                max_results=settings.final_result_limit
            )
            search_methods["fusion_method"] = "rrf_per_category"
            print(f"   RRF per-category fusion complete: {len(fused_products)} products")
        elif settings.use_rrf_merging:
            fused_products = self.rrf_fusion.fuse_rankings(
                elasticsearch_products, 
                vector_products,
                max_results=settings.final_result_limit
            )
            search_methods["fusion_method"] = "rrf"
            print(f"   RRF fusion complete: {len(fused_products)} products")
        else:
            # Simple merge if RRF is disabled
            fused_products = self._merge_product_results_simple(
                elasticsearch_products, 
                vector_products
            )
            search_methods["fusion_method"] = "simple"
            print(f"   Simple merge complete: {len(fused_products)} products")
        
        # Step 5: Process solutions (no fusion needed for solutions)
        solutions = vector_solutions[:settings.final_result_limit] if vector_solutions else []
        
        return {
            "products": fused_products,
            "solutions": solutions,
            "search_methods": search_methods
        }
    
    async def _analyze_hybrid_recommendations(
        self, 
        products: List[Dict], 
        solutions: List[Dict], 
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze hybrid recommendations using Pydantic function calling"""
        
        # Use per-category fusion for analysis if categories are present
        categories = requirements.get('recommended_categories') or requirements.get('llm_context', {}).get('recommended_categories')
        if categories:
            # Re-fuse products per category for analysis
            products = self.rrf_fusion.fuse_rankings_per_category(
                [p for p in products if p.get('search_source') in ('elasticsearch', 'both')],
                [p for p in products if p.get('search_source') in ('vector', 'both')],
                categories,
                max_results=settings.final_result_limit
            )
        
        analysis_prompt = f"""You are a technical solution architect analyzing hybrid search results from both keyword and semantic search.

REQUIREMENTS:
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
            logger.error(f"Hybrid analysis failed: {e}")
            return {
                "analysis_summary": "Analysis failed - using fallback",
                "key_recommendations": [],
                "technical_insights": [],
                "business_benefits": [],
                "confidence_score": 0.3
            }
    
    async def _analyze_and_rank_results(
        self, 
        search_results: Dict[str, Any],
        context_analysis: ContextAnalysis,
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze and rank search results using LLM insights"""
        
        try:
            # Analyze hybrid recommendations
            analysis = await self._analyze_hybrid_recommendations(
                search_results["products"], 
                search_results["solutions"], 
                requirements
            )
            
            # Calculate confidence
            confidence = self._calculate_hybrid_confidence(search_results, requirements)
            
            return {
                "requirements": requirements,
                "products": search_results["products"],
                "solutions": search_results["solutions"],
                "analysis": analysis,
                "search_methods": search_results["search_methods"],
                "retrieval_confidence": confidence,
                "llm_context_used": True,
                "similar_products_analysis": context_analysis.similar_products is not None
            }
            
        except Exception as e:
            logger.error(f"Result analysis failed: {e}")
            return {
                "requirements": requirements,
                "products": search_results.get("products", []),
                "solutions": search_results.get("solutions", []),
                "analysis": {},
                "search_methods": search_results.get("search_methods", {}),
                "retrieval_confidence": 0.0,
                "llm_context_used": True,
                "similar_products_analysis": False,
                "error": str(e)
            }
    
    async def retrieve_products(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main interface for hybrid product retrieval using LLM-powered context analysis"""
        
        try:
            print(f"🧠 Hybrid Product Retriever: Starting LLM-powered analysis...")
            
            # Use the enhanced conversation analysis with LLM context
            enhanced_results = await self.analyze_conversation_and_retrieve(messages, customer_context)
            
            # Build RRF parameters for response
            rrf_parameters = {
                'k': self.rrf_fusion.k,
                'elasticsearch_weight': settings.rrf_elasticsearch_weight,
                'semantic_weight': settings.rrf_semantic_weight,
                'description': 'Reciprocal Rank Fusion parameters for hybrid search result merging'
            }
            
            # Return structured response with LLM context
            retrieval_result = {
                'products': enhanced_results.get('products', []),
                'solutions': enhanced_results.get('solutions', []),
                'requirements': enhanced_results.get('requirements', {}),
                'total_products': len(enhanced_results.get('products', [])),
                'total_solutions': len(enhanced_results.get('solutions', [])),
                'search_methods': enhanced_results.get('search_methods', {}),
                'retrieval_method': 'llm_enhanced_hybrid_elasticsearch_vector_rrf',
                'fusion_method': enhanced_results.get('search_methods', {}).get('fusion_method', 'unknown'),
                'rrf_parameters': rrf_parameters,
                'retrieval_confidence': enhanced_results.get('retrieval_confidence', 0.0),
                'llm_context_used': True,
                'similar_products_analysis': enhanced_results.get('similar_products_analysis', False),
                'success': True
            }
            
            print(f"✅ LLM-Enhanced Hybrid Retriever: Found {len(enhanced_results.get('products', []))} products, {len(enhanced_results.get('solutions', []))} solutions")
            print(f"   Confidence: {enhanced_results.get('retrieval_confidence', 0.0):.1%}")
            print(f"   LLM Context: {enhanced_results.get('requirements', {}).get('llm_context', {}).get('primary_need', 'Unknown')}")
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
                'llm_context_used': False,
                'similar_products_analysis': False,
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
            es_count = search_methods.get('elasticsearch_count', 0)
            vector_count = search_methods.get('vector_products_count', 0)
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

    async def _elasticsearch_search(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Perform Elasticsearch keyword search for products"""
        try:
            # Build search query from requirements
            search_terms = requirements.get('search_terms', [])
            product_categories = requirements.get('product_categories', [])
            use_case = requirements.get('use_case', '')
            
            # Combine search terms
            query_terms = search_terms + product_categories
            if use_case:
                query_terms.append(use_case)
            
            # Remove duplicates and empty strings
            query_terms = list(set([term for term in query_terms if term and term.strip()]))
            
            if not query_terms:
                query_terms = ['business', 'solution']  # Fallback
            
            # Build Elasticsearch query
            query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"name": {"query": term, "boost": 2.0}}} for term in query_terms
                        ] + [
                            {"match": {"description": {"query": term, "boost": 1.0}}} for term in query_terms
                        ] + [
                            {"match": {"category": {"query": term, "boost": 1.5}}} for term in query_terms
                        ]
                    }
                },
                "size": settings.final_result_limit
            }
            
            print(f"🔍 Elasticsearch query: {json.dumps(query, indent=2)}")
            
            # Perform search
            results = await self.elasticsearch.search_products(query)
            
            # Add search metadata
            for product in results:
                product['search_source'] = 'elasticsearch'
                product['keyword_score'] = product.get('_score', 0)
            
            return results
            
        except Exception as e:
            logger.error(f"Elasticsearch search failed: {e}")
            return []
    
    async def _elasticsearch_vector_search_products(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Perform vector search for products using semantic similarity with intelligent category filtering"""
        try:
            if not self.vector_service:
                return []
            
            # Use semantic query from requirements
            semantic_query = requirements.get('semantic_query', '')
            if not semantic_query:
                semantic_query = requirements.get('use_case', 'business solution')
            
            # Get category recommendations from multiple possible sources
            categories = None
            llm_context = requirements.get('llm_context', {})
            
            # Try multiple sources for categories (more robust)
            if requirements.get('recommended_categories'):
                categories = requirements['recommended_categories']
                logger.info(f"🎯 Using requirements recommended_categories: {categories}")
            elif llm_context.get('recommended_categories'):
                categories = llm_context['recommended_categories']
                logger.info(f"🎯 Using llm_context recommended_categories: {categories}")
            elif requirements.get('product_categories'):
                categories = requirements['product_categories']
                logger.info(f"🎯 Using product_categories as fallback: {categories}")
            
            # Normalize and validate categories
            categories = self._normalize_categories(categories)
            
            logger.info(f"🧠 Vector search query: {semantic_query}")
            if categories:
                logger.info(f"🎯 Final category filtering: {categories} (count: {len(categories)})")
            
            # Perform vector search with category filtering using the correct method name and parameter
            results = await self.vector_service.vector_search_products(
                semantic_query, 
                size=settings.final_result_limit,
                categories=categories  # Pass categories for intelligent filtering
            )
            
            # Add search metadata
            for product in results:
                product['search_source'] = 'vector'
                product['semantic_score'] = product.get('_similarity_score', 0)
                if categories:
                    product['category_filtered'] = True
                    product['filter_categories'] = categories
            
            logger.info(f"🧠 Vector search results: {len(results)} products")
            if categories:
                logger.info(f"   Category-filtered search for: {categories}")
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search for products failed: {e}")
            return []
    
    def _normalize_categories(self, categories) -> Optional[List[str]]:
        """Normalize and validate categories for vector search"""
        if not categories:
            return None
            
        # Convert to list if string
        if isinstance(categories, str):
            categories = [categories]
        
        # Ensure it's a list
        if not isinstance(categories, list):
            return None
        
        # Filter out empty/None values and normalize
        normalized = []
        for cat in categories:
            if cat and str(cat).strip():
                # Normalize category name
                normalized_cat = str(cat).strip().lower()
                normalized.append(normalized_cat)
        
        if not normalized:
            return None
            
        return normalized
    
    async def _elasticsearch_vector_search_solutions(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Perform vector search for solutions using semantic similarity"""
        try:
            if not self.vector_service:
                return []
            
            # Use semantic query from requirements
            semantic_query = requirements.get('semantic_query', '')
            if not semantic_query:
                semantic_query = requirements.get('use_case', 'business solution')
            
            print(f"🧠 Vector search for solutions: {semantic_query}")
            
            # Perform vector search for solutions using the correct method name and parameter
            results = await self.vector_service.vector_search_solutions(semantic_query, size=settings.final_result_limit)
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search for solutions failed: {e}")
            return []
    
    def _merge_product_results_simple(
        self, 
        elasticsearch_products: List[Dict], 
        vector_products: List[Dict]
    ) -> List[Dict]:
        """Simple merge of product results without RRF"""
        
        # Create a map of product ID to product
        all_products = {}
        
        # Add Elasticsearch products
        for product in elasticsearch_products:
            product_id = product.get('id', '')
            if product_id:
                all_products[product_id] = product.copy()
                all_products[product_id]['search_source'] = 'elasticsearch'
                all_products[product_id]['keyword_score'] = product.get('_score', 0)
                all_products[product_id]['semantic_score'] = 0
        
        # Add vector products (overwrite if exists)
        for product in vector_products:
            product_id = product.get('id', '')
            if product_id:
                if product_id in all_products:
                    # Product found in both sources
                    all_products[product_id]['search_source'] = 'both'
                    all_products[product_id]['semantic_score'] = product.get('_similarity_score', 0)
                else:
                    # Product only in vector search
                    all_products[product_id] = product.copy()
                    all_products[product_id]['search_source'] = 'vector'
                    all_products[product_id]['keyword_score'] = 0
                    all_products[product_id]['semantic_score'] = product.get('_similarity_score', 0)
        
        # Sort by combined score (keyword + semantic)
        merged_products = list(all_products.values())
        merged_products.sort(key=lambda x: x.get('keyword_score', 0) + x.get('semantic_score', 0), reverse=True)
        
        return merged_products[:settings.final_result_limit]

    async def _get_category_recommendations(
        self, 
        requirements: Dict[str, Any]
    ) -> tuple[List[str], float]:
        """Get category recommendations using Elasticsearch vector service's LLM analysis"""
        
        try:
            if self.vector_service and hasattr(self.vector_service, '_extract_categories_with_llm'):
                logger.info("🎯 Getting category recommendations from vector service...")
                categories = await self.vector_service._extract_categories_with_llm(requirements)
                
                # Calculate confidence based on number of categories and context richness
                confidence = 0.8 if len(categories) >= 2 else 0.6
                if len(categories) >= 4:
                    confidence = 0.9
                
                return categories, confidence
            else:
                logger.warning("Vector service category analysis not available")
                return [], 0.0
                
        except Exception as e:
            logger.error(f"Category recommendation failed: {e}")
            return [], 0.0

# Async helper to avoid import issues
async def run_async(coro):
    """Helper to run async code"""
    return await coro 