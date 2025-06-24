import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from .base import AIProvider, AIMessage, AIResponse
from .conversational_config import get_personality_prompt, get_industry_context, get_response_guidance
from config import settings

class SimpleConversationalAgent(AIProvider):
    """Simple, conversational B2B sales agent focused on natural dialogue"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.conversation_memory = {}
        
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
        """Generate natural, conversational responses using dynamic configuration"""
        
        # Build conversational context
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Generate response
        response = await self.base_provider.generate_response(enhanced_messages)
        
        # Add conversational metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'agent_type': 'simple_conversational',
            'conversation_style': 'natural',
            'response_time': datetime.now().isoformat()
        })
        
        return response
    
    def _build_conversational_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> List[AIMessage]:
        """Build context for natural conversation using dynamic configuration"""
        
        # Get dynamic personality prompt
        system_prompt = get_personality_prompt()
        
        # Add industry-specific context if available
        if customer_context and customer_context.get('industry'):
            industry_context = get_industry_context(customer_context['industry'])
            system_prompt += industry_context
        
        # Add customer context if available
        if customer_context:
            customer_info = f"""
Customer Context:
- Company: {customer_context.get('company_name', 'Unknown')}
- Industry: {customer_context.get('industry', 'Business')}
- Contact: {customer_context.get('contact_name', 'Customer')}
"""
            system_prompt += customer_info
        
        # Add general conversation guidance
        system_prompt += """

How to handle different types of requests:

1. **Product Inquiries**: When customers ask about products, solutions, or recommendations:
   - Show enthusiasm about helping them find the right solution
   - Ask about their specific needs and use cases
   - Provide helpful information about relevant options
   - Ask follow-up questions to better understand their requirements
   - Offer to provide more detailed information or quotes when ready

2. **Quote Requests**: When customers ask about pricing, quotes, or costs:
   - Acknowledge their request warmly
   - Ask for any missing details (budget, timeline, specific requirements)
   - Let them know you'll prepare a detailed quote
   - Ask if they'd like to discuss any specific aspects while you work on it
   - Keep it conversational and helpful

3. **General Questions**: For any other questions:
   - Respond naturally and helpfully
   - Ask clarifying questions when needed
   - Provide relevant information
   - Guide the conversation toward understanding their needs

4. **Technical Questions**: When customers ask technical questions:
   - Provide clear, understandable explanations
   - Avoid jargon unless they're technical
   - Offer to provide more detailed technical information if needed
   - Connect technical features to business benefits

Remember: You're having a conversation with a real person, not following a rigid sales script. Be human, be helpful, and let the conversation flow naturally. Adapt your response style based on the customer's tone and the type of question they're asking."""
        
        # Create system message
        system_message = AIMessage(role="system", content=system_prompt)
        
        # Return enhanced messages
        return [system_message] + messages
    
    async def generate_quote_request_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> AIResponse:
        """Handle quote requests naturally"""
        
        quote_prompt = """The customer is asking for a quote. Respond naturally and helpfully:

1. Acknowledge their request warmly
2. Ask for any missing details (budget, timeline, specific requirements)
3. Let them know you'll prepare a detailed quote
4. Ask if they'd like to discuss any specific aspects while you work on it

Keep it conversational and helpful - don't sound like a robot!"""
        
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        enhanced_messages.append(AIMessage(role="system", content=quote_prompt))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'quote_request': True,
            'agent_type': 'simple_conversational'
        })
        
        return response
    
    async def generate_product_inquiry_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> AIResponse:
        """Handle product inquiries naturally"""
        
        product_prompt = """The customer is asking about products. Respond naturally:

1. Show enthusiasm about helping them find the right solution
2. Ask about their specific needs and use cases
3. Provide helpful information about relevant options
4. Ask follow-up questions to better understand their requirements
5. Offer to provide more detailed information or quotes when ready

Be conversational and genuinely helpful!"""
        
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        enhanced_messages.append(AIMessage(role="system", content=product_prompt))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'product_inquiry': True,
            'agent_type': 'simple_conversational'
        })
        
        return response 