import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from pydantic import BaseModel, Field

from .base import AIProvider, AIMessage, AIResponse
from services.prompt_manager import get_prompt_manager
from .hybrid_product_retriever_agent import HybridProductRetrieverAgent
from .quote_generation_agent import QuoteGenerationAgent
from config import settings

class ConversationIntent(BaseModel):
    """Pydantic model for analyzing conversation intent"""
    intent_type: str = Field(description="Type of intent: 'product_inquiry', 'quote_request', 'general_chat', 'technical_question', 'pricing_inquiry'")
    should_retrieve_products: bool = Field(description="Whether product retrieval is needed")
    should_generate_quote: bool = Field(description="Whether quote generation is needed")
    confidence: float = Field(description="Confidence in the intent analysis (0.0 to 1.0)")
    reasoning: str = Field(description="Reasoning for the decision")
    missing_info: List[str] = Field(description="Missing information needed for product retrieval or quote generation")
    suggested_questions: List[str] = Field(description="Suggested follow-up questions")

class SimpleConversationalAgent(AIProvider):
    """Simple, conversational B2B sales agent with intelligent product retrieval and quote generation"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.conversation_memory = {}
        self.prompt_manager = get_prompt_manager()
        
        # Initialize hybrid product retriever if configured
        self.hybrid_retriever = None
        if settings.use_hybrid_retriever and settings.azure_embedding_endpoint and settings.azure_embedding_api_key:
            try:
                self.hybrid_retriever = HybridProductRetrieverAgent(
                    base_provider=base_provider,
                    azure_embedding_endpoint=settings.azure_embedding_endpoint,
                    azure_embedding_key=settings.azure_embedding_api_key
                )
                print("✅ Hybrid Product Retriever initialized for SimpleConversationalAgent")
            except Exception as e:
                print(f"⚠️ Failed to initialize hybrid retriever: {e}")
        
        # Initialize quote generation agent
        self.quote_agent = QuoteGenerationAgent(base_provider)
        print("✅ Quote Generation Agent initialized for SimpleConversationalAgent")
        
    @property
    def provider_name(self) -> str:
        return f"simple_conversational_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def initialize(self):
        """Initialize the agent and its components"""
        try:
            if self.hybrid_retriever:
                await self.hybrid_retriever.initialize()
            print("✅ SimpleConversationalAgent initialized successfully")
        except Exception as e:
            print(f"⚠️ SimpleConversationalAgent initialization warning: {e}")
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate intelligent responses with product retrieval and quote generation capabilities"""
        
        print("🤖 SimpleConversationalAgent: Analyzing conversation intent...")
        
        # Step 1: Analyze conversation intent using Pydantic function calling
        intent_analysis = await self._analyze_conversation_intent(messages, customer_context)
        
        print(f"🎯 Intent Analysis:")
        print(f"   Intent: {intent_analysis.intent_type}")
        print(f"   Retrieve Products: {intent_analysis.should_retrieve_products}")
        print(f"   Generate Quote: {intent_analysis.should_generate_quote}")
        print(f"   Confidence: {intent_analysis.confidence:.1%}")
        print(f"   Reasoning: {intent_analysis.reasoning}")
        
        # Step 2: Retrieve products if needed
        product_data = None
        if intent_analysis.should_retrieve_products and self.hybrid_retriever:
            print("🔍 Retrieving products using hybrid search...")
            try:
                product_data = await self.hybrid_retriever.retrieve_products(messages, customer_context)
                print(f"✅ Retrieved {len(product_data.get('products', []))} products, {len(product_data.get('solutions', []))} solutions")
            except Exception as e:
                print(f"⚠️ Product retrieval failed: {e}")
                product_data = {'products': [], 'solutions': [], 'error': str(e)}
        
        # Step 3: Generate appropriate response based on intent
        if intent_analysis.should_generate_quote:
            response = await self._generate_quote_response(messages, customer_context, product_data, intent_analysis)
        elif intent_analysis.should_retrieve_products and product_data:
            response = await self._generate_product_response(messages, customer_context, product_data, intent_analysis)
        else:
            response = await self._generate_general_response(messages, customer_context, intent_analysis)
        
        # Step 4: Add metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'agent_type': 'simple_conversational',
            'conversation_style': 'natural',
            'response_time': datetime.now().isoformat(),
            'config_source': 'prompt_manager',
            'intent_analysis': intent_analysis.model_dump(),
            'product_retrieved': intent_analysis.should_retrieve_products,
            'quote_generated': intent_analysis.should_generate_quote,
            'hybrid_retriever_used': self.hybrid_retriever is not None
        })
        
        if product_data:
            response.metadata['product_data'] = {
                'total_products': len(product_data.get('products', [])),
                'total_solutions': len(product_data.get('solutions', [])),
                'retrieval_method': product_data.get('retrieval_method', 'none'),
                'fusion_method': product_data.get('fusion_method', 'none'),
                'retrieval_confidence': product_data.get('retrieval_confidence', 0.0)
            }
        
        return response
    
    async def _analyze_conversation_intent(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> ConversationIntent:
        """Analyze conversation intent using Pydantic function calling - focus on discovery first"""
        
        conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages[-3:]])  # Last 3 messages
        
        analysis_prompt = f"""Analyze this conversation to determine the customer's intent and what actions should be taken.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT: {customer_context or 'None provided'}

IMPORTANT GUIDELINES:
1. **Discovery First**: Always prioritize gathering requirements over product recommendations
2. **Product Retrieval**: Only retrieve products if the customer has provided substantial requirements AND explicitly asks for recommendations
3. **Quote Generation**: Only generate quotes if the customer explicitly requests a quote AND has provided detailed requirements
4. **Be Conservative**: It's better to ask more questions than to make premature recommendations

Determine:
1. What type of intent this represents
2. Whether product retrieval is needed (be very conservative - only if customer has provided detailed requirements AND asks for recommendations)
3. Whether quote generation is needed (only if explicitly requested with detailed requirements)
4. What information is missing (focus on gathering requirements first)
5. Suggested follow-up questions to gather more information

Examples of when NOT to retrieve products:
- Customer mentions a product category but no specific requirements
- Customer asks general questions about technology
- Customer hasn't provided budget, timeline, or specific use cases
- Customer is still in early discovery phase

Examples of when to retrieve products:
- Customer has provided detailed requirements (budget, timeline, specific needs) AND explicitly asks for recommendations
- Customer has described their use case in detail AND asks for product suggestions
- Customer is ready for solution presentation phase

Be very conservative about product retrieval - it's better to gather more information first."""

        try:
            intent_analysis = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=analysis_prompt)],
                ConversationIntent
            )
            return intent_analysis
        except Exception as e:
            print(f"⚠️ Intent analysis failed: {e}")
            # Fallback to conservative analysis
            return ConversationIntent(
                intent_type="discovery",
                should_retrieve_products=False,
                should_generate_quote=False,
                confidence=0.5,
                reasoning="Fallback analysis - focusing on discovery",
                missing_info=["specific requirements", "budget", "timeline", "use case details"],
                suggested_questions=["What specific problem are you trying to solve?", "What's your budget range?", "When do you need this solution?"]
            )
    
    async def _generate_quote_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        product_data: Optional[Dict[str, Any]],
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate quote response with focus on gathering missing information first"""
        
        print("💰 Generating quote response...")
        
        # Get quote-specific guidance from prompt manager
        quote_guidance = self.prompt_manager.get_prompt("conversational_agent", "quote_guidance", "")
        
        if not quote_guidance:
            quote_guidance = """The customer is asking for a quote. However, before providing a detailed quote, ensure you have all necessary information.

APPROACH:
1. Acknowledge their quote request warmly
2. Check if you have all required information (budget, timeline, specific requirements, use case details)
3. If information is missing, ask for it first before proceeding with quote generation
4. Only proceed with quote generation if you have comprehensive requirements
5. If you have the information, provide a summary and next steps

Be professional yet conversational. It's better to gather complete information than to provide an inaccurate quote."""
        
        # Build enhanced context
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Add missing information context - prioritize this
        if intent_analysis.missing_info:
            missing_info_context = f"""
IMPORTANT: Before generating a quote, we need to gather more information.

Missing Information:
{chr(10).join([f"- {info}" for info in intent_analysis.missing_info])}

Focus on gathering this information first. Only proceed with quote generation if you have comprehensive requirements.
"""
            enhanced_messages.append(AIMessage(role="system", content=missing_info_context))
        
        # Add product context if available (but don't prioritize it)
        if product_data and product_data.get('products'):
            product_context = self._build_product_context(product_data)
            enhanced_messages.append(AIMessage(role="system", content=product_context))
        
        # Add quote guidance
        enhanced_messages.append(AIMessage(role="system", content=quote_guidance))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'quote_request': True,
            'missing_info': intent_analysis.missing_info,
            'suggested_questions': intent_analysis.suggested_questions,
            'requirements_complete': len(intent_analysis.missing_info) == 0
        })
        
        return response
    
    async def _generate_product_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        product_data: Dict[str, Any],
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate response with product recommendations - only if requirements are complete"""
        
        print("📦 Generating product response...")
        
        # Get product-specific guidance from prompt manager
        product_guidance = self.prompt_manager.get_prompt("conversational_agent", "product_guidance", "")
        
        if not product_guidance:
            product_guidance = """The customer is asking about products and you have sufficient requirements to make recommendations.

APPROACH:
1. Acknowledge their inquiry and the requirements they've provided
2. Present relevant product recommendations with clear reasoning
3. Explain why these products fit their specific needs
4. Ask if they'd like more details about any specific product
5. Suggest next steps (demo, quote, etc.)

Be informative and helpful, but also be ready to gather more information if needed."""
        
        # Build enhanced context
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Add product context
        product_context = self._build_product_context(product_data)
        enhanced_messages.append(AIMessage(role="system", content=product_context))
        
        # Add product guidance
        enhanced_messages.append(AIMessage(role="system", content=product_guidance))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'product_inquiry': True,
            'products_recommended': len(product_data.get('products', [])),
            'solutions_recommended': len(product_data.get('solutions', [])),
            'requirements_complete': len(intent_analysis.missing_info) == 0
        })
        
        return response
    
    async def _generate_general_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate general conversational response with focus on discovery"""
        
        print("💬 Generating general response with discovery focus...")
        
        # Build conversational context using prompt manager
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Add discovery-focused guidance
        discovery_guidance = """You are in discovery mode. Your primary goal is to understand the customer's needs and gather requirements.

APPROACH:
1. Be conversational and helpful
2. Ask follow-up questions to understand their specific needs
3. Gather information about their business context, challenges, and goals
4. Don't jump to product recommendations unless they explicitly ask AND you have sufficient information
5. Focus on understanding their problem before suggesting solutions

Remember: It's better to ask one more question than to make premature recommendations."""
        
        enhanced_messages.append(AIMessage(role="system", content=discovery_guidance))
        
        # Add suggested questions if available
        if intent_analysis.suggested_questions:
            questions_context = f"""
Suggested follow-up questions to gather more information:
{chr(10).join([f"- {question}" for question in intent_analysis.suggested_questions])}

Incorporate these questions naturally into your response to better understand their needs.
"""
            enhanced_messages.append(AIMessage(role="system", content=questions_context))
        
        # Generate response
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'general_chat': True,
            'discovery_mode': True,
            'suggested_questions': intent_analysis.suggested_questions,
            'missing_info': intent_analysis.missing_info
        })
        
        return response
    
    def _build_product_context(self, product_data: Dict[str, Any]) -> str:
        """Build context from product data"""
        
        products = product_data.get('products', [])
        solutions = product_data.get('solutions', [])
        
        context = f"""
Available Product Recommendations:
Total Products: {len(products)}
Total Solutions: {len(solutions)}
Retrieval Method: {product_data.get('retrieval_method', 'unknown')}
Fusion Method: {product_data.get('fusion_method', 'unknown')}
Confidence: {product_data.get('retrieval_confidence', 0):.1%}

"""
        
        if products:
            context += "Top Products:\n"
            for i, product in enumerate(products[:5]):  # Top 5 products
                context += f"{i+1}. {product.get('name', 'Unknown')} - ${product.get('price', 0):,.2f}\n"
                context += f"   Category: {product.get('category', 'Unknown')}\n"
                context += f"   Description: {product.get('description', 'No description')[:100]}...\n\n"
        
        if solutions:
            context += "Available Solutions:\n"
            for i, solution in enumerate(solutions[:3]):  # Top 3 solutions
                context += f"{i+1}. {solution.get('name', 'Unknown')}\n"
                context += f"   Use Case: {solution.get('use_case', 'No use case')}\n"
                context += f"   Total Price: ${solution.get('total_price', 0):,.2f}\n\n"
        
        return context
    
    def _build_conversational_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> List[AIMessage]:
        """Build context for natural conversation using dynamic configuration from prompt manager"""
        
        # Get main system prompt from prompt manager
        system_prompt = self.prompt_manager.get_system_prompt("conversational_agent")
        
        # Add discovery-focused system guidance
        discovery_system_guidance = """

IMPORTANT SALES APPROACH:
You are a consultative B2B sales assistant. Your primary goal is to understand the customer's needs through discovery before making any recommendations.

DISCOVERY-FIRST PRINCIPLES:
1. **Ask Questions First**: Always gather requirements before suggesting solutions
2. **Understand the Problem**: Focus on understanding their challenges and goals
3. **Gather Context**: Learn about their business, budget, timeline, and specific needs
4. **Be Patient**: Don't rush to product recommendations
5. **Build Trust**: Show genuine interest in their success

WHEN TO RECOMMEND PRODUCTS:
- Only after you have comprehensive requirements (budget, timeline, specific needs, use case details)
- Only when the customer explicitly asks for recommendations
- Only when you understand their problem well enough to suggest relevant solutions

WHEN TO GATHER MORE INFORMATION:
- Customer mentions a product category but no specific requirements
- Customer asks general questions about technology
- Customer hasn't provided budget, timeline, or specific use cases
- Customer is still in early discovery phase

Remember: It's better to ask one more question than to make premature recommendations that don't fit their needs."""

        system_prompt = discovery_system_guidance + system_prompt
        
        # Get conversational configuration
        config = self.prompt_manager.get_conversational_config()
        
        # Add personality context if available
        if config.get("personality"):
            personality = config["personality"]
            name = personality.get("name", "Alex")
            role = personality.get("role", "B2B Sales Consultant")
            traits = ", ".join(personality.get("personality_traits", []))
            communication_style = personality.get("communication_style", "conversational")
            tone = personality.get("tone", "warm_and_professional")
            
            personality_context = f"""
Agent Identity:
- Name: {name}
- Role: {role}
- Personality: {traits}
- Communication Style: {communication_style}
- Tone: {tone}

"""
            system_prompt = personality_context + system_prompt
        
        # Add industry-specific context if available
        if customer_context and customer_context.get('industry'):
            industry_context = self._get_industry_context(customer_context['industry'], config)
            if industry_context:
                system_prompt += industry_context
        
        # Add customer context if available
        if customer_context:
            customer_info = f"""
Customer Context:
- Company: {customer_context.get('company_name', 'Unknown')}
- Industry: {customer_context.get('industry', 'Business')}
- Contact: {customer_context.get('contact_name', 'Customer')}
- Company Size: {customer_context.get('company_size', 'Unknown')}
- Budget Range: {customer_context.get('budget_range', 'Unknown')}
- Timeline: {customer_context.get('timeline', 'Unknown')}
"""
            system_prompt += customer_info
        
        # Add response guidelines if available
        if config.get("response_guidelines"):
            guidelines_context = self._get_response_guidelines_context(config["response_guidelines"])
            system_prompt += guidelines_context
        
        # Create system message
        system_message = AIMessage(role="system", content=system_prompt)
        
        # Return enhanced messages
        return [system_message] + messages
    
    def _get_industry_context(self, industry: str, config: Dict[str, Any]) -> str:
        """Get industry-specific context from configuration"""
        industry_responses = config.get("industry_responses", {})
        
        if industry and industry.lower() in industry_responses:
            industry_config = industry_responses[industry.lower()]
            focus_areas = ", ".join(industry_config.get("focus_areas", []))
            concerns = ", ".join(industry_config.get("common_concerns", []))
            
            return f"""
Industry Context ({industry}):
- Focus areas: {focus_areas}
- Common concerns: {concerns}
- Tailor your responses to address these industry-specific needs and concerns.
"""
        return ""
    
    def _get_response_guidelines_context(self, response_guidelines: Dict[str, Any]) -> str:
        """Get response guidelines context"""
        guidelines_text = """

How to handle different types of requests:

"""
        
        for request_type, guidance in response_guidelines.items():
            approach = guidance.get("approach", "natural_help")
            elements = guidance.get("key_elements", [])
            
            guidelines_text += f"""
{request_type.replace('_', ' ').title()}:
- Approach: {approach.replace('_', ' ').title()}
- Key elements: {', '.join(elements)}
"""
        
        guidelines_text += """
Remember: You're having a conversation with a real person, not following a rigid sales script. Be human, be helpful, and let the conversation flow naturally. Adapt your response style based on the customer's tone and the type of question they're asking."""
        
        return guidelines_text
    
    async def generate_quote(self, quote_request: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a detailed quote using the QuoteGenerationAgent"""
        
        print("💰 SimpleConversationalAgent: Generating quote using QuoteGenerationAgent...")
        
        try:
            # Extract conversation messages and customer context
            conversation_messages = quote_request.get('conversation_messages', [])
            customer_context = quote_request.get('customer_context', {})
            
            # If no conversation messages provided, create a basic one from the request
            if not conversation_messages:
                requirements = quote_request.get('requirements', {})
                customer_info = quote_request.get('customer_info', {})
                
                # Create a basic conversation message from the requirements
                basic_message = f"Customer needs: {requirements.get('description', 'Business technology solution')}"
                if customer_info.get('company_name'):
                    basic_message += f" for {customer_info['company_name']}"
                if customer_info.get('industry'):
                    basic_message += f" in {customer_info['industry']} industry"
                
                conversation_messages = [AIMessage(role="user", content=basic_message)]
            
            # Use the QuoteGenerationAgent to generate the quote
            quote = await self.quote_agent.generate_quote_from_conversation(
                conversation_messages=conversation_messages,
                customer_context=customer_context
            )
            
            if quote:
                # Add metadata to indicate it was generated through SimpleConversationalAgent
                quote['generated_by'] = 'SimpleConversationalAgent_with_QuoteGenerationAgent'
                quote['hybrid_retriever_available'] = self.hybrid_retriever is not None
                print(f"✅ Quote generated successfully: {quote.get('quote_number', 'Unknown')}")
                return quote
            else:
                print("❌ Quote generation failed - no quote returned")
                return {
                    'error': 'Quote generation failed - no quote returned',
                    'quote_id': f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'generated_at': datetime.now().isoformat(),
                    'quote_text': 'Quote generation failed - no quote returned'
                }
            
        except Exception as e:
            print(f"❌ Quote generation failed: {e}")
            return {
                'error': str(e),
                'quote_id': f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'generated_at': datetime.now().isoformat(),
                'quote_text': f"Quote generation failed: {str(e)}"
            } 