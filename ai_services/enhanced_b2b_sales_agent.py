import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import os
import uuid

from .base import AIProvider, AIMessage, AIResponse
from .quote_generation_agent import QuoteGenerationAgent
from .product_retriever_agent import ProductRetrieverAgent
from .conversation_flow_manager import ConversationFlowAgent
from .hybrid_product_retriever_agent import HybridProductRetrieverAgent
from .conversation_flow_manager import ConversationFlowAgent
from config import settings
from .quick_response_generator import QuickResponseGenerator

class EnhancedB2BSalesAgent(AIProvider):
    """Enhanced B2B Sales Agent with hybrid retrieval capabilities"""
    
    def __init__(
        self, 
        base_provider: AIProvider,
        use_hybrid_retriever: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.conversation_analyzer = ConversationFlowAgent(base_provider)
        self.quote_agent = QuoteGenerationAgent(base_provider)
        self.quick_response_generator = QuickResponseGenerator(base_provider)
        
        # Track asked questions to prevent duplicates
        self.asked_questions = set()
        
        # Cache for product recommendations
        self.product_cache = {
            'products': [],
            'solutions': [],
            'requirements': {},
            'last_retrieval_time': None,
            'retrieval_stage': None,
            'cache_valid': False
        }
        
        # Quick start templates for lazy users
        self.quick_start_templates = {
            "basic": "I need a quote for {product_type}",
            "detailed": "I need a quote for {product_type} with {features}",
            "budget": "I have a budget of {budget} for {product_type}",
            "comparison": "Compare {product1} vs {product2}",
            "specific": "I want to buy {product_name}",
            "help": "Help me choose the right product"
        }
        
        # Lazy user detection
        self.lazy_user_indicators = {
            "short_messages": 0,
            "template_usage": 0,
            "help_requests": 0
        }
        
        # Choose retriever based on configuration
        if use_hybrid_retriever and settings.azure_embedding_endpoint and settings.azure_embedding_api_key:
            print("🔧 Using Hybrid Product Retriever (Elasticsearch + ChromaDB)")
            self.retriever_agent = HybridProductRetrieverAgent(
                base_provider=base_provider,
                azure_embedding_endpoint=settings.azure_embedding_endpoint,
                azure_embedding_key=settings.azure_embedding_api_key
            )
        else:
            print("🔧 Using Standard Product Retriever (Elasticsearch only)")
            self.retriever_agent = ProductRetrieverAgent(base_provider)
        
        self.product_recommendations = {}
        
        # Conversation context for multi-agent collaboration
        self.conversation_context = []
        self.customer_requirements = {}
        
    @property
    def provider_name(self) -> str:
        return f"enhanced_b2b_sales_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def initialize(self):
        """Initialize the sales agent and its components"""
        try:
            # Initialize retriever agent if it's hybrid
            if hasattr(self.retriever_agent, 'initialize'):
                await self.retriever_agent.initialize()
            print("✅ Enhanced B2B Sales Agent initialized successfully")
        except Exception as e:
            print(f"⚠️ Enhanced B2B Sales Agent initialization warning: {e}")
            # Continue with standard retriever as fallback
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate sales-focused responses with intelligent conversation flow management"""
        
        # Store conversation for agent collaboration
        self.conversation_context = messages
        
        # Check for lazy user patterns
        self._detect_lazy_user_patterns(messages)
        
        # Update asked questions from recent messages
        self._update_asked_questions(messages)
        
        # Check for explicit quote request
        last_message = messages[-1].content.lower() if messages else ""
        is_explicit_quote_request = any(phrase in last_message for phrase in [
            "prepare a detailed quote", "could you please prepare", "generate a quote",
            "send me a quote", "i need a quote", "quote me", "quotation please",
            "detailed proposal", "pricing proposal", "can you quote"
        ])
        
        # If lazy user detected, provide more guided assistance
        if self._is_lazy_user():
            return await self._handle_lazy_user_interaction(messages, customer_context)
        
        print("🤝 Enhanced Sales Agent: Starting intelligent conversation flow analysis...")
        
        # Step 1: Use AI-powered flow analysis
        flow_analysis = await self.conversation_analyzer.analyze_conversation_state(messages, customer_context)
        
        # Force quote generation if explicitly requested
        if is_explicit_quote_request:
            flow_analysis['quote_ready'] = True
            flow_analysis['should_generate_quote'] = True
            flow_analysis['recommendation_selected'] = True
            flow_analysis['current_stage'] = 'quote_ready'
        
        # Generate quick responses based on current context
        quick_responses = await self.quick_response_generator.generate_quick_responses(
            messages=messages,
            customer_context=customer_context,
            num_responses=3
        )
        
        print(f"🧠 AI Flow Analysis:")
        print(f"   📊 Business Context: {flow_analysis.get('business_context_score', 0)}%")
        print(f"   📊 Technical Requirements: {flow_analysis.get('technical_requirements_score', 0)}%")
        print(f"   📊 Decision Readiness: {flow_analysis.get('decision_readiness_score', 0)}%")
        print(f"   📈 Current Stage: {flow_analysis.get('current_stage', 'unknown')}")
        print(f"   Quote Ready: {flow_analysis.get('quote_ready', False)}")
        print(f"   🤖 AI Reasoning: {flow_analysis.get('reasoning', 'N/A')}")
        
        # Step 2: Enhanced quote readiness check
        enhanced_quote_ready = self._enhanced_quote_readiness_check(messages, flow_analysis)
        
        # Debug logging for flow control
        print(f"🔍 Flow Control Debug:")
        print(f"   is_explicit_quote_request: {is_explicit_quote_request}")
        print(f"   enhanced_quote_ready: {enhanced_quote_ready}")
        print(f"   flow_analysis['should_generate_quote']: {flow_analysis.get('should_generate_quote', False)}")
        print(f"   flow_analysis['quote_ready']: {flow_analysis.get('quote_ready', False)}")
        print(f"   flow_analysis['recommendation_selected']: {flow_analysis.get('recommendation_selected', False)}")
        
        # Step 3: Get AI-powered action suggestions
        action_guidance = await self.conversation_analyzer.suggest_next_actions(flow_analysis, messages)
        
        print(f"💡 AI Action Guidance: {action_guidance.get('primary_action', 'continue')}")
        
        # Step 4: Execute based on AI recommendations and conversation stage
        current_stage = flow_analysis.get('current_stage', 'initial_discovery')
        
        # Check if we have an explicit quote request or enhanced readiness (from the enhanced quote check)
        explicit_or_enhanced_ready = (
            is_explicit_quote_request or 
            enhanced_quote_ready or 
            flow_analysis.get('should_generate_quote', False)
        )
        
        # Priority 1: Handle explicit quote requests or enhanced readiness (regardless of stage)
        if explicit_or_enhanced_ready:
            print(f"🎯 Routing to quote generation due to explicit request ({is_explicit_quote_request}) or enhanced readiness ({enhanced_quote_ready})")
            response = await self._handle_quote_ready_conversation(messages, customer_context, flow_analysis)
        # Priority 2: Handle recommendation stage when in solution presentation but not quote ready
        elif current_stage == 'solution_presentation' and not flow_analysis.get('recommendations_presented', False):
            print("🎯 Routing to recommendation stage")
            response = await self._handle_recommendation_stage(messages, customer_context, flow_analysis)
        # Priority 3: Handle discovery or other stages
        else:
            print(f"🎯 Routing to discovery stage: {current_stage}")
            response = await self._handle_discovery_conversation(messages, customer_context, flow_analysis)
        
        # Step 5: Add intelligent flow analysis to metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'ai_flow_analysis': flow_analysis,
            'action_guidance': action_guidance,
            'intelligent_flow_managed': True,
            'enhanced_quote_check': enhanced_quote_ready,
            'current_stage': current_stage,
            'quick_responses': quick_responses,
            'quick_response_templates': [
                {
                    'text': resp['text'],
                    'template': resp.get('template'),
                    'intent': resp['intent'],
                    'confidence': resp['confidence']
                }
                for resp in quick_responses
            ] if quick_responses else []
        })
        
        return response
    
    async def _handle_premature_pricing_request(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Handle when customer asks for pricing too early"""
        
        print("⚠️ Handling premature pricing request - redirecting to discovery")
        
        # Build context for redirecting conversation
        missing_info = flow_analysis.get('missing_info', [])
        next_questions = flow_analysis.get('next_questions', [])
        
        redirect_prompt = f"""The customer is asking for pricing, but we need more information first to provide an accurate quote. 

MISSING INFORMATION: {', '.join(missing_info)}
SUGGESTED NEXT QUESTIONS: {next_questions}

Politely acknowledge their pricing interest, explain that you want to provide the most accurate quote possible, and ask 1-2 discovery questions to gather the missing information. Be consultative and helpful, not pushy.

Example approach: "I'd be happy to prepare a detailed quote for you! To ensure I recommend the right solution at the best value, let me ask a couple quick questions about..."
"""
        
        enhanced_messages = self._add_discovery_context(messages, customer_context, redirect_prompt)
        response = await self.base_provider.generate_response(enhanced_messages)
        
        return response
    
    async def _handle_quote_ready_conversation(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Handle conversation when ready for quote generation"""
        
        print("✅ Conversation ready for quote generation")
        
        # Check if we have recommendations available
        if not self.product_recommendations or not self.product_recommendations.get('products'):
            print("⚠️ No recommendations available - retrieving products for quote")
            # Get product recommendations for quote generation
            retrieval_result = await self._collaborate_with_retriever_agent(
                messages=messages,
                customer_context=customer_context,
                force_retrieval=True
            )
            self.product_recommendations = retrieval_result
        
        # If we still don't have products after retrieval, fall back to recommendation stage
        if not self.product_recommendations.get('products'):
            print("❌ No products available after retrieval - falling back to recommendation stage")
            return await self._handle_recommendation_stage(messages, customer_context, flow_analysis)
        
        # For explicit quote requests, automatically select the best recommendation if none is explicitly selected
        if not flow_analysis.get('recommendation_selected', False):
            print("🎯 Auto-selecting top recommendation for quote generation")
            # Select the top product for quote generation
            top_product = self.product_recommendations.get('products', [])[0] if self.product_recommendations.get('products') else None
            if top_product:
                flow_analysis['recommendation_selected'] = True
                if customer_context is None:
                    customer_context = {}
                customer_context['selected_recommendation'] = top_product
                print(f"✅ Auto-selected: {top_product.get('name', 'Unknown Product')}")
            else:
                print("❌ No products available for auto-selection")
                return await self._handle_recommendation_stage(messages, customer_context, flow_analysis)
        
        # Generate sales response
        enhanced_messages = self._add_enhanced_sales_context(messages, customer_context, self.product_recommendations)
        response = await self.base_provider.generate_response(enhanced_messages)
        
        # Generate quote
        response = await self._collaborate_with_quote_agent(response, customer_context, flow_analysis)
        
        # Add retrieval metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'product_recommendations': self.product_recommendations.get('products', []),
            'solution_recommendations': self.product_recommendations.get('solutions', []),
            'retrieval_confidence': self.product_recommendations.get('retrieval_confidence', 0),
            'customer_requirements': self.product_recommendations.get('requirements', {})
        })
        
        return response
    
    async def _handle_discovery_conversation(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Handle discovery and information gathering conversations"""
        
        print(f"🔍 Handling discovery conversation - stage: {flow_analysis['current_stage']}")
        
        # Only retrieve products if we're in deep discovery or solution presentation
        if flow_analysis['current_stage'] in ['deep_discovery', 'solution_presentation']:
            retrieval_result = await self._collaborate_with_retriever_agent(
                messages=messages,
                customer_context=customer_context
            )
        else:
            retrieval_result = {}
        
        # Build discovery-focused context
        discovery_context = self._build_discovery_context(flow_analysis, retrieval_result)
        enhanced_messages = self._add_discovery_context(messages, customer_context, discovery_context)
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        # Add discovery guidance to metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'discovery_guidance': {
                'next_questions': flow_analysis.get('next_questions', []),
                'missing_info': flow_analysis.get('missing_info', []),
                'current_stage': flow_analysis['current_stage']
            }
        })
        
        return response
    
    def _build_discovery_context(self, flow_analysis: Dict[str, Any], retrieval_result: Dict[str, Any]) -> str:
        """Build context for discovery conversations"""
        
        current_stage = flow_analysis['current_stage']
        missing_info = flow_analysis.get('missing_info', [])
        next_questions = flow_analysis.get('next_questions', [])
        completion_scores = flow_analysis.get('completion_scores', {})
        
        # Filter out already asked questions
        next_questions = [q for q in next_questions if q not in self.asked_questions]
        
        # Add quick options for lazy users
        quick_options = """
QUICK OPTIONS:
1. "Tell me about your products"
2. "What's your best seller?"
3. "Show me pricing"
4. "Compare options"
5. "Help me choose"
"""
        
        context = f"""
CONVERSATION GUIDANCE FOR DISCOVERY STAGE: {current_stage.upper()}

CURRENT INFORMATION GATHERING STATUS:
• Business Context: {completion_scores.get('business_context', 0):.1%} complete
• Technical Requirements: {completion_scores.get('technical_requirements', 0):.1%} complete  
• Operational Requirements: {completion_scores.get('operational_requirements', 0):.1%} complete
• Pain Points: {completion_scores.get('pain_points', 0):.1%} complete

STILL NEEDED: {', '.join(missing_info) if missing_info else 'Information gathering on track'}

SUGGESTED NEXT QUESTIONS TO ASK:
{chr(10).join(f'• {q}' for q in next_questions) if next_questions else '• Continue natural conversation flow'}

{quick_options if self._is_lazy_user() else ''}

DISCOVERY PRIORITIES FOR THIS STAGE:
"""
        
        if current_stage == "initial_discovery":
            context += """
• Focus on understanding their business and current challenges
• Ask about their industry, company size, and primary use cases
• Identify pain points with current solutions
• Keep technical questions high-level for now
"""
        elif current_stage == "deep_discovery":
            context += """
• Dive deeper into technical requirements and specifications
• Understand their workflow and performance needs
• Explore scalability and future growth requirements
• Discuss timeline and budget considerations
"""
        elif current_stage == "solution_presentation":
            context += """
• Present relevant solutions based on gathered requirements
• Highlight how solutions address their specific pain points
• Discuss implementation approach and timeline
• Prepare for transitioning to quote discussion
"""
        
        context += """

IMPORTANT: 
1. Do NOT offer quotes or detailed pricing until you have sufficient information
2. Do NOT suggest scheduling a meeting
3. Focus on being consultative and asking insightful questions that demonstrate expertise
4. If they ask for pricing early, politely redirect to gather more information first
5. Avoid asking questions that have already been answered
"""
        
        return context
    
    def _add_discovery_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        additional_context: str
    ) -> List[AIMessage]:
        """Add discovery-focused context to messages"""
        
        system_prompt = self._build_discovery_system_prompt()
        
        enhanced_messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="system", content=additional_context),
        ]
        
        # Add customer context if available
        if customer_context:
            customer_info = self._build_customer_context(customer_context)
            enhanced_messages.append(AIMessage(role="system", content=customer_info))
        
        # Add conversation history
        enhanced_messages.extend(messages)
        
        return enhanced_messages
    
    def _build_discovery_system_prompt(self) -> str:
        """Build system prompt focused on discovery and information gathering"""
        
        return """You are an expert B2B technology sales consultant with deep expertise in enterprise solutions. Your primary role is to understand your prospects' business needs through consultative selling.

KEY RESPONSIBILITIES:
1. 🔍 DISCOVER business challenges and technical requirements through thoughtful questioning
2. 🎯 QUALIFY prospects by understanding their decision-making process, timeline, and budget
3. 🤝 BUILD TRUST by demonstrating expertise and genuinely caring about their success
4. 💡 EDUCATE about solutions only after understanding their specific needs
5. 📊 GATHER sufficient information before discussing pricing or quotes

DISCOVERY METHODOLOGY:
• Ask open-ended questions that uncover business impact
• Listen actively and ask follow-up questions
• Understand their current state vs. desired future state
• Identify all stakeholders involved in the decision
• Explore their evaluation criteria and success metrics

CONSULTATIVE SELLING PRINCIPLES:
• Be genuinely curious about their business
• Share relevant insights and best practices
• Position yourself as a trusted advisor, not just a vendor
• Focus on business outcomes, not just technical features
• Create value in every interaction

CONVERSATION FLOW RULES:
• Always gather sufficient context before proposing solutions
• Ask about business impact and consequences of current challenges
• Understand their evaluation process and timeline
• Never rush to pricing - focus on fit and value first
• When they ask for pricing early, redirect professionally to gather more context

COMMUNICATION STYLE:
• Professional yet conversational
• Consultative and advisory
• Ask insightful questions that demonstrate expertise
• Show genuine interest in their success
• Be patient with the discovery process

Remember: Your goal is to thoroughly understand their needs so you can recommend the perfect solution. Quality discovery leads to better solutions and higher close rates."""

    async def _should_retrieve_products(self, flow_analysis: Dict[str, Any]) -> bool:
        """Determine if products should be retrieved based on conversation stage and cache status"""
        
        current_stage = flow_analysis.get('current_stage', 'initial_discovery')
        
        # Never retrieve in initial discovery
        if current_stage == 'initial_discovery':
            return False
            
        # Only retrieve in solution presentation if we don't have cached products
        if current_stage == 'solution_presentation':
            return not self.product_cache['cache_valid'] or not self.product_cache['products']
            
        # For deep discovery, only retrieve if we don't have cached products
        if current_stage == 'deep_discovery':
            return not self.product_cache['cache_valid'] or not self.product_cache['products']
                
        # For quote_ready stage, only retrieve if we don't have cached products
        if current_stage == 'quote_ready':
            return not self.product_cache['cache_valid'] or not self.product_cache['products']
        
        # Default to not retrieving
        return False

    async def _collaborate_with_retriever_agent(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        force_retrieval: bool = False
    ) -> Dict[str, Any]:
        """Collaborate with hybrid product retriever agent with caching"""
        
        try:
            # Get flow analysis to determine if we should retrieve
            flow_analysis = await self.conversation_analyzer.analyze_conversation_state(messages, customer_context)
            
            # Check if we should retrieve products
            if not force_retrieval and not await self._should_retrieve_products(flow_analysis):
                print("🔄 Using cached product recommendations")
                return {
                    'products': self.product_cache['products'],
                    'solutions': self.product_cache['solutions'],
                    'requirements': self.product_cache['requirements'],
                    'search_methods': self.product_cache.get('search_methods', {}),
                    'retrieval_success': True,
                    'retrieval_method': 'cache',
                    'retrieval_confidence': self.product_cache.get('retrieval_confidence', 0.5)
                }
            
            print(f"🤝 Enhanced Sales Agent: Collaborating with {'Hybrid' if isinstance(self.retriever_agent, HybridProductRetrieverAgent) else 'Standard'} Product Retriever...")
            
            # Get product recommendations
            retrieval_result = await self.retriever_agent.retrieve_products(messages, customer_context)
            
            # Ensure we have a proper dictionary structure
            if not isinstance(retrieval_result, dict):
                print(f"⚠️ Retriever returned unexpected type: {type(retrieval_result)}")
                retrieval_result = {
                    'products': retrieval_result if isinstance(retrieval_result, list) else [],
                    'solutions': [],
                    'requirements': {},
                    'total_products': len(retrieval_result) if isinstance(retrieval_result, list) else 0,
                    'total_solutions': 0,
                    'success': False,
                    'error': 'Unexpected return type from retriever'
                }
            
            # Extract results safely
            products = retrieval_result.get('products', [])
            solutions = retrieval_result.get('solutions', [])
            requirements = retrieval_result.get('requirements', {})
            search_methods = retrieval_result.get('search_methods', {})
            
            # Normalize product and solution data to ensure all required fields exist
            products = self._normalize_product_data(products)
            solutions = self._normalize_solution_data(solutions)
            
            print(f"📦 Enhanced Sales Agent: Retrieved {len(products)} products, {len(solutions)} solutions")
            
            if search_methods:
                print(f"🔍 Search method breakdown: {search_methods}")
            
            # Update cache only if we got valid results
            if products or solutions:
                self.product_cache = {
                    'products': products,
                    'solutions': solutions,
                    'requirements': requirements,
                    'search_methods': search_methods,
                    'retrieval_confidence': retrieval_result.get('retrieval_confidence', 0.5),
                    'last_retrieval_time': datetime.now(),
                    'retrieval_stage': flow_analysis.get('current_stage'),
                    'cache_valid': True
                }
            
            return {
                'products': products,
                'solutions': solutions,
                'requirements': requirements,
                'search_methods': search_methods,
                'retrieval_success': retrieval_result.get('success', False),
                'retrieval_method': retrieval_result.get('retrieval_method', 'unknown'),
                'retrieval_confidence': retrieval_result.get('retrieval_confidence', 0.5)
            }
            
        except Exception as e:
            print(f"⚠️ Retriever collaboration failed: {str(e)}")
            import traceback
            print(traceback.format_exc())
            
            # Return cached results if available
            if self.product_cache['products']:
                print("🔄 Falling back to cached product recommendations")
                return {
                    'products': self.product_cache['products'],
                    'solutions': self.product_cache['solutions'],
                    'requirements': self.product_cache['requirements'],
                    'search_methods': self.product_cache.get('search_methods', {}),
                    'retrieval_success': True,
                    'retrieval_method': 'cache_fallback',
                    'retrieval_confidence': self.product_cache.get('retrieval_confidence', 0.5)
                }
            
            # Return safe fallback structure
            return {
                'products': [],
                'solutions': [],
                'requirements': {},
                'search_methods': {},
                'retrieval_success': False,
                'error': str(e),
                'retrieval_confidence': 0.0
            }
    
    async def _collaborate_with_quote_agent(
        self, 
        response: AIResponse, 
        customer_context: Optional[Dict],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Enhanced collaboration with quote agent using flow analysis"""
        
        # Ensure response has metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        print(f"🎯 Sales Agent: Collaborating with Quote Agent...")
        print(f"🔍 Quote ready status: {flow_analysis.get('quote_ready', False)}")
        print(f"🔍 Should generate quote: {flow_analysis.get('should_generate_quote', False)}")
        
        # Enhanced conversation context with retriever findings and flow analysis
        enhanced_conversation = self._enhance_conversation_for_quote_generation(flow_analysis)
        
        # Prepare enhanced customer context with all necessary information
        enhanced_customer_context = {
            **(customer_context or {}),
            'product_recommendations': self.product_recommendations.get('products', []),
            'solution_recommendations': self.product_recommendations.get('solutions', []),
            'extracted_requirements': self.product_recommendations.get('requirements', {}),
            'conversation_analysis': flow_analysis,
            'flow_confidence': flow_analysis.get('confidence_level', 'medium'),
            'business_context_score': flow_analysis.get('business_context_score', 50),
            'technical_requirements_score': flow_analysis.get('technical_requirements_score', 50),
            'completion_scores': flow_analysis.get('completion_scores', {}),
            'quote_ready': flow_analysis.get('quote_ready', False),
            'should_generate_quote': flow_analysis.get('should_generate_quote', False),
            'current_stage': flow_analysis.get('current_stage', 'deep_discovery'),
            'recommendation_selected': flow_analysis.get('recommendation_selected', False)
        }
        
        # Debug logging for customer context
        print(f"🔍 Customer Context Debug:")
        print(f"   Original customer_context has selected_recommendation: {'selected_recommendation' in (customer_context or {})}")
        print(f"   Enhanced context has selected_recommendation: {'selected_recommendation' in enhanced_customer_context}")
        if 'selected_recommendation' in enhanced_customer_context:
            selected = enhanced_customer_context['selected_recommendation']
            print(f"   Selected recommendation: {selected.get('name', 'Unknown')} (ID: {selected.get('id', 'Unknown')})")
        
        # Ensure selected_recommendation is available if auto-selected
        if flow_analysis.get('recommendation_selected', False) and 'selected_recommendation' not in enhanced_customer_context:
            # Auto-select the first product if none was explicitly selected
            top_product = self.product_recommendations.get('products', [])[0] if self.product_recommendations.get('products') else None
            if top_product:
                enhanced_customer_context['selected_recommendation'] = top_product
                print(f"🎯 Quote Agent: Auto-selecting recommendation for quote: {top_product.get('name', 'Unknown Product')}")
            else:
                print("❌ Quote Agent: No products available for auto-selection")
        
        print(f"📝 Enhanced context prepared with {len(enhanced_conversation)} messages")
        
        # Debug logging for quote generation
        extracted_requirements = enhanced_customer_context.get('extracted_requirements', {})
        print(f"🔍 Quote Generation Debug:")
        print(f"   Product recommendations: {len(enhanced_customer_context.get('product_recommendations', []))}")
        print(f"   Extracted requirements keys: {list(extracted_requirements.keys()) if extracted_requirements else 'None'}")
        print(f"   Technical requirements: {len(extracted_requirements.get('technical_requirements', [])) if extracted_requirements else 0}")
        print(f"   Business requirements: {len(extracted_requirements.get('business_requirements', [])) if extracted_requirements else 0}")
        
        # Let quote agent generate quote with enhanced context
        try:
            # First verify we have the necessary data
            if not enhanced_customer_context.get('product_recommendations'):
                raise ValueError("No product recommendations available for quote generation")
            
            if not enhanced_customer_context.get('extracted_requirements'):
                raise ValueError("No customer requirements available for quote generation")
            
            # Generate quote with enhanced context
            quote = await self.quote_agent.generate_quote_from_conversation(
                enhanced_conversation,
                enhanced_customer_context
            )
            
            if quote:
                print(f"✅ Quote Agent provided enhanced quote with ID: {quote.get('id')}")
                print(f"📄 PDF URL: {quote.get('pdf_url', 'Not generated')}")
                
                # Generate pitch deck
                from services.pitch_deck_service import PitchDeckService
                pitch_deck_service = PitchDeckService()
                
                try:
                    # Extract pitch deck structure from quote
                    deck_structure = await pitch_deck_service.extract_ppt_structure(str(quote))
                    
                    # Generate unique deck ID
                    deck_id = str(uuid.uuid4())
                    
                    # Generate the pitch deck
                    deck_path = f"Data/pitch_decks/pitch_deck_{deck_id}.pptx"
                    os.makedirs(os.path.dirname(deck_path), exist_ok=True)
                    
                    # Generate the PowerPoint file
                    await pitch_deck_service.generate_ppt(deck_structure, deck_path)
                    
                    # Add quote and pitch deck to response metadata
                    response.metadata['quote'] = quote
                    response.metadata['quote_generated'] = True
                    response.metadata['quote_id'] = quote.get('id')
                    response.metadata['pitch_deck'] = {
                        'id': deck_id,
                        'path': deck_path,
                        'download_url': f"/api/quotes/download-pitch-deck/{deck_id}"
                    }
                    
                    # Enhance sales response to incorporate the quote and pitch deck
                    response = self._enhance_response_with_dynamic_quote(response, quote, deck_id)
                except Exception as deck_error:
                    print(f"⚠️ Pitch deck generation failed: {str(deck_error)}")
                    # Continue without pitch deck
                    response.metadata['pitch_deck_error'] = str(deck_error)
            else:
                print("❌ Quote agent couldn't generate quote from enhanced conversation")
                response.metadata['quote_generation_failed'] = True
                
                # Add fallback message
                response.content += "\n\n💡 I'd be happy to prepare a detailed quote for you! Let me gather a bit more information to ensure I provide the most accurate recommendations."
                
        except ValueError as ve:
            print(f"❌ Validation error in quote generation: {str(ve)}")
            response.metadata['quote_error'] = str(ve)
            response.content += f"\n\n💡 I need a bit more information to prepare your quote. {str(ve)}"
            
        except Exception as e:
            print(f"❌ Error in quote generation: {str(e)}")
            response.metadata['quote_error'] = str(e)
            
            # Add error handling message
            response.content += "\n\n💡 I'm ready to prepare a quote for you! Let me just verify a few details to ensure accuracy."
        
        return response
    
    def _enhance_conversation_for_quote_generation(self, flow_analysis: Dict[str, Any]) -> List[AIMessage]:
        """Enhance conversation context with flow analysis for better quote generation"""
        
        enhanced_messages = list(self.conversation_context)
        
        # Add system message with comprehensive context
        context_summary = f"""
CONVERSATION FLOW ANALYSIS FOR QUOTE GENERATION:

READINESS ASSESSMENT:
• Current Stage: {flow_analysis['current_stage']}
• Quote Ready: {flow_analysis['quote_ready']}
• Conversation Quality: {flow_analysis.get('conversation_quality', {})}

INFORMATION COMPLETENESS:
• Business Context: {flow_analysis['completion_scores'].get('business_context', 0):.1%}
• Technical Requirements: {flow_analysis['completion_scores'].get('technical_requirements', 0):.1%}  
• Operational Requirements: {flow_analysis['completion_scores'].get('operational_requirements', 0):.1%}
• Pain Points Understanding: {flow_analysis['completion_scores'].get('pain_points', 0):.1%}

DYNAMIC PRODUCT RECOMMENDATIONS:
{json.dumps(self.product_recommendations.get('products', [])[:3], indent=2)}

SOLUTION RECOMMENDATIONS:
{json.dumps(self.product_recommendations.get('solutions', []), indent=2)}

Use this comprehensive analysis to generate a well-informed, accurate quote that addresses the customer's specific needs and requirements identified through proper discovery.
"""
        
        enhanced_messages.insert(-1, AIMessage(
            role="system", 
            content=context_summary
        ))
        
        return enhanced_messages
    
    def _add_enhanced_sales_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict],
        retrieval_result: Dict[str, Any]
    ) -> List[AIMessage]:
        """Add enhanced sales context for quote-ready conversations"""
        
        system_prompt = """You are an expert B2B technology sales consultant ready to present solutions and discuss pricing. The prospect has provided sufficient information about their needs, and you're now transitioning to solution presentation and quote discussion.

CURRENT FOCUS:
• Present tailored solutions based on gathered requirements
• Highlight specific business benefits and ROI
• Address any remaining concerns or questions
• Facilitate transition to formal quote discussion
• Create urgency and motivation to move forward

APPROACH:
• Summarize your understanding of their needs
• Present recommended solutions with clear business justification
• Discuss implementation approach and timeline
• Address pricing and next steps professionally
• Maintain consultative approach while moving toward close"""
        
        dynamic_product_info = self._build_dynamic_product_context(retrieval_result)
        
        enhanced_messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="system", content=dynamic_product_info),
        ]
        
        # Add customer context if available
        if customer_context:
            customer_info = self._build_customer_context(customer_context)
            enhanced_messages.append(AIMessage(role="system", content=customer_info))
        
        # Add conversation history
        enhanced_messages.extend(messages)
        
        return enhanced_messages
    
    def _build_dynamic_product_context(self, retrieval_result: Dict[str, Any]) -> str:
        """Build enhanced product context including hybrid search info"""
        
        context = "🛍️ HYBRID PRODUCT INTELLIGENCE:\n\n"
        
        products = retrieval_result.get('products', [])
        solutions = retrieval_result.get('solutions', [])
        requirements = retrieval_result.get('requirements', {})
        search_methods = retrieval_result.get('search_methods', {})
        
        if search_methods:
            context += "=== HYBRID SEARCH RESULTS ===\n"
            context += f"🔍 Elasticsearch (keyword): {search_methods.get('elasticsearch_products', 0)} products\n"
            context += f"🧠 ChromaDB (semantic): {search_methods.get('chroma_products', 0)} products\n"
            context += f"💡 Solutions (semantic): {search_methods.get('chroma_solutions', 0)} solutions\n"
            context += f"🎯 Total merged: {search_methods.get('merged_products', 0)} products\n\n"
        
        if products:
            context += "=== TOP HYBRID RECOMMENDATIONS ===\n"
            for i, product in enumerate(products[:3], 1):
                context += f"{i}. {product.get('name', 'Unknown')}\n"
                context += f"   Description: {product.get('description', 'No description')}\n"
                
                if 'price' in product:
                    context += f"   Price: ${product['price']:,.2f}\n"
                
                # Show search source and scores
                search_source = product.get('search_source', 'unknown')
                context += f"   Found in: {search_source}\n"
                
                if product.get('keyword_score'):
                    context += f"   Keyword relevance: {product['keyword_score']:.2f}\n"
                
                if product.get('semantic_score'):
                    context += f"   Semantic similarity: {product['semantic_score']:.2f}\n"
                
                if product.get('hybrid_score'):
                    context += f"   🎯 Hybrid score: {product['hybrid_score']:.2f}\n"
                
                context += f"   Product ID: {product.get('id', 'N/A')}\n\n"
        
        # Add confidence and method info
        confidence = retrieval_result.get('retrieval_confidence', 0)
        retrieval_method = retrieval_result.get('retrieval_method', 'unknown')
        
        context += f"🎯 HYBRID SEARCH CONFIDENCE: {confidence:.1%}\n"
        context += f"🔧 RETRIEVAL METHOD: {retrieval_method}\n"
        
        if confidence < 0.5:
            context += "⚠️ Low confidence - Ask more discovery questions for better semantic matching\n"
        elif confidence > 0.8:
            context += "✅ High confidence - Excellent keyword + semantic match!\n"
        
        context += "\n💡 **Use these REAL products found through hybrid search (keyword + AI semantic) to provide specific recommendations!**"
        
        return context
    
    def _build_customer_context(self, customer_context: Dict[str, Any]) -> str:
        """Build customer context for personalized sales approach"""
        context = f"👤 CUSTOMER PROFILE:\n"
        
        if customer_context.get('company_name'):
            context += f"Company: {customer_context['company_name']}\n"
        if customer_context.get('industry'):
            context += f"Industry: {customer_context['industry']}\n"
        if customer_context.get('company_size'):
            context += f"Size: {customer_context['company_size']}\n"
        if customer_context.get('budget_range'):
            context += f"Budget Range: {customer_context['budget_range']}\n"
        if customer_context.get('timeline'):
            context += f"Timeline: {customer_context['timeline']}\n"
        if customer_context.get('pain_points'):
            context += f"Pain Points: {', '.join(customer_context['pain_points'])}\n"
        
        context += "\nUse this information to personalize your approach and recommendations."
        
        return context
    
    def _get_stage_guidance(self, stage: str) -> Dict[str, Any]:
        """Get guidance for the current conversation stage"""
        
        guidance = {
            "initial_discovery": {
                "focus": "Understand business context and high-level challenges",
                "objectives": ["Industry/company size", "Primary use cases", "Current pain points"],
                "avoid": ["Technical details", "Pricing discussions", "Product recommendations"]
            },
            "deep_discovery": {
                "focus": "Explore technical requirements and operational needs",
                "objectives": ["Technical specifications", "Performance requirements", "Timeline/budget"],
                "avoid": ["Premature solution presentation", "Detailed pricing"]
            },
            "solution_presentation": {
                "focus": "Present tailored solutions and build value",
                "objectives": ["Solution recommendations", "Business benefits", "ROI discussion"],
                "avoid": ["Generic presentations", "Feature dumping"]
            },
            "qualification_complete": {
                "focus": "Finalize requirements and prepare for quote",
                "objectives": ["Confirm all requirements", "Discuss next steps", "Quote preparation"],
                "avoid": ["Reopening discovery unnecessarily"]
            },
            "premature_pricing_request": {
                "focus": "Redirect to gather necessary information",
                "objectives": ["Explain need for more info", "Ask key discovery questions"],
                "avoid": ["Providing estimates without context", "Being pushy"]
            }
        }
        
        return guidance.get(stage, {
            "focus": "Continue consultative conversation",
            "objectives": ["Understand customer needs"],
            "avoid": ["Rushing the process"]
        })
    
    def _enhance_response_with_dynamic_quote(self, response: AIResponse, quote: Dict[str, Any], deck_id: str) -> AIResponse:
        """Enhanced response with dynamic quote and pitch deck information"""
        
        if 'pdf_url' in quote:
            # Add professional quote presentation with dynamic context
            response.content += f"\n\n🎯 **Excellent! Based on our thorough discussion and your specific requirements, I've prepared a comprehensive, customized quote using our intelligent product matching system.**"
            response.content += f"\n\n📋 **Quote #{quote.get('quote_number', 'N/A')}**"
            
            # Highlight the thorough discovery process
            response.content += f"\n\n✅ **Complete Requirements Analysis:** Our conversation covered all the essential areas needed for an accurate quote - your business context, technical requirements, operational needs, and specific challenges."
            
            # Highlight the intelligent matching
            if self.product_recommendations.get('retrieval_confidence', 0) > 0.7:
                response.content += f"\n\n🤖 **AI-Powered Recommendations:** Our system identified a {self.product_recommendations.get('retrieval_confidence', 0):.1%} match with your requirements based on our comprehensive product intelligence!"
            
            # Add pricing summary
            if 'pricing' in quote:
                pricing = quote['pricing']
                response.content += f"\n\n💰 **Investment Summary:**"
                response.content += f"\n• Subtotal: **${pricing['subtotal']:,.2f}**"
                response.content += f"\n• Tax: ${pricing['tax_amount']:,.2f}"
                response.content += f"\n• **Total Investment: ${pricing['total']:,.2f}**"
                response.content += f"\n• Quote valid until: {datetime.fromisoformat(quote['valid_until']).strftime('%B %d, %Y')}"
            
            # Add PDF download link
            response.content += f"\n\n📄 **[Download Complete Quote PDF]({quote['pdf_url']})**"
            
            # Add pitch deck download link
            response.content += f"\n\n📊 **[Download Pitch Deck](/api/quotes/download-pitch-deck/{deck_id})**"
            
            # Enhanced next steps
            response.content += f"\n\n**Next Steps:**"
            response.content += f"\n1. Review the detailed quote with all selected products and solutions"
            response.content += f"\n2. Check out the pitch deck for a visual overview of the solution"
            response.content += f"\n3. Let me know if you'd like to discuss any aspects in more detail"
            response.content += f"\n4. I can arrange product demos or technical consultations if helpful"
            response.content += f"\n5. We can finalize implementation timeline and support arrangements"
            
            response.content += f"\n\nThis quote and pitch deck reflect our thorough understanding of your business needs and technical requirements. I'm confident these recommendations will deliver the performance and value you're looking for! 🚀"
            
        return response
    
    def _enhanced_quote_readiness_check(self, messages: List[AIMessage], flow_analysis: Dict[str, Any]) -> bool:
        """Enhanced logic to detect when customer is truly ready for a quote"""
        
        if not messages:
            return False
        
        # Get the last few messages for analysis
        recent_messages = messages[-3:] if len(messages) > 3 else messages
        recent_text = " ".join([msg.content.lower() for msg in recent_messages if msg.content]).strip()
        
        print(f"🔍 Enhanced Quote Check - Recent text: {recent_text[:200]}...")
        
        # Strong quote request indicators
        strong_quote_indicators = [
            "prepare a detailed quote", "could you please prepare", "generate a quote",
            "send me a quote", "i need a quote", "quote me", "quotation please",
            "detailed proposal", "pricing proposal", "can you quote", "give me a quote",
            "receive the quote", "yes send detailed quote", "how much", "what's the price",
            "pricing information", "cost estimate", "budget estimate", "price quote",
            "send me pricing", "what would it cost", "total cost", "final price",
            "i'll prepare", "i will send", "send it over", "quote shortly",
            "formal quote", "detailed quote", "pricing quote"
        ]
        
        # Check for explicit quote requests
        explicit_quote_request = any(phrase in recent_text for phrase in strong_quote_indicators)
        
        # If there's an explicit quote request, proceed with quote generation
        if explicit_quote_request:
            print("✅ Explicit quote request detected - proceeding with quote generation")
            flow_analysis['quote_ready'] = True
            flow_analysis['should_generate_quote'] = True
            flow_analysis['recommendation_selected'] = True
            return True
            
        # Calculate readiness scores
        explicit_request_score = 100 if explicit_quote_request else 0
        business_context_score = flow_analysis.get('business_context_score', 0)
        technical_score = flow_analysis.get('technical_requirements_score', 0)
        
        # Overall readiness calculation with adjusted weights
        overall_readiness = (
            explicit_request_score * 0.5 +     # Explicit requests are weighted more heavily
            business_context_score * 0.25 +    # Business context is important
            technical_score * 0.25             # Technical requirements are important
        )
        
        print(f"🎯 Enhanced Readiness Scores:")
        print(f"   📝 Explicit Request: {explicit_request_score}%")
        print(f"   💼 Business Context: {business_context_score}%")
        print(f"   🔧 Technical Requirements: {technical_score}%")
        print(f"   📊 Overall Readiness: {overall_readiness:.1f}%")
        
        # Decision threshold - lowered from 70% to 50%
        if explicit_quote_request:
            is_ready = True  # Always ready for explicit requests
            print(f"✅ Explicit quote request detected - proceeding with quote")
        else:
            is_ready = overall_readiness >= 50  # Lower threshold for implicit readiness
            print(f"📋 Implicit readiness check - threshold: 50%")
        
        print(f"🎯 Final Decision: {'READY FOR QUOTE' if is_ready else 'CONTINUE DISCOVERY'}")
        
        # Update flow analysis
        flow_analysis['quote_ready'] = is_ready
        flow_analysis['should_generate_quote'] = is_ready
        flow_analysis['recommendation_selected'] = is_ready
        
        return is_ready

    async def generate_recommendations(self, request: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate product recommendations based on customer requirements"""
        try:
            print("🎯 Enhanced Sales Agent: Generating recommendations...")
            
            # Get product recommendations using hybrid retriever
            retrieval_result = await self._collaborate_with_retriever_agent(
                messages=[AIMessage(role="user", content=json.dumps(request))],
                customer_context=request.get('customer_context', {})
            )
            
            # Extract and format recommendations
            products = retrieval_result.get('products', [])
            solutions = retrieval_result.get('solutions', [])
            
            # Normalize products to ensure all required fields exist
            products = self._normalize_product_data(products)
            solutions = self._normalize_solution_data(solutions)
            
            # Combine and format recommendations
            recommendations = []
            
            # Add product recommendations
            for product in products:
                try:
                    # Safely handle price conversion
                    price = product.get('price')
                    if price is not None:
                        try:
                            price = float(price)
                        except (ValueError, TypeError):
                            price = 0.0
                    else:
                        price = 0.0

                    # Safely handle hybrid score
                    hybrid_score = product.get('hybrid_score')
                    if hybrid_score is not None:
                        try:
                            hybrid_score = float(hybrid_score)
                        except (ValueError, TypeError):
                            hybrid_score = 0.0
                    else:
                        hybrid_score = 0.0

                    # Safely handle features and benefits
                    features = product.get('features', [])
                    if not isinstance(features, list):
                        features = []
                    
                    benefits = product.get('benefits', [])
                    if not isinstance(benefits, list):
                        benefits = []

                    recommendation = {
                        'product_id': product.get('id', ''),
                        'name': product.get('name', ''),
                        'description': product.get('description', ''),
                        'price': price,
                        'features': features,
                        'benefits': benefits,
                        'suitability_score': hybrid_score,
                        'customization_options': product.get('customization_options', {}),
                        'search_source': product.get('search_source', 'hybrid'),
                        'confidence': hybrid_score
                    }
                    recommendations.append(recommendation)
                except Exception as e:
                    print(f"⚠️ Error processing product {product.get('id', 'unknown')}: {str(e)}")
                    continue
            
            # Add solution recommendations if available
            if solutions:
                for solution in solutions:
                    try:
                        # Safely handle price conversion
                        price = solution.get('price')
                        if price is not None:
                            try:
                                price = float(price)
                            except (ValueError, TypeError):
                                price = 0.0
                        else:
                            price = 0.0

                        # Safely handle match score
                        match_score = solution.get('match_score')
                        if match_score is not None:
                            try:
                                match_score = float(match_score)
                            except (ValueError, TypeError):
                                match_score = 0.0
                        else:
                            match_score = 0.0

                        # Safely handle features and benefits
                        features = solution.get('features', [])
                        if not isinstance(features, list):
                            features = []
                        
                        benefits = solution.get('benefits', [])
                        if not isinstance(benefits, list):
                            benefits = []

                        recommendation = {
                            'product_id': solution.get('id', ''),
                            'name': solution.get('name', ''),
                            'description': solution.get('description', ''),
                            'price': price,
                            'features': features,
                            'benefits': benefits,
                            'suitability_score': match_score,
                            'customization_options': solution.get('customization_options', {}),
                            'search_source': 'solution',
                            'confidence': match_score
                        }
                        recommendations.append(recommendation)
                    except Exception as e:
                        print(f"⚠️ Error processing solution {solution.get('id', 'unknown')}: {str(e)}")
                        continue
            
            print(f"✅ Generated {len(recommendations)} recommendations")
            return recommendations
            
        except Exception as e:
            print(f"❌ Recommendation generation failed: {str(e)}")
            return []

    def _normalize_product_data(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize product data to ensure all required fields exist"""
        normalized_products = []
        
        for product in products:
            try:
                # Create a copy to avoid modifying the original
                normalized_product = dict(product)
                
                # Ensure description field exists
                if 'description' not in normalized_product or not normalized_product['description']:
                    # Generate description from available fields
                    description_parts = []
                    
                    # Add product name
                    if normalized_product.get('name'):
                        description_parts.append(normalized_product['name'])
                    
                    # Add category if available
                    if normalized_product.get('category'):
                        description_parts.append(f"({normalized_product['category']})")
                    
                    # Add core specifications for hardware
                    if normalized_product.get('core_count'):
                        description_parts.append(f"{normalized_product['core_count']}-core")
                    
                    if normalized_product.get('core_clock'):
                        description_parts.append(f"{normalized_product['core_clock']}GHz")
                    
                    if normalized_product.get('tdp'):
                        description_parts.append(f"{normalized_product['tdp']}W TDP")
                    
                    # Create description or use fallback
                    if description_parts:
                        normalized_product['description'] = ' '.join(description_parts)
                    else:
                        normalized_product['description'] = f"Professional {normalized_product.get('name', 'technology product')}"
                
                # Ensure other required fields exist
                if 'features' not in normalized_product:
                    normalized_product['features'] = []
                
                if 'benefits' not in normalized_product:
                    normalized_product['benefits'] = []
                
                if 'id' not in normalized_product or not normalized_product['id']:
                    # Generate ID from name
                    normalized_product['id'] = f"product_{hash(normalized_product.get('name', 'unknown'))}"
                
                normalized_products.append(normalized_product)
                
            except Exception as e:
                print(f"⚠️ Error normalizing product {product.get('name', 'unknown')}: {str(e)}")
                # Add a minimal safe product
                normalized_products.append({
                    'id': f"product_{hash(str(product))}",
                    'name': product.get('name', 'Unknown Product'),
                    'description': f"Professional {product.get('name', 'technology product')}",
                    'price': product.get('price', 0),
                    'features': [],
                    'benefits': []
                })
        
        return normalized_products

    def _normalize_solution_data(self, solutions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize solution data to ensure all required fields exist"""
        normalized_solutions = []
        
        for solution in solutions:
            try:
                # Create a copy to avoid modifying the original
                normalized_solution = dict(solution)
                
                # Ensure description field exists
                if 'description' not in normalized_solution or not normalized_solution['description']:
                    normalized_solution['description'] = f"Complete {normalized_solution.get('name', 'technology solution')}"
                
                # Ensure other required fields exist
                if 'features' not in normalized_solution:
                    normalized_solution['features'] = []
                
                if 'benefits' not in normalized_solution:
                    normalized_solution['benefits'] = []
                
                if 'id' not in normalized_solution or not normalized_solution['id']:
                    normalized_solution['id'] = f"solution_{hash(normalized_solution.get('name', 'unknown'))}"
                
                normalized_solutions.append(normalized_solution)
                
            except Exception as e:
                print(f"⚠️ Error normalizing solution {solution.get('name', 'unknown')}: {str(e)}")
                # Add a minimal safe solution
                normalized_solutions.append({
                    'id': f"solution_{hash(str(solution))}",
                    'name': solution.get('name', 'Unknown Solution'),
                    'description': f"Complete {solution.get('name', 'technology solution')}",
                    'price': solution.get('price', 0),
                    'features': [],
                    'benefits': []
                })
        
        return normalized_solutions

    def _build_recommendation_context(self, recommendations: List[Dict[str, Any]]) -> str:
        """Build context for recommendation presentation"""
        
        context = "🎯 RECOMMENDATION ANALYSIS:\n\n"
        
        if not recommendations:
            context += "No specific recommendations available at this time.\n"
            return context
        
        # Add top recommendations
        context += "=== TOP RECOMMENDATIONS ===\n"
        for i, rec in enumerate(recommendations[:3], 1):
            context += f"\n{i}. {rec.get('name', 'Unknown Product')}\n"
            context += f"   Description: {rec.get('description', 'No description available')}\n"
            context += f"   Price: ${rec.get('price', 0):,.2f}\n"
            context += f"   Suitability: {rec.get('suitability_score', 0):.1%}\n"
            
            if rec.get('features'):
                context += "   Key Features:\n"
                for feature in rec.get('features', [])[:3]:
                    context += f"   • {feature}\n"
            
            if rec.get('benefits'):
                context += "   Business Benefits:\n"
                for benefit in rec.get('benefits', [])[:3]:
                    context += f"   • {benefit}\n"
        
        # Add recommendation strategy
        context += "\n=== RECOMMENDATION STRATEGY ===\n"
        context += "1. ONLY present products that have been successfully retrieved and validated from the database\n"
        context += "2. Each recommendation MUST have a valid product ID and exist in the database\n"
        context += "3. Focus on benefits and ROI, not just features\n"
        context += "4. Be ready to explain why these solutions are the best fit\n"
        context += "5. Guide toward selection and quote generation\n"
        
        return context
    
    def _add_recommendation_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        recommendation_context: str
    ) -> List[AIMessage]:
        """Add recommendation-focused context to messages"""
        
        system_prompt = """You are an expert B2B technology sales consultant presenting personalized recommendations. Your goal is to guide the customer toward selecting the best solution for their needs.

KEY OBJECTIVES:
1. Present recommendations in order of suitability
2. Focus on business value and ROI
3. Address potential concerns proactively
4. Guide toward selection and next steps
5. Maintain consultative approach

PRESENTATION APPROACH:
• Start with the most suitable recommendation
• Explain why it's the best fit for their needs
• Highlight key benefits and value
• Be ready to discuss alternatives
• Guide toward selection and quote generation"""
        
        enhanced_messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="system", content=recommendation_context),
        ]
        
        # Add customer context if available
        if customer_context:
            customer_info = self._build_customer_context(customer_context)
            enhanced_messages.append(AIMessage(role="system", content=customer_info))
        
        # Add conversation history
        enhanced_messages.extend(messages)
        
        return enhanced_messages
    
    def _detect_lazy_user_patterns(self, messages: List[AIMessage]):
        """Detect patterns that indicate a lazy user"""
        if not messages:
            return
            
        # Check for short messages
        recent_messages = messages[-3:] if len(messages) > 3 else messages
        short_messages = sum(1 for msg in recent_messages if len(msg.content.split()) < 3)
        self.lazy_user_indicators["short_messages"] = short_messages
        
        # Check for template usage
        template_usage = sum(1 for msg in recent_messages 
                           if any(template in msg.content.lower() 
                                 for template in self.quick_start_templates.values()))
        self.lazy_user_indicators["template_usage"] = template_usage
        
        # Check for help requests
        help_requests = sum(1 for msg in recent_messages 
                          if "help" in msg.content.lower() or 
                             "what" in msg.content.lower() or
                             "how" in msg.content.lower())
        self.lazy_user_indicators["help_requests"] = help_requests

    def _is_lazy_user(self) -> bool:
        """Determine if the user is exhibiting lazy user patterns"""
        return (
            self.lazy_user_indicators["short_messages"] >= 2 or
            self.lazy_user_indicators["template_usage"] >= 1 or
            self.lazy_user_indicators["help_requests"] >= 2
        )

    async def _handle_lazy_user_interaction(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]]
    ) -> AIResponse:
        """Handle interaction with lazy users by providing more guided assistance"""
        
        # Get the last message
        last_message = messages[-1].content if messages else ""
        
        # Build lazy user assistance context
        assistance_context = f"""You are helping a user who prefers quick, guided interactions. 
        Provide clear, concise responses with specific options and next steps.
        
        QUICK OPTIONS:
        1. "I need a quote" - Start quote process
        2. "Compare products" - Compare different options
        3. "Show me options" - View available products
        4. "Help me choose" - Get personalized recommendations
        5. "Tell me more" - Get detailed information
        
        USER'S LAST MESSAGE: {last_message}
        
        Provide a helpful response that:
        1. Acknowledges their message
        2. Offers 2-3 specific next steps
        3. Uses simple, clear language
        4. Includes clickable options if possible
        5. Keeps the response brief and actionable"""
        
        enhanced_messages = [
            AIMessage(role="system", content=assistance_context),
            *messages
        ]
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        # Add lazy user assistance metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
            
        response.metadata.update({
            'lazy_user_assistance': True,
            'quick_options': [
                "Get a quote",
                "Compare products",
                "View options",
                "Get recommendations",
                "Learn more"
            ],
            'user_patterns': self.lazy_user_indicators
        })
        
        return response 

    def _update_asked_questions(self, messages: List[AIMessage]):
        """Update the set of asked questions from recent messages"""
        if not messages:
            return
            
        # Look at the last few messages
        recent_messages = messages[-3:] if len(messages) > 3 else messages
        
        # Extract questions from assistant messages
        for msg in recent_messages:
            if msg.role == "assistant":
                # Simple question detection
                questions = [q.strip() for q in msg.content.split('?') if q.strip()]
                self.asked_questions.update(questions)
                
                # Also track questions with question marks
                question_mark_questions = [q.strip() for q in msg.content.split('?') if '?' in q]
                self.asked_questions.update(question_mark_questions)

    async def _handle_recommendation_stage(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Handle the solution presentation and recommendation stage"""
        
        print("🎯 Handling recommendation stage...")
        
        try:
            # Get product recommendations
            retrieval_result = await self._collaborate_with_retriever_agent(
                messages=messages,
                customer_context=customer_context,
                force_retrieval=True  # Force retrieval to ensure fresh recommendations
            )
            
            # Store recommendations for later use
            self.product_recommendations = retrieval_result
            
            # Check if user has selected a recommendation
            last_message = messages[-1].content.lower() if messages else ""
            selected_recommendation = None
            info_requested = False
            
            # Enhanced product selection detection
            for product in retrieval_result.get('products', []):
                try:
                    product_name = product.get('name', '').lower()
                    product_model = product.get('model', '').lower()
                    product_specs = product.get('specifications', {})
                    
                    # Check for exact product name or model match
                    if product_name in last_message or product_model in last_message:
                        selected_recommendation = product
                        flow_analysis['recommendation_selected'] = True
                        flow_analysis['should_generate_quote'] = True
                        flow_analysis['quote_ready'] = True
                        break
                        
                    # Check for partial matches in product specifications
                    for spec_key, spec_value in product_specs.items():
                        if isinstance(spec_value, str):
                            spec_value = spec_value.lower()
                            if spec_value in last_message:
                                selected_recommendation = product
                                flow_analysis['recommendation_selected'] = True
                                flow_analysis['should_generate_quote'] = True
                                flow_analysis['quote_ready'] = True
                                break
                                
                    # Check for RAID configuration mentions
                    if 'raid' in last_message and 'raid' in str(product_specs).lower():
                        selected_recommendation = product
                        flow_analysis['recommendation_selected'] = True
                        flow_analysis['should_generate_quote'] = True
                        flow_analysis['quote_ready'] = True
                        break
                        
                except Exception as e:
                    print(f"⚠️ Error processing product: {str(e)}")
                    continue
            
            # Check for explicit quote requests
            explicit_quote_request = any(phrase in last_message for phrase in [
                "give me quote", "prepare quote", "generate quote", "send quote",
                "quote please", "need quote", "want quote", "quote for"
            ])
            
            # Update flow analysis based on selection or quote request
            if explicit_quote_request and not info_requested:
                flow_analysis['recommendation_selected'] = True
                flow_analysis['should_generate_quote'] = True
                flow_analysis['quote_ready'] = True
                # Store the selected recommendation in customer context
                if customer_context is None:
                    customer_context = {}
                if selected_recommendation:
                    customer_context['selected_recommendation'] = selected_recommendation
                else:
                    # If no specific selection but quote requested, use the first recommendation
                    first_product = retrieval_result.get('products', [])[0] if retrieval_result.get('products') else None
                    if first_product:
                        customer_context['selected_recommendation'] = first_product
                    else:
                        raise ValueError("No recommendations available for quote generation")
            
            # Build recommendation context
            recommendation_context = self._build_recommendation_context(
                retrieval_result.get('products', []) + retrieval_result.get('solutions', [])
            )
            
            # Add recommendation context to messages
            enhanced_messages = self._add_recommendation_context(
                messages=messages,
                customer_context=customer_context,
                recommendation_context=recommendation_context
            )
            
            # If info was requested, add specific product details
            if info_requested and selected_recommendation:
                try:
                    product_details = f"""
DETAILED PRODUCT INFORMATION FOR {selected_recommendation.get('name', 'Selected Product')}:

SPECIFICATIONS:
{json.dumps(selected_recommendation.get('specifications', {}), indent=2)}

FEATURES:
{chr(10).join(f'• {feature}' for feature in selected_recommendation.get('features', []))}

BENEFITS:
{chr(10).join(f'• {benefit}' for benefit in selected_recommendation.get('benefits', []))}

PRICING:
• Base Price: ${float(selected_recommendation.get('price', 0)):,.2f}
• Additional options available

Please provide more specific information about what aspects of the product you'd like to know more about.
"""
                    enhanced_messages.append(AIMessage(role="system", content=product_details))
                except Exception as e:
                    print(f"⚠️ Error generating product details: {str(e)}")
                    # Add basic product info if detailed info fails
                    basic_info = f"""
BASIC PRODUCT INFORMATION FOR {selected_recommendation.get('name', 'Selected Product')}:

{selected_recommendation.get('description', 'No description available')}

Please let me know what specific information you'd like to know about this product.
"""
                    enhanced_messages.append(AIMessage(role="system", content=basic_info))
            
            # Generate response with recommendations
            response = await self.base_provider.generate_response(enhanced_messages)
            
            # Add recommendation metadata
            if not hasattr(response, 'metadata') or response.metadata is None:
                response.metadata = {}
                
            response.metadata.update({
                'recommendations_presented': True,
                'recommendation_selected': flow_analysis['recommendation_selected'],
                'should_generate_quote': flow_analysis['should_generate_quote'],
                'quote_ready': flow_analysis['quote_ready'],
                'product_recommendations': retrieval_result.get('products', []),
                'solution_recommendations': retrieval_result.get('solutions', []),
                'retrieval_confidence': retrieval_result.get('retrieval_confidence', 0),
                'search_methods': retrieval_result.get('search_methods', {}),
                'selected_recommendation': selected_recommendation,
                'info_requested': info_requested
            })
            
            return response
            
        except Exception as e:
            print(f"❌ Error in recommendation stage: {str(e)}")
            import traceback
            print(traceback.format_exc())
            # Return a safe response
            return AIResponse(
                content="I apologize, but I encountered an error while processing the recommendations. Could you please try asking about the products again?",
                model="enhanced-sales-agent",
                provider=self.provider_name,
                metadata={
                    'error': str(e),
                    'recommendations_presented': False,
                    'recommendation_selected': False,
                    'should_generate_quote': False,
                    'quote_ready': False
                }
            ) 