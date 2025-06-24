import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from .base import AIProvider, AIMessage, AIResponse
from services.prompt_manager import get_prompt_manager
from config import settings

class SimpleConversationalAgent(AIProvider):
    """Simple, conversational B2B sales agent focused on natural dialogue with dynamic configuration"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.conversation_memory = {}
        self.prompt_manager = get_prompt_manager()
        
    @property
    def provider_name(self) -> str:
        return f"simple_conversational_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate natural, conversational responses using dynamic configuration from prompt manager"""
        
        # Build conversational context using prompt manager
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Generate response
        response = await self.base_provider.generate_response(enhanced_messages)
        
        # Add conversational metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'agent_type': 'simple_conversational',
            'conversation_style': 'natural',
            'response_time': datetime.now().isoformat(),
            'config_source': 'prompt_manager'
        })
        
        return response
    
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
    
    async def generate_quote_request_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> AIResponse:
        """Handle quote requests naturally using prompt manager configuration"""
        
        # Get quote-specific guidance from prompt manager
        quote_guidance = self.prompt_manager.get_prompt("conversational_agent", "quote_guidance", "")
        
        if not quote_guidance:
            quote_guidance = """The customer is asking for a quote. Respond naturally and helpfully:

1. Acknowledge their request warmly
2. Ask for any missing details (budget, timeline, specific requirements)
3. Let them know you'll prepare a detailed quote
4. Ask if they'd like to discuss any specific aspects while you work on it

Keep it conversational and helpful - don't sound like a robot!"""
        
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        enhanced_messages.append(AIMessage(role="system", content=quote_guidance))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'quote_request': True,
            'agent_type': 'simple_conversational',
            'config_source': 'prompt_manager'
        })
        
        return response
    
    async def generate_product_inquiry_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> AIResponse:
        """Handle product inquiries naturally using prompt manager configuration"""
        
        # Get product-specific guidance from prompt manager
        product_guidance = self.prompt_manager.get_prompt("conversational_agent", "product_guidance", "")
        
        if not product_guidance:
            product_guidance = """The customer is asking about products. Respond naturally:

1. Show enthusiasm about helping them find the right solution
2. Ask about their specific needs and use cases
3. Provide helpful information about relevant options
4. Ask follow-up questions to better understand their requirements
5. Offer to provide more detailed information or quotes when ready

Be conversational and genuinely helpful!"""
        
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        enhanced_messages.append(AIMessage(role="system", content=product_guidance))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'product_inquiry': True,
            'agent_type': 'simple_conversational',
            'config_source': 'prompt_manager'
        })
        
        return response 