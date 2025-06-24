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
        """Analyze conversation intent using Pydantic function calling"""
        
        conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages[-3:]])  # Last 3 messages
        
        analysis_prompt = f"""Analyze this conversation to determine the customer's intent and what actions should be taken.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT: {customer_context or 'None provided'}

Determine:
1. What type of intent this represents
2. Whether product retrieval is needed
3. Whether quote generation is needed
4. What information might be missing
5. Suggested follow-up questions

Be intelligent about this - don't retrieve products for every question, only when the customer is actually looking for product recommendations or solutions."""

        try:
            intent_analysis = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=analysis_prompt)],
                ConversationIntent
            )
            return intent_analysis
        except Exception as e:
            print(f"⚠️ Intent analysis failed: {e}")
            # Fallback to basic analysis
            return ConversationIntent(
                intent_type="general_chat",
                should_retrieve_products=False,
                should_generate_quote=False,
                confidence=0.5,
                reasoning="Fallback analysis due to error",
                missing_info=[],
                suggested_questions=[]
            )
    
    async def _generate_quote_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        product_data: Optional[Dict[str, Any]],
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate quote response with product recommendations"""
        
        print("💰 Generating quote response...")
        
        # Get quote-specific guidance from prompt manager
        quote_guidance = self.prompt_manager.get_prompt("conversational_agent", "quote_guidance", "")
        
        if not quote_guidance:
            quote_guidance = """The customer is asking for a quote. Provide a comprehensive response that includes:

1. Acknowledgment of their request
2. Summary of their requirements
3. Product recommendations (if available)
4. Next steps for quote generation
5. Any missing information needed

Be professional yet conversational."""
        
        # Build enhanced context
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Add product context if available
        if product_data and product_data.get('products'):
            product_context = self._build_product_context(product_data)
            enhanced_messages.append(AIMessage(role="system", content=product_context))
        
        # Add quote guidance
        enhanced_messages.append(AIMessage(role="system", content=quote_guidance))
        
        # Add missing information context
        if intent_analysis.missing_info:
            missing_info_context = f"""
Missing Information Needed:
{chr(10).join([f"- {info}" for info in intent_analysis.missing_info])}

Ask for this information to provide an accurate quote.
"""
            enhanced_messages.append(AIMessage(role="system", content=missing_info_context))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'quote_request': True,
            'missing_info': intent_analysis.missing_info,
            'suggested_questions': intent_analysis.suggested_questions
        })
        
        return response
    
    async def _generate_product_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        product_data: Dict[str, Any],
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate response with product recommendations"""
        
        print("📦 Generating product response...")
        
        # Get product-specific guidance from prompt manager
        product_guidance = self.prompt_manager.get_prompt("conversational_agent", "product_guidance", "")
        
        if not product_guidance:
            product_guidance = """The customer is asking about products. Provide a helpful response that includes:

1. Acknowledgment of their inquiry
2. Relevant product recommendations
3. Key features and benefits
4. Next steps or questions

Be informative and helpful, not pushy."""
        
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
            'solutions_recommended': len(product_data.get('solutions', []))
        })
        
        return response
    
    async def _generate_general_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate general conversational response"""
        
        print("💬 Generating general response...")
        
        # Build conversational context using prompt manager
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Add suggested questions if available
        if intent_analysis.suggested_questions:
            questions_context = f"""
Suggested follow-up questions to ask:
{chr(10).join([f"- {question}" for question in intent_analysis.suggested_questions])}

Consider incorporating these questions naturally into your response if appropriate.
"""
            enhanced_messages.append(AIMessage(role="system", content=questions_context))
        
        # Generate response
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'general_chat': True,
            'suggested_questions': intent_analysis.suggested_questions
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