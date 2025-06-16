import json
from typing import List, Dict, Any, Optional
from datetime import datetime
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
            print("🔧 Using Hybrid Product Retriever (Elasticsearch keyword + vector search)")
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
        
        # Handle enum format vs string format for current_stage
        if hasattr(current_stage, 'value'):
            current_stage_str = current_stage.value
        elif isinstance(current_stage, str):
            current_stage_str = current_stage.lower()
        else:
            current_stage_str = str(current_stage).lower()
        
        # Clean up any enum prefixes
        if '.' in current_stage_str:
            current_stage_str = current_stage_str.split('.')[-1]
        
        print(f"🔍 Processing current_stage: '{current_stage}' -> normalized: '{current_stage_str}'")
        
        # Priority 1: Handle quote-ready conversations (AI determined OR explicit request)
        if (enhanced_quote_ready or 
            (flow_analysis.get('quote_ready', False) and flow_analysis.get('should_generate_quote', False)) or
            (current_stage_str == 'quote_ready' and flow_analysis.get('decision_readiness_score', 0) >= 70)):
            print("🎯 Handling quote-ready conversation (AI-determined or explicit request)")
            # Go directly to quote generation without checking for recommendation context
            response = await self._handle_quote_ready_conversation(messages, customer_context, flow_analysis)
        
        # Priority 2: Handle solution presentation and recommendation stage
        elif current_stage_str == 'solution_presentation' or (current_stage_str == 'deep_discovery' and flow_analysis.get('technical_requirements_score', 0) > 60):
            print("🎯 Routing to recommendation stage for solution presentation")
            response = await self._handle_recommendation_stage(messages, customer_context, flow_analysis)
        
        # Priority 3: Handle discovery stages
        else:
            print(f"🎯 Routing to discovery stage: {current_stage_str}")
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
        """Handle conversation when ready for quote generation - simplified without product retrieval"""
        
        print("✅ Conversation ready for quote generation")
        print(f"🔍 Debug - Quote ready conversation input:")
        print(f"   messages count: {len(messages)}")
        print(f"   customer_context keys: {list(customer_context.keys()) if customer_context else 'None'}")
        print(f"   flow_analysis keys: {list(flow_analysis.keys())}")
        
        # Simplified approach - go directly to quote generation without product retrieval
        print("🎯 Proceeding directly to quote generation without product retrieval")
        
        # Prepare minimal customer context for quote generation
        if customer_context is None:
            customer_context = {}
            print("🔍 Debug - Created empty customer_context")
        
        # Add basic customer info if not already present
        if 'company_name' not in customer_context:
            customer_context['company_name'] = 'Valued Customer'
            print("🔍 Debug - Added default company_name")
        if 'contact_name' not in customer_context:
            customer_context['contact_name'] = 'Dear Customer'
            print("🔍 Debug - Added default contact_name")
        if 'industry' not in customer_context:
            customer_context['industry'] = 'Technology'
            print("🔍 Debug - Added default industry")
        
        print(f"🔍 Debug - Final customer_context: {customer_context}")
        print(f"🔍 Debug - Conversation context length: {len(self.conversation_context)}")
        
        print("✅ Proceeding with simplified quote generation")
        
        try:
            # Generate quote directly using conversation messages
            print("🔍 Debug - Calling quote_agent.generate_quote_from_conversation...")
            quote = await self.quote_agent.generate_quote_from_conversation(
                conversation_messages=list(self.conversation_context),
                customer_context=customer_context
            )
            print(f"🔍 Debug - Quote generation result type: {type(quote)}")
            if quote:
                print(f"🔍 Debug - Quote keys: {list(quote.keys())}")
                print(f"🔍 Debug - Quote ID: {quote.get('quote_id', 'None')}")
                print(f"🔍 Debug - Quote number: {quote.get('quote_number', 'None')}")
                print(f"🔍 Debug - PDF generated: {quote.get('pdf_generated', 'None')}")
                print(f"🔍 Debug - PDF URL: {quote.get('pdf_url', 'None')}")
            else:
                print("🔍 Debug - Quote is None!")
                
        except Exception as e:
            print(f"❌ Debug - Quote generation failed with exception: {str(e)}")
            import traceback
            print(f"❌ Debug - Traceback: {traceback.format_exc()}")
            quote = None
        
        # Generate a simple sales response
        print("🔍 Debug - Generating sales response...")
        try:
            simple_sales_prompt = """You are a B2B sales consultant who has just generated a quote for the customer. 
            Acknowledge that you've prepared their quote and let them know it's being processed. 
            Keep your response brief and professional, focusing on the next steps."""
            
            enhanced_messages = [
                AIMessage(role="system", content=simple_sales_prompt),
                *messages
            ]
            
            response = await self.base_provider.generate_response(enhanced_messages)
            print(f"🔍 Debug - Sales response generated successfully")
        except Exception as e:
            print(f"❌ Debug - Sales response generation failed: {str(e)}")
            # Create a fallback response
            response = AIResponse(
                content="I've prepared your quote and it's being processed. Please check back shortly for the download links.",
                model="fallback",
                provider=self.provider_name
            )
        
        # Add quote information to the response if quote was generated successfully
        if quote:
            print(f"✅ Quote generated successfully: {quote.get('quote_number', 'Unknown')}")
            
            try:
                # Generate pitch deck for the quote
                print("🔍 Debug - Starting pitch deck generation...")
                await self._generate_pitch_deck_for_quote(quote)
                print(f"🔍 Debug - Pitch deck generation completed")
                print(f"🔍 Debug - Pitch deck generated: {quote.get('pitch_deck_generated', 'None')}")
                print(f"🔍 Debug - Pitch deck URL: {quote.get('pitch_deck_url', 'None')}")
            except Exception as e:
                print(f"❌ Debug - Pitch deck generation failed: {str(e)}")
                import traceback
                print(f"❌ Debug - Pitch deck traceback: {traceback.format_exc()}")
            
            try:
                # Enhance response with quote information
                print("🔍 Debug - Enhancing response with quote information...")
                response = self._enhance_response_with_dynamic_quote(response, quote, quote.get('quote_id', 'unknown'))
                print("🔍 Debug - Response enhancement completed")
            except Exception as e:
                print(f"❌ Debug - Response enhancement failed: {str(e)}")
                import traceback
                print(f"❌ Debug - Response enhancement traceback: {traceback.format_exc()}")
            
            # Add quote metadata
            try:
                if not hasattr(response, 'metadata') or response.metadata is None:
                    response.metadata = {}
                
                metadata_update = {
                    'quote_generated': True,
                    'quote_id': quote.get('quote_id'),
                    'quote_number': quote.get('quote_number'),
                    'quote_total': quote.get('financials', {}).get('total') if 'financials' in quote else quote.get('total'),
                    'pdf_generated': quote.get('pdf_generated', False),
                    'pdf_url': quote.get('pdf_url'),
                    'pitch_deck_generated': quote.get('pitch_deck_generated', False),
                    'pitch_deck_url': quote.get('pitch_deck_url'),
                    'generation_method': 'simplified_conversation_only'
                }
                
                response.metadata.update(metadata_update)
                print(f"🔍 Debug - Metadata updated: {metadata_update}")
                print(f"📄 Quote metadata added to response")
                
            except Exception as e:
                print(f"❌ Debug - Metadata update failed: {str(e)}")
                import traceback
                print(f"❌ Debug - Metadata traceback: {traceback.format_exc()}")
            
        else:
            print("❌ Quote generation failed")
            # Add error information to response
            try:
                if not hasattr(response, 'metadata') or response.metadata is None:
                    response.metadata = {}
                response.metadata['quote_generation_error'] = "Failed to generate quote"
                print("🔍 Debug - Added quote generation error to metadata")
            except Exception as e:
                print(f"❌ Debug - Failed to add error metadata: {str(e)}")
        
        print(f"🔍 Debug - Final response content length: {len(response.content) if response.content else 0}")
        print(f"🔍 Debug - Final response metadata keys: {list(response.metadata.keys()) if hasattr(response, 'metadata') and response.metadata else 'None'}")
        
        return response
    
    async def _handle_discovery_conversation(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Handle discovery and information gathering conversations"""
        
        current_stage = flow_analysis.get('current_stage', 'initial_discovery')
        
        # Handle enum format vs string format for current_stage
        if hasattr(current_stage, 'value'):
            current_stage_str = current_stage.value
        elif isinstance(current_stage, str):
            current_stage_str = current_stage.lower()
        else:
            current_stage_str = str(current_stage).lower()
        
        # Clean up any enum prefixes
        if '.' in current_stage_str:
            current_stage_str = current_stage_str.split('.')[-1]
        
        print(f"🔍 Handling discovery conversation - stage: {current_stage} -> normalized: {current_stage_str}")
        
        # If this is actually a quote_ready stage that got routed here by mistake, redirect
        if (current_stage_str == 'quote_ready' or 
            (flow_analysis.get('quote_ready', False) and flow_analysis.get('should_generate_quote', False))):
            print("🔄 Quote-ready stage detected in discovery handler - redirecting to quote generation")
            return await self._handle_quote_ready_conversation(messages, customer_context, flow_analysis)
        
        # Only retrieve products if we're in deep discovery or solution presentation
        if current_stage_str in ['deep_discovery', 'solution_presentation']:
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
                'current_stage': current_stage_str
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
        
        # Get prompt from admin dashboard
        prompt_manager = get_prompt_manager()
        
        # Try to get the prompt from the discovery category first, then sales_agent
        discovery_prompt = prompt_manager.get_prompt("discovery", "main_system_prompt", "")
        if discovery_prompt:
            return discovery_prompt
        
        # Fallback to sales_agent category
        sales_prompt = prompt_manager.get_prompt("sales_agent", "main_system_prompt", "")
        if sales_prompt:
            return sales_prompt
        
        # Final fallback to hardcoded prompt
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
            
            # Add debugging for conversation content
            print(f"🔍 Debug - Conversation analysis for retrieval:")
            print(f"   Messages count: {len(messages)}")
            print(f"   Last user message: {messages[-1].content[:200] if messages else 'None'}...")
            if customer_context:
                print(f"   Customer context keys: {list(customer_context.keys())}")
            
            # Get product recommendations
            retrieval_result = await self.retriever_agent.retrieve_products(messages, customer_context)
            
            # Add debugging for retrieval result
            print(f"🔍 Debug - Retrieval result analysis:")
            print(f"   Type: {type(retrieval_result)}")
            print(f"   Keys: {list(retrieval_result.keys()) if isinstance(retrieval_result, dict) else 'Not a dict'}")
            if isinstance(retrieval_result, dict):
                print(f"   Products found: {len(retrieval_result.get('products', []))}")
                print(f"   Solutions found: {len(retrieval_result.get('solutions', []))}")
                print(f"   Requirements extracted: {retrieval_result.get('requirements', {}).keys() if retrieval_result.get('requirements') else 'None'}")
                
                # Debug requirements in detail
                requirements = retrieval_result.get('requirements', {})
                if requirements:
                    print(f"🔍 Debug - Extracted requirements:")
                    print(f"   Technical requirements: {requirements.get('technical_requirements', [])}")
                    print(f"   Business requirements: {requirements.get('business_requirements', [])}")
                    print(f"   Product categories: {requirements.get('product_categories', [])}")
                    print(f"   Search terms: {requirements.get('search_terms', [])}")
                    print(f"   Use case: {requirements.get('use_case', 'Unknown')}")
                    print(f"   Semantic query: {requirements.get('semantic_query', 'None')}")
                
                # Debug first few products found
                products = retrieval_result.get('products', [])
                if products:
                    print(f"🔍 Debug - First 3 products found:")
                    for i, product in enumerate(products[:3]):
                        print(f"   {i+1}. {product.get('name', 'Unknown')} (Category: {product.get('category', 'Unknown')}, Price: ${product.get('price', 0)})")
                else:
                    print(f"❌ Debug - No products found!")
            
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
    def _quote_to_text(self,quote: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"Quote Number: {quote.get('quote_number', '')}")
        lines.append(f"Title: {quote.get('quote_title', '')}")
        lines.append(f"Customer: {quote.get('customer_info', {}).get('name', 'N/A')}")
        lines.append(f"Total: {quote.get('currency', '')} {quote.get('total', 0):,.2f}")
        lines.append("Line Items:")
        for item in quote.get("line_items", []):
            lines.append(f"- {item.get('description', 'No desc')} x {item.get('quantity', 1)} @ {item.get('price', 0)}")
        return "\n".join(lines)

    async def _collaborate_with_quote_agent(
        self, 
        response: AIResponse, 
        recommendation_context: Dict[str, Any],
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
        
        # Prepare enhanced customer context
        enhanced_customer_context = {
            **(customer_context or {}),
            'product_recommendations': self.product_recommendations.get('products', []),
            'solution_recommendations': self.product_recommendations.get('solutions', []),
            'extracted_requirements': self.customer_requirements,
            'conversation_analysis': flow_analysis,
            'flow_confidence': flow_analysis.get('confidence_level', 'medium'),
            'business_context_score': flow_analysis.get('business_context_score', 50),
            'technical_requirements_score': flow_analysis.get('technical_requirements_score', 50)
        }
        
        print(f"📝 Enhanced context prepared with {len(enhanced_conversation)} messages")
        
        # Let quote agent generate quote with enhanced context
        try:
            quote = await self.quote_agent.generate_quote_from_conversation(
                enhanced_conversation,
                enhanced_customer_context
            )
            
            if quote:
                print(f"✅ Quote Agent provided enhanced quote with ID: {quote.get('id')}")
                print(f"📄 PDF URL: {quote.get('pdf_url', 'Not generated')}")
                
                # Add quote to response metadata
                response.metadata['quote'] = quote
                response.metadata['quote_generated'] = True
                response.metadata['quote_id'] = quote.get('id')
                
                # Enhance sales response to incorporate the quote
                response = self._enhance_response_with_dynamic_quote(response, quote)
            else:
                print("❌ Quote agent couldn't generate quote from enhanced conversation")
                response.metadata['quote_generation_failed'] = True
                
                # Add fallback message
                response.content += "\n\n💡 I'd be happy to prepare a detailed quote for you! Let me gather a bit more information to ensure I provide the most accurate recommendations."
                
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
        
        # Get prompt from admin dashboard
        prompt_manager = get_prompt_manager()
        
        # Try to get sales agent prompt with variables
        system_prompt = prompt_manager.get_system_prompt("sales_agent", variables={"stage": "quote_ready"})
        
        if not system_prompt:
            # Fallback to hardcoded prompt
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
            context += f"🧠 Elasticsearch (vector): {search_methods.get('vector_products', 0)} products\n"
            context += f"💡 Solutions (vector): {search_methods.get('vector_solutions', 0)} solutions\n"
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
        
        context += "\n💡 **Use these REAL products found through hybrid search (keyword + AI vector) to provide specific recommendations!**"
        
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
        
        print(f"🔍 Debug - Enhancing response with quote info:")
        print(f"   Quote keys: {list(quote.keys())}")
        print(f"   PDF generated: {quote.get('pdf_generated', 'Not set')}")
        print(f"   PDF URL: {quote.get('pdf_url', 'Not set')}")
        print(f"   Pitch deck generated: {quote.get('pitch_deck_generated', 'Not set')}")
        print(f"   Pitch deck URL: {quote.get('pitch_deck_url', 'Not set')}")
        
        # Always enhance the response if we have a quote, regardless of PDF status
        if quote:
            # Add professional quote presentation with dynamic context
            response.content += f"\n\n🎯 **Excellent! Based on our thorough discussion and your specific requirements, I've prepared a comprehensive, customized quote using our intelligent product matching system.**"
            response.content += f"\n\n📋 **Quote #{quote.get('quote_number', 'N/A')}**"
            
            # Highlight the thorough discovery process
            response.content += f"\n\n✅ **Complete Requirements Analysis:** Our conversation covered all the essential areas needed for an accurate quote - your business context, technical requirements, operational needs, and specific challenges."
            
            # Highlight the intelligent matching
            if self.product_recommendations.get('retrieval_confidence', 0) > 0.7:
                response.content += f"\n\n🤖 **AI-Powered Recommendations:** Our system identified a {self.product_recommendations.get('retrieval_confidence', 0):.1%} match with your requirements based on our comprehensive product intelligence!"
            
            # Add pricing summary
            if 'financials' in quote:
                financials = quote['financials']
                response.content += f"\n\n💰 **Investment Summary:**"
                response.content += f"\n• Subtotal: **${financials['subtotal']:,.2f}**"
                response.content += f"\n• Tax: ${financials['tax_amount']:,.2f}"
                response.content += f"\n• **Total Investment: ${financials['total']:,.2f}**"
                if quote.get('valid_until'):
                    try:
                        response.content += f"\n• Quote valid until: {datetime.fromisoformat(quote['valid_until']).strftime('%B %d, %Y')}"
                    except:
                        response.content += f"\n• Quote valid until: {quote['valid_until']}"
            elif 'pricing' in quote:
                # Support legacy format
                pricing = quote['pricing']
                response.content += f"\n\n💰 **Investment Summary:**"
                response.content += f"\n• Subtotal: **${pricing['subtotal']:,.2f}**"
                response.content += f"\n• Tax: ${pricing['tax_amount']:,.2f}"
                response.content += f"\n• **Total Investment: ${pricing['total']:,.2f}**"
                if quote.get('valid_until'):
                    try:
                        response.content += f"\n• Quote valid until: {datetime.fromisoformat(quote['valid_until']).strftime('%B %d, %Y')}"
                    except:
                        response.content += f"\n• Quote valid until: {quote['valid_until']}"
            
            # Add PDF download link if available
            if quote.get('pdf_generated', False) and quote.get('pdf_url'):
                response.content += f"\n\n📄 **[Download Complete Quote PDF]({quote['pdf_url']})**"
            else:
                response.content += f"\n\n📄 **Quote PDF:** Currently being generated..."
                if quote.get('pdf_error'):
                    response.content += f" (Note: PDF generation encountered an issue - please contact support if needed)"
            
            # Add pitch deck download link only if it was generated successfully
            if quote.get('pitch_deck_generated', False) and quote.get('pitch_deck_url'):
                response.content += f"\n\n📊 **[Download Pitch Deck]({quote['pitch_deck_url']})**"
            
            # Enhanced next steps
            response.content += f"\n\n**Next Steps:**"
            response.content += f"\n1. Review the detailed quote with all selected products and solutions"
            if quote.get('pitch_deck_generated', False):
                response.content += f"\n2. Check out the pitch deck for a visual overview of the solution"
                response.content += f"\n3. Let me know if you'd like to discuss any aspects in more detail"
                response.content += f"\n4. I can arrange product demos or technical consultations if helpful"
                response.content += f"\n5. We can finalize implementation timeline and support arrangements"
            else:
                response.content += f"\n2. Let me know if you'd like to discuss any aspects in more detail"
                response.content += f"\n3. I can arrange product demos or technical consultations if helpful"
                response.content += f"\n4. We can finalize implementation timeline and support arrangements"
            
            response.content += f"\n\nThis quote reflects our thorough understanding of your business needs and technical requirements. I'm confident these recommendations will deliver the performance and value you're looking for! 🚀"
            
        return response
    
    def _enhanced_quote_readiness_check(self, messages: List[AIMessage], flow_analysis: Dict[str, Any]) -> bool:
        """Enhanced logic to detect when customer is truly ready for a quote - considers both explicit requests and AI analysis"""
        
        if not messages:
            return False
        
        # Get the last few messages for analysis
        recent_messages = messages[-3:] if len(messages) > 3 else messages
        recent_text = " ".join([msg.content.lower() for msg in recent_messages if msg.content]).strip()
        
        print(f"🔍 Enhanced Quote Check - Recent text: {recent_text[:200]}...")
        
        # Very specific quote request indicators - only these should trigger quote generation
        explicit_quote_indicators = [
            "prepare a detailed quote", "could you please prepare", "generate a quote",
            "send me a quote", "i need a quote", "provide a quote", "create a quote",
            "quotation please", "detailed proposal", "pricing proposal", "formal quote",
            "can you quote", "give me a quote", "send me pricing", "detailed quote",
            "i want a quote", "i would like a quote", "please quote", "quote me",
            "prepare quote", "create quote", "generate quote"
        ]
        
        # General pricing indicators that should NOT trigger quote generation by themselves
        general_pricing_indicators = [
            "how much", "what's the price", "pricing", "cost", "budget",
            "what would it cost", "price range", "roughly cost", "approximately cost",
            "ballpark", "estimate", "around", "about how much"
        ]
        
        # Check for explicit quote requests first
        explicit_quote_request = any(phrase in recent_text for phrase in explicit_quote_indicators)
        
        # Check for general pricing inquiries (should not trigger quotes by themselves)
        general_pricing_inquiry = any(phrase in recent_text for phrase in general_pricing_indicators) and not explicit_quote_request
        
        # Check AI flow analysis for readiness
        ai_quote_ready = flow_analysis.get('quote_ready', False)
        ai_should_generate = flow_analysis.get('should_generate_quote', False)
        ai_current_stage = flow_analysis.get('current_stage', '')
        
        # Handle enum format vs string format for current_stage
        if hasattr(ai_current_stage, 'value'):
            ai_current_stage_str = ai_current_stage.value
        elif isinstance(ai_current_stage, str):
            ai_current_stage_str = ai_current_stage.lower()
        else:
            ai_current_stage_str = str(ai_current_stage).lower()
        
        # Clean up any enum prefixes
        if '.' in ai_current_stage_str:
            ai_current_stage_str = ai_current_stage_str.split('.')[-1]
        
        print(f"🎯 Quote Readiness Analysis:")
        print(f"   📝 Explicit Quote Request: {explicit_quote_request}")
        print(f"   💰 General Pricing Inquiry: {general_pricing_inquiry}")
        print(f"   🤖 AI Quote Ready: {ai_quote_ready}")
        print(f"   🤖 AI Should Generate: {ai_should_generate}")
        print(f"   🤖 AI Current Stage: {ai_current_stage} -> {ai_current_stage_str}")
        
        # If there's an explicit quote request, proceed with quote generation
        if explicit_quote_request:
            print("✅ EXPLICIT quote request detected - proceeding with quote generation")
            flow_analysis['quote_ready'] = True
            flow_analysis['should_generate_quote'] = True
            flow_analysis['recommendation_selected'] = True
            return True
            
        # If AI determines quote readiness, trust the AI analysis
        if ai_quote_ready and ai_should_generate:
            print("✅ AI-DETERMINED quote readiness - proceeding with quote generation")
            flow_analysis['quote_ready'] = True
            flow_analysis['should_generate_quote'] = True
            flow_analysis['recommendation_selected'] = True
            return True
        
        # If current stage is quote_ready with high decision readiness, proceed
        if ai_current_stage_str == 'quote_ready' and flow_analysis.get('decision_readiness_score', 0) >= 70:
            print("✅ AI STAGE-DETERMINED quote readiness - proceeding with quote generation")
            flow_analysis['quote_ready'] = True
            flow_analysis['should_generate_quote'] = True
            flow_analysis['recommendation_selected'] = True
            return True
        
        # If it's just a general pricing inquiry without AI readiness, stay in recommendation stage
        if general_pricing_inquiry and not ai_quote_ready:
            print("💰 General pricing inquiry without AI readiness - staying in recommendation stage")
            flow_analysis['quote_ready'] = False
            flow_analysis['should_generate_quote'] = False
            flow_analysis['recommendation_selected'] = False
            return False
            
        # Calculate readiness scores for edge cases
        business_context_score = flow_analysis.get('business_context_score', 0)
        technical_score = flow_analysis.get('technical_requirements_score', 0)
        decision_score = flow_analysis.get('decision_readiness_score', 0)
        
        # Conservative overall readiness calculation - but consider AI analysis
        overall_readiness = (
            business_context_score * 0.3 +    # Business context weight
            technical_score * 0.3 +           # Technical requirements weight
            decision_score * 0.4               # Decision readiness weight (higher)
        )
        
        print(f"🎯 Conservative Readiness Scores:")
        print(f"   💼 Business Context: {business_context_score}%")
        print(f"   🔧 Technical Requirements: {technical_score}%")
        print(f"   📋 Decision Readiness: {decision_score}%")
        print(f"   📊 Overall Readiness: {overall_readiness:.1f}%")
        
        # Lower threshold when combined with AI analysis suggesting readiness
        if ai_quote_ready or ai_current_stage_str == 'quote_ready':
            threshold = 60  # Lower threshold when AI agrees
            print(f"🤖 AI supports readiness - using lower threshold: {threshold}%")
        else:
            threshold = 80  # Higher threshold without AI support
            print(f"📋 No AI support - using higher threshold: {threshold}%")
        
        is_ready = overall_readiness >= threshold
        
        if is_ready:
            print(f"✅ Readiness score above threshold - proceeding to quote")
        else:
            print(f"📋 Readiness below threshold - staying in recommendation/discovery stage")
        
        print(f"🎯 Final Decision: {'READY FOR QUOTE' if is_ready else 'CONTINUE RECOMMENDATION DISCUSSION'}")
        
        # Update flow analysis with final decision
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
            
            print(f"📦 Raw retrieval results: {len(products)} products, {len(solutions)} solutions")
            
            # Normalize products to ensure all required fields exist
            products = self._normalize_product_data(products)
            solutions = self._normalize_solution_data(solutions)
            
            print(f"✅ Normalized: {len(products)} products, {len(solutions)} solutions")
            
            # Combine and format recommendations
            recommendations = []
            
            # Add product recommendations
            for i, product in enumerate(products):
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

                    # Safely handle hybrid score (from Elasticsearch keyword + vector scoring)
                    hybrid_score = 0.0
                    for score_field in ['hybrid_score', 'score', 'relevance_score', 'elasticsearch_score']:
                        if score_field in product:
                            try:
                                hybrid_score = float(product[score_field])
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    # If no score found, assign based on position (higher position = lower score)
                    if hybrid_score == 0.0:
                        hybrid_score = max(0.1, 1.0 - (i * 0.1))  # Decreasing score based on position
                    
                    # Ensure score is between 0 and 1
                    hybrid_score = max(0.0, min(1.0, abs(hybrid_score)))

                    # Safely handle features and benefits
                    features = product.get('features', [])
                    if not isinstance(features, list):
                        if isinstance(features, str):
                            features = [features]
                        else:
                            features = []
                    
                    benefits = product.get('benefits', [])
                    if not isinstance(benefits, list):
                        if isinstance(benefits, str):
                            benefits = [benefits]
                        else:
                            benefits = []
                    
                    # Generate benefits from features if empty
                    if not benefits and features:
                        benefits = [f"Reliable {feature}" for feature in features[:3]]
                    
                    # Generate default features if empty
                    if not features:
                        features = ["Professional grade", "Enterprise ready", "Reliable performance"]
                    
                    # Ensure we have a valid product ID
                    product_id = product.get('id') or product.get('product_id') or f"product_{hash(product.get('name', 'unknown'))}"

                    recommendation = {
                        'product_id': str(product_id),
                        'name': product.get('name', 'Professional Solution'),
                        'description': product.get('description', f"Professional {product.get('name', 'technology solution')}"),
                        'price': price,
                        'features': features,
                        'benefits': benefits,
                        'suitability_score': hybrid_score,
                        'customization_options': product.get('customization_options', {}),
                        'search_source': product.get('search_source', 'hybrid'),
                        'confidence': hybrid_score,
                        'category': product.get('category', 'general'),
                        'specifications': product.get('specifications', {}),
                        'original_product_data': product  # Keep original data for quote generation
                    }
                    recommendations.append(recommendation)
                    print(f"✅ Added product recommendation: {recommendation['name']} (Score: {hybrid_score:.3f})")
                    
                except Exception as e:
                    print(f"⚠️ Error processing product {product.get('id', 'unknown')}: {str(e)}")
                    continue
            
            # Add solution recommendations if available
            if solutions:
                for i, solution in enumerate(solutions):
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
                        match_score = 0.0
                        for score_field in ['match_score', 'score', 'relevance_score']:
                            if score_field in solution:
                                try:
                                    match_score = float(solution[score_field])
                                    break
                                except (ValueError, TypeError):
                                    continue
                        
                        # If no score found, assign based on position
                        if match_score == 0.0:
                            match_score = max(0.1, 0.8 - (i * 0.1))  # Slightly lower than products
                        
                        # Ensure score is between 0 and 1
                        match_score = max(0.0, min(1.0, abs(match_score)))

                        # Safely handle features and benefits
                        features = solution.get('features', [])
                        if not isinstance(features, list):
                            if isinstance(features, str):
                                features = [features]
                            else:
                                features = []
                        
                        benefits = solution.get('benefits', [])
                        if not isinstance(benefits, list):
                            if isinstance(benefits, str):
                                benefits = [benefits]
                            else:
                                benefits = []
                        
                        # Generate benefits from components if empty
                        if not benefits and solution.get('components'):
                            benefits = [f"Complete {comp} solution" for comp in solution['components'][:3]]
                        
                        # Generate default features if empty
                        if not features:
                            features = ["Complete solution", "End-to-end support", "Scalable architecture"]
                        
                        # Ensure we have a valid solution ID
                        solution_id = solution.get('id') or solution.get('solution_id') or f"solution_{hash(solution.get('name', 'unknown'))}"

                        recommendation = {
                            'product_id': str(solution_id),
                            'name': solution.get('name', 'Complete Business Solution'),
                            'description': solution.get('description', f"Complete {solution.get('name', 'business solution')}"),
                            'price': price,
                            'features': features,
                            'benefits': benefits,
                            'suitability_score': match_score,
                            'customization_options': solution.get('customization_options', {}),
                            'search_source': 'solution',
                            'confidence': match_score,
                            'category': 'solution',
                            'components': solution.get('components', []),
                            'original_solution_data': solution  # Keep original data for quote generation
                        }
                        recommendations.append(recommendation)
                        print(f"✅ Added solution recommendation: {recommendation['name']} (Score: {match_score:.3f})")
                        
                    except Exception as e:
                        print(f"⚠️ Error processing solution {solution.get('id', 'unknown')}: {str(e)}")
                        continue
            
            # Sort recommendations by suitability score (highest first)
            recommendations.sort(key=lambda x: x['suitability_score'], reverse=True)
            
            print(f"✅ Generated {len(recommendations)} total recommendations")
            for i, rec in enumerate(recommendations[:5]):  # Log top 5
                print(f"   {i+1}. {rec['name']} (Score: {rec['suitability_score']:.3f})")
            
            return recommendations
            
        except Exception as e:
            print(f"❌ Recommendation generation failed: {str(e)}")
            import traceback
            print(traceback.format_exc())
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
        """Build context for recommendation presentation with focus on discussion and feedback"""
        
        context = "🎯 RECOMMENDATION DISCUSSION STAGE:\n\n"
        
        if not recommendations:
            context += "⚠️ NO RECOMMENDATIONS AVAILABLE:\n"
            context += "- Ask for more specific requirements\n"
            context += "- Offer to search for different types of solutions\n"
            context += "- Be helpful and consultative\n\n"
            return context
        
        context += "=== PATIENT RECOMMENDATION APPROACH ===\n"
        context += "YOU ARE PRESENTING RECOMMENDATIONS FOR DISCUSSION. Your approach should be:\n"
        context += "1. 🎯 Present the TOP recommendation first with clear business justification\n"
        context += "2. 💬 Ask for their thoughts and feedback on this recommendation\n"
        context += "3. 🔄 Be ready to present alternatives if they want to see other options\n"
        context += "4. ❓ Encourage questions about features, benefits, and implementation\n"
        context += "5. ⏰ Be PATIENT - don't rush to quotes unless explicitly asked\n"
        context += "6. 📊 Compare options when requested\n"
        context += "7. 🤝 Build confidence through explanation and consultation\n\n"
        
        # Add top recommendations with detailed context
        context += "=== AVAILABLE RECOMMENDATIONS ===\n"
        for i, rec in enumerate(recommendations[:5], 1):  # Show up to 5 recommendations
            context += f"\n{i}. **{rec.get('name', 'Unknown Product')}**\n"
            context += f"   Description: {rec.get('description', 'No description available')}\n"
            
            # Add price information carefully
            price = rec.get('price', 0)
            if price and price > 0:
                context += f"   Investment: ${price:,.2f}\n"
            
            # Add suitability score if available
            if rec.get('suitability_score', 0) > 0:
                context += f"   Suitability Match: {rec.get('suitability_score', 0):.1%}\n"
            
            # Add key features
            features = rec.get('features', [])
            if features:
                context += "   Key Features:\n"
                for feature in features[:3]:  # Top 3 features
                    context += f"   • {feature}\n"
            
            # Add benefits
            benefits = rec.get('benefits', [])
            if benefits:
                context += "   Business Benefits:\n"
                for benefit in benefits[:3]:  # Top 3 benefits
                    context += f"   • {benefit}\n"
        
            # Add category/source info
            if rec.get('category'):
                context += f"   Category: {rec.get('category')}\n"
            
            if rec.get('search_source'):
                context += f"   Found via: {rec.get('search_source')}\n"
        
        # Add guidance for the conversation
        context += "\n=== CONVERSATION GUIDELINES ===\n"
        context += "• START with the top recommendation and explain why it's the best fit\n"
        context += "• ASK for their thoughts: 'What do you think about this solution?'\n"
        context += "• LISTEN to their feedback and concerns\n"
        context += "• OFFER alternatives: 'Would you like to see other options?'\n"
        context += "• COMPARE when requested: explain differences clearly\n"
        context += "• EDUCATE about business value, not just technical features\n"
        context += "• BE PATIENT - let them process and ask questions\n"
        context += "• ONLY suggest quotes when they explicitly ask for one\n\n"
        
        context += "=== IMPORTANT REMINDERS ===\n"
        context += "❌ DO NOT automatically suggest quotes or pricing\n"
        context += "❌ DO NOT rush the conversation\n"
        context += "✅ DO focus on understanding their preferences\n"
        context += "✅ DO encourage questions and discussion\n"
        context += "✅ DO explain business value and ROI\n"
        context += "✅ DO offer to compare different options\n"
        context += "✅ DO build confidence in the recommendations\n"
        
        return context
    
    def _add_recommendation_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        recommendation_context: str
    ) -> List[AIMessage]:
        """Add recommendation-focused context to messages"""
        
        # Get prompt from admin dashboard
        prompt_manager = get_prompt_manager()
        
        # Get product recommendation prompt
        system_prompt = prompt_manager.get_system_prompt("product_retriever")
        
        if not system_prompt:
            # Fallback to hardcoded prompt
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
        """Handle the solution presentation and recommendation stage with patience and feedback collection"""
        
        try:
            # Get the last message for analysis
            last_message = messages[-1].content.lower() if messages else ""
            
            # Get product recommendations
            retrieval_result = await self._collaborate_with_retriever_agent(
                messages=messages,
                customer_context=customer_context
            )
            
            # Store retrieval result
            self.product_recommendations = retrieval_result
            
            # Analyze conversation intent more carefully
            intent_analysis = await self._analyze_conversation_intent(messages, customer_context)
            
            # Be more specific about quote requests - only very explicit requests should trigger quote
            explicit_quote_request = any(phrase in last_message for phrase in [
                "prepare a detailed quote", "generate a quote", "send me a quote",
                "i need a quote", "provide a quote", "create a quote",
                "quote please", "detailed proposal", "formal quote"
            ])
            
            # Don't treat general pricing questions as quote requests
            pricing_inquiry = any(phrase in last_message for phrase in [
                "how much", "what's the price", "pricing", "cost", "budget"
            ]) and not explicit_quote_request
            
            print(f"🔍 Debug - Recommendation stage analysis:")
            print(f"   explicit_quote_request: {explicit_quote_request}")
            print(f"   pricing_inquiry: {pricing_inquiry}")
            print(f"   intent_analysis.intent_type: {intent_analysis.get('intent_type')}")
            
            # Store simple recommendation context for quote generation
            recommendation_context = {
                'conversation_messages': [{'role': msg.role, 'content': msg.content} for msg in messages],
                'available_products': retrieval_result.get('products', []),
                'available_solutions': retrieval_result.get('solutions', []),
                'extracted_requirements': retrieval_result.get('requirements', {}),
                'stage': 'recommendation'
            }
            
            # Store context for future quote generation
            flow_analysis['recommendation_context'] = recommendation_context
            if customer_context is None:
                customer_context = {}
            customer_context['recommendation_context'] = recommendation_context
            
            # Only set quote readiness for EXPLICIT quote requests
            if explicit_quote_request:
                flow_analysis['recommendation_selected'] = True
                flow_analysis['should_generate_quote'] = True
                flow_analysis['quote_ready'] = True
                print(f"✅ EXPLICIT quote request detected - ready for quote generation")
                
                # Return to the main flow for quote generation
                return await self._handle_quote_ready_conversation(messages, customer_context, flow_analysis)
            else:
                # Stay in recommendation stage - don't rush to quote
                flow_analysis['recommendation_selected'] = False
                flow_analysis['should_generate_quote'] = False
                flow_analysis['quote_ready'] = False
                print(f"📋 Staying in recommendation stage for discussion and feedback")
            
            # Build recommendation presentation context
            recommendation_display_context = self._build_recommendation_presentation_context(
                retrieval_result.get('products', []),
                retrieval_result.get('solutions', []),
                pricing_inquiry,
                intent_analysis
            )
            
            # Add recommendation context to messages
            enhanced_messages = self._add_patient_recommendation_context(
                messages=messages,
                customer_context=customer_context,
                recommendation_context=recommendation_display_context,
                pricing_inquiry=pricing_inquiry
            )
            
            # Generate response focused on recommendation discussion
            response = await self.base_provider.generate_response(enhanced_messages)
            
            # Add metadata
            if not hasattr(response, 'metadata') or response.metadata is None:
                response.metadata = {}
            
            response.metadata.update({
                'recommendations_presented': True,
                'recommendation_stage': 'active_discussion',
                'explicit_quote_requested': explicit_quote_request,
                'pricing_inquiry': pricing_inquiry,
                'recommendation_selected': False,  # Still discussing
                'should_generate_quote': False,   # Not ready yet
                'quote_ready': False,             # Stay in recommendation stage
                'product_recommendations': retrieval_result.get('products', []),
                'solution_recommendations': retrieval_result.get('solutions', []),
                'retrieval_confidence': retrieval_result.get('retrieval_confidence', 0),
                'search_methods': retrieval_result.get('search_methods', {}),
                'recommendation_context_stored': True,
                'conversation_guidance': 'Focus on recommendation discussion and feedback'
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

    def _build_recommendation_presentation_context(
        self, 
        products: List[Dict[str, Any]], 
        solutions: List[Dict[str, Any]],
        pricing_inquiry: bool,
        intent_analysis: Dict[str, Any]
    ) -> str:
        """Build context for patient recommendation presentation and discussion"""
        
        context = "🎯 RECOMMENDATION PRESENTATION STAGE:\n\n"
        
        context += "=== CONVERSATION STAGE GUIDANCE ===\n"
        context += "YOU ARE IN THE RECOMMENDATION PRESENTATION STAGE. Your goals:\n"
        context += "1. Present 2-3 top recommendations clearly\n"
        context += "2. Explain WHY each recommendation fits their needs\n"
        context += "3. Encourage questions and feedback\n"
        context += "4. Compare options if asked\n"
        context += "5. Be patient - don't rush to quote generation\n"
        context += "6. Only mention quotes if they EXPLICITLY ask for one\n\n"
        
        if pricing_inquiry:
            context += "🔍 USER SHOWED PRICING INTEREST:\n"
            context += "- They asked about pricing/cost but didn't request a formal quote\n"
            context += "- Provide general price ranges if helpful\n"
            context += "- Focus on value and ROI, not just price\n"
            context += "- Ask if they'd like a detailed quote after discussing options\n\n"
        
        if not products and not solutions:
            context += "⚠️ NO RECOMMENDATIONS AVAILABLE:\n"
            context += "- Acknowledge this and ask for more specific requirements\n"
            context += "- Offer to search for different types of solutions\n"
            context += "- Be helpful and consultative\n\n"
            return context
        
        # Add top recommendations
        context += "=== TOP PRODUCT RECOMMENDATIONS ===\n"
        all_recommendations = products + solutions
        
        for i, rec in enumerate(all_recommendations[:3], 1):
            context += f"\n{i}. {rec.get('name', 'Unknown Product')}\n"
            context += f"   Description: {rec.get('description', 'No description available')}\n"
            
            # Add price information carefully
            price = rec.get('price', 0)
            if price and price > 0:
                context += f"   Investment: ${price:,.2f}\n"
            
            # Add key features
            features = rec.get('features', [])
            if features:
                context += "   Key Features:\n"
                for feature in features[:3]:
                    context += f"   • {feature}\n"
            
            # Add benefits
            benefits = rec.get('benefits', [])
            if benefits:
                context += "   Business Benefits:\n"
                for benefit in benefits[:3]:
                    context += f"   • {benefit}\n"
            
            # Add why it's suitable
            if rec.get('suitability_score', 0) > 0:
                context += f"   Suitability: {rec.get('suitability_score', 0):.1%} match\n"
        
        # Add conversation guidance
        context += "\n=== RECOMMENDATION DISCUSSION APPROACH ===\n"
        context += "1. PRESENT: Start by presenting the top recommendation and why it fits\n"
        context += "2. EXPLAIN: Clearly explain the business value and benefits\n"
        context += "3. ENGAGE: Ask what they think, if they have questions, or want to see alternatives\n"
        context += "4. LISTEN: Pay attention to their feedback and concerns\n"
        context += "5. ADAPT: Adjust recommendations based on their input\n"
        context += "6. GUIDE: Help them understand the differences between options\n"
        context += "7. PATIENCE: Don't rush - let them digest the information\n\n"
        
        context += "=== IMPORTANT GUIDELINES ===\n"
        context += "• DO NOT automatically suggest quotes unless explicitly asked\n"
        context += "• DO focus on helping them understand their options\n"
        context += "• DO encourage questions and discussion\n"
        context += "• DO compare options if they ask\n"
        context += "• DO address concerns and objections patiently\n"
        context += "• DO ask for their feedback on the recommendations\n"
        context += "• ONLY mention formal quotes when they specifically request one\n"
        
        return context

    def _add_patient_recommendation_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        recommendation_context: str,
        pricing_inquiry: bool
    ) -> List[AIMessage]:
        """Add patient recommendation-focused context to messages"""
        
        # Get prompt from admin dashboard
        prompt_manager = get_prompt_manager()
        
        # Get product recommendation prompt
        system_prompt = prompt_manager.get_system_prompt("product_retriever")
        
        if not system_prompt:
            # Enhanced system prompt for patient recommendation stage
            system_prompt = """You are an expert B2B technology sales consultant in the RECOMMENDATION PRESENTATION stage. Your role is to present solutions thoughtfully and allow for discussion.

RECOMMENDATION STAGE OBJECTIVES:
1. 🎯 Present 2-3 top recommendations clearly with business justification
2. 💬 Encourage questions, feedback, and discussion about the options
3. 🔍 Help them understand the differences and benefits of each option
4. 🤝 Build confidence in the recommendations through explanation
5. ⏰ Be patient - don't rush to quotes unless explicitly requested
6. 📊 Compare options when asked and address concerns

CONVERSATION APPROACH:
• Start with your top recommendation and explain WHY it's the best fit
• Highlight the specific business benefits for their situation
• Ask for their thoughts and feedback on the recommendation
• Be ready to explain alternatives and comparisons
• Address any concerns or questions thoroughly
• Only mention formal quotes when they specifically ask for one

IMPORTANT GUIDELINES:
• NEVER rush to quote generation unless explicitly requested
• ALWAYS explain the business value, not just features
• ENCOURAGE questions and feedback about the recommendations
• BE PATIENT and let them process the information
• FOCUS on helping them make an informed decision
• ASK what they think about each recommendation"""
        
        # Add pricing guidance if there was a pricing inquiry
        if pricing_inquiry:
            system_prompt += """

PRICING INQUIRY DETECTED:
The customer showed interest in pricing/cost but didn't request a formal quote.
• Provide general price ranges to give context
• Focus on value and ROI, not just price
• Explain what's included in the investment
• Ask if they'd like a detailed quote after discussing options
• Don't automatically generate quotes - let them decide"""
        
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

    async def _analyze_conversation_intent(self, messages: List[AIMessage], customer_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the conversation to determine user intent"""
        try:
            # Get the last few messages for context
            recent_messages = messages[-3:] if len(messages) > 3 else messages
            message_text = " ".join([msg.content for msg in recent_messages])
            
            # Initialize intent analysis
            intent_analysis = {
                'intent_type': 'unknown',
                'confidence': 0.0,
                'key_phrases': [],
                'context': {}
            }
            
            # Check for selection intent
            selection_indicators = [
                "i want", "i'll take", "i'll get", "i'll buy", "i'll purchase",
                "i choose", "i select", "i prefer", "i like", "i want to get",
                "i want to buy", "i want to purchase", "i want to take",
                "i want to choose", "i want to select", "i want to prefer",
                "i want to like", "i want that", "i want this",
                "i'll go with", "i'll choose", "i'll select", "i'll prefer",
                "i'll like", "i'll take that", "i'll take this",
                "i'll get that", "i'll get this", "i'll buy that", "i'll buy this",
                "i'll purchase that", "i'll purchase this",
                "sounds good", "that works", "that's good", "that's perfect",
                "i'll take it", "i'll get it", "i'll buy it", "i'll purchase it",
                "let's go with", "let's take", "let's get", "let's buy",
                "let's purchase", "let's choose", "let's select"
            ]
            
            # Check for information request intent
            info_indicators = [
                "tell me more", "more info", "more details", "what about",
                "how does", "can you explain", "tell me about", "what is",
                "what are", "how is", "how are", "why", "when", "where",
                "which", "who", "what", "how"
            ]
            
            # Check for quote request intent
            quote_indicators = [
                "give me quote", "prepare quote", "generate quote", "send quote",
                "quote please", "need quote", "want quote", "quote for",
                "how much", "what's the price", "pricing", "cost"
            ]
            
            # Analyze message for different intents
            message_lower = message_text.lower()
            
            # Check for selection intent
            selection_matches = [indicator for indicator in selection_indicators if indicator in message_lower]
            if selection_matches:
                intent_analysis['intent_type'] = 'selection'
                intent_analysis['confidence'] = min(1.0, len(selection_matches) * 0.2)  # Scale confidence based on matches
                intent_analysis['key_phrases'] = selection_matches
            
            # Check for information request intent
            info_matches = [indicator for indicator in info_indicators if indicator in message_lower]
            if info_matches and not selection_matches:  # Only if not already a selection
                intent_analysis['intent_type'] = 'information'
                intent_analysis['confidence'] = min(1.0, len(info_matches) * 0.2)
                intent_analysis['key_phrases'] = info_matches
            
            # Check for quote request intent
            quote_matches = [indicator for indicator in quote_indicators if indicator in message_lower]
            if quote_matches:
                intent_analysis['intent_type'] = 'quote'
                intent_analysis['confidence'] = min(1.0, len(quote_matches) * 0.2)
                intent_analysis['key_phrases'] = quote_matches
            
            # Add context from customer_context if available
            if customer_context:
                intent_analysis['context'] = {
                    'requirements': customer_context.get('requirements', []),
                    'preferences': customer_context.get('preferences', {}),
                    'constraints': customer_context.get('constraints', {})
                }
            
            return intent_analysis
            
        except Exception as e:
            print(f"⚠️ Error analyzing conversation intent: {str(e)}")
            return {
                'intent_type': 'unknown',
                'confidence': 0.0,
                'key_phrases': [],
                'context': {}
            }

    def _extract_product_selection_keywords(self, message: str) -> Dict[str, List[str]]:
        """Extract product selection keywords from user message"""
        message_lower = message.lower()
        
        # Common brand names - general technology brands
        brands = []
        brand_keywords = [
            # Storage brands
            'synology', 'qnap', 'seagate', 'wd', 'western digital', 'toshiba', 'samsung', 'asustor', 'netgear', 'drobo',
            # Computer hardware brands
            'intel', 'amd', 'nvidia', 'asus', 'msi', 'gigabyte', 'evga', 'corsair', 'thermaltake',
            # Networking brands
            'cisco', 'ubiquiti', 'tp-link', 'linksys', 'd-link', 'netgear', 'aruba', 'juniper',
            # Server/enterprise brands
            'dell', 'hp', 'hpe', 'lenovo', 'ibm', 'supermicro', 'fujitsu',
            # Software/cloud brands
            'microsoft', 'vmware', 'citrix', 'oracle', 'sap', 'adobe', 'autodesk',
            # Audio/video brands
            'sony', 'panasonic', 'canon', 'nikon', 'blackmagic', 'avid',
            # Gaming brands
            'razer', 'logitech', 'steelseries', 'hyperx', 'alienware'
        ]
        for brand in brand_keywords:
            if brand in message_lower:
                brands.append(brand)
        
        # Product specifications - general patterns
        specifications = []
        
        # Enhanced specification patterns for general products
        spec_patterns = [
            r'(\d+)\s*(bay|bays)',              # Storage: "4 bay", "6 bays"
            r'(\d+)\s*(tb|gb|mb)',              # Storage: "6TB", "16GB", "512MB"
            r'(\d+)\s*(core|cores)',            # CPU: "8 core", "16 cores"
            r'(\d+)\s*(thread|threads)',        # CPU: "16 threads"
            r'(\d+\.?\d*)\s*(ghz|mhz)',        # Frequency: "3.5 GHz", "2400 MHz"
            r'(\d+)\s*(bit)',                   # Architecture: "64 bit"
            r'(\d+)\s*(port|ports)',            # Networking: "24 port", "48 ports"
            r'(\d+\.?\d*)\s*(gb|gbe)',          # Networking: "2.5 GbE", "10 GB"
            r'(\d+)\s*(inch|"|inches)',         # Display: "27 inch", "15.6\""
            r'(\d+)\s*x\s*(\d+)',               # Resolution: "1920x1080"
            r'(\d+)\s*(w|watt|watts)',          # Power: "650W", "80 watts"
            r'(\d+)\s*(rpm)',                   # Storage: "7200 RPM"
            r'raid\s*(\d+)',                    # Storage: "RAID 6"
            r'pcie?\s*(\d+\.?\d*)',             # PCIe: "PCIe 4.0"
            r'usb\s*(\d+\.?\d*)',               # USB: "USB 3.2"
            r'sata\s*(\d+)',                    # SATA: "SATA 3"
            r'ddr(\d+)',                        # Memory: "DDR4", "DDR5"
        ]
        
        import re
        for pattern in spec_patterns:
            matches = re.findall(pattern, message_lower)
            for match in matches:
                if isinstance(match, tuple):
                    specifications.append(' '.join(str(m) for m in match))
                else:
                    specifications.append(str(match))
        
        # Look for explicit model numbers in original case
        model_patterns = [
            # Storage models
            r'TS-\d+\w*',                       # QNAP models
            r'DS\d+\w*',                        # Synology models
            r'AS\d+\w*',                        # Asustor models
            # CPU models
            r'i[357]-\d+\w*',                   # Intel Core models
            r'Ryzen\s+\d+\s+\d+\w*',          # AMD Ryzen models
            r'Xeon\s+\w+\d+\w*',               # Intel Xeon models
            # GPU models
            r'RTX\s*\d+\w*',                    # NVIDIA RTX
            r'GTX\s*\d+\w*',                    # NVIDIA GTX
            r'RX\s*\d+\w*',                     # AMD Radeon RX
            # General product codes
            r'[A-Z]{2,4}-\d+\w*',              # General model patterns
        ]
        
        for pattern in model_patterns:
            matches = re.findall(pattern, message)  # Use original case
            specifications.extend(matches)
        
        # Look for common specification terms - general technology
        spec_terms = [
            # Storage
            'nas', 'ssd', 'hdd', 'nvme', 'sata', 'raid', 'backup', 'storage',
            # Computing
            'cpu', 'processor', 'gpu', 'graphics', 'memory', 'ram', 'motherboard',
            # Networking
            'ethernet', 'wifi', 'wireless', 'network', 'router', 'switch', 'firewall',
            # Server/enterprise
            'server', 'workstation', 'rack', 'blade', 'virtualization',
            # Display/audio
            'monitor', 'display', 'speaker', 'headset', 'microphone', 'webcam',
            # General
            'professional', 'enterprise', 'business', 'gaming', 'consumer'
        ]
        for term in spec_terms:
            if term in message_lower:
                specifications.append(term)
        
        # Enhanced product name detection - general patterns
        product_names = []
        
        # Look for complete product names (brand + model) - general patterns
        product_name_patterns = [
            # Storage products
            r'qnap\s+ts-\d+\w*',
            r'synology\s+ds\d+\w*',
            r'synology\s+diskstation\s+ds\d+\w*',
            r'asustor\s+as\d+\w*',
            r'seagate\s+ironwolf\s*pro?',
            r'wd\s+red\s*pro?',
            # CPU products
            r'intel\s+core\s+i[357]-\d+\w*',
            r'amd\s+ryzen\s+\d+\s+\d+\w*',
            r'intel\s+xeon\s+\w+\d+\w*',
            # GPU products
            r'nvidia\s+rtx\s*\d+\w*',
            r'nvidia\s+gtx\s*\d+\w*',
            r'amd\s+radeon\s+rx\s*\d+\w*',
            # General brand + model patterns
            r'[a-z]+\s+[a-z0-9-]+\s*\w*'
        ]
        
        for pattern in product_name_patterns:
            matches = re.findall(pattern, message_lower)
            product_names.extend(matches)
        
        return {
            'brands': brands,
            'specifications': specifications,
            'product_names': product_names
        }

    async def _generate_pitch_deck_for_quote(self, quote: Dict[str, Any]) -> None:
        """Generate pitch deck for the quote"""
        try:
            print("📊 Generating pitch deck for quote...")
            print(f"🔍 Debug - Input quote type: {type(quote)}")
            print(f"🔍 Debug - Input quote keys: {list(quote.keys()) if quote else 'None'}")
            
            # Import pitch deck service
            from services.pitch_deck_service import PitchDeckService
            print("🔍 Debug - PitchDeckService imported successfully")
            
            # Initialize pitch deck service
            pitch_deck_service = PitchDeckService()
            print("🔍 Debug - PitchDeckService initialized")
            
            # Get quote ID
            quote_id = quote.get('quote_id', 'unknown')
            print(f"🔍 Debug - Quote ID: {quote_id}")
            
            # Convert quote to string for processing
            quote_str = str(quote)
            print(f"🔍 Debug - Quote string length: {len(quote_str)}")
            print(f"🔍 Debug - Quote string preview: {quote_str[:200]}...")
            
            # Generate the pitch deck structure
            print("🔍 Debug - Calling extract_ppt_structure...")
            deck_structure = await pitch_deck_service.extract_ppt_structure(quote_str)
            print(f"🔍 Debug - Deck structure type: {type(deck_structure)}")
            print(f"🔍 Debug - Deck structure keys: {list(deck_structure.keys()) if isinstance(deck_structure, dict) else 'Not a dict'}")
            
            # Generate the pitch deck file
            deck_path = f"Data/pitch_decks/pitch_deck_{quote_id}.pptx"
            print(f"🔍 Debug - Target deck path: {deck_path}")
            
            # Ensure the directory exists
            import os
            pitch_deck_dir = "Data/pitch_decks"
            if not os.path.exists(pitch_deck_dir):
                print(f"🔍 Debug - Creating directory: {pitch_deck_dir}")
                os.makedirs(pitch_deck_dir, exist_ok=True)
            else:
                print(f"🔍 Debug - Directory already exists: {pitch_deck_dir}")
            
            print("🔍 Debug - Calling generate_ppt...")
            file_path = await pitch_deck_service.generate_ppt(deck_structure, deck_path)
            print(f"🔍 Debug - generate_ppt returned: {file_path}")
            print(f"🔍 Debug - File path type: {type(file_path)}")
            
            # Check if file was actually created
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"🔍 Debug - File created successfully: {file_path}")
                print(f"🔍 Debug - File size: {file_size} bytes")
                
                # Add pitch deck information to quote
                quote['pitch_deck_generated'] = True
                quote['pitch_deck_path'] = file_path
                quote['pitch_deck_url'] = f"/api/quotes/download-pitch-deck/{quote_id}"
                quote['pitch_deck_id'] = quote_id
                print(f"✅ Pitch deck generated successfully: {file_path}")
                print(f"🔍 Debug - Updated quote with pitch deck info")
            else:
                print("⚠️ Pitch deck generation returned no path or file doesn't exist")
                if file_path:
                    print(f"🔍 Debug - Returned path: {file_path}")
                    print(f"🔍 Debug - File exists: {os.path.exists(file_path)}")
                quote['pitch_deck_error'] = "Pitch deck generation failed - no path returned or file not created"
                quote['pitch_deck_generated'] = False
                
        except ImportError as e:
            print(f"❌ Debug - Import error: {str(e)}")
            quote['pitch_deck_error'] = f"Import error: {str(e)}"
            quote['pitch_deck_generated'] = False
            
        except Exception as e:
            print(f"❌ Pitch deck generation failed: {str(e)}")
            import traceback
            print(f"❌ Debug - Full traceback: {traceback.format_exc()}")
            quote['pitch_deck_error'] = f"Pitch deck generation error: {str(e)}"
            quote['pitch_deck_generated'] = False
    
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
