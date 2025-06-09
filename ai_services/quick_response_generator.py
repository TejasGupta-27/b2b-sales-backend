from typing import List, Dict, Any, Optional
from .base import AIProvider, AIMessage
import json
from pydantic import BaseModel, Field
from enum import Enum

class ResponseIntent(str, Enum):
    DISCOVERY = "discovery"
    BUDGET = "budget"
    TIMELINE = "timeline"
    TECHNICAL = "technical"
    COMPARISON = "comparison"
    PRICING = "pricing"
    SOCIAL_PROOF = "social_proof"
    IMPLEMENTATION = "implementation"
    CUSTOMIZATION = "customization"
    NEXT_STEPS = "next_steps"
    PRODUCT_INFO = "product_info"
    QUOTE = "quote"

class ResponseTemplate(BaseModel):
    """Model for a response template with fillable blanks"""
    template: str = Field(..., description="The template text with {placeholders}")
    placeholders: Dict[str, str] = Field(..., description="Description of each placeholder")
    example_values: Dict[str, str] = Field(default_factory=dict, description="Example values for placeholders")
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="How relevant this template is to the current context")

class QuickResponse(BaseModel):
    """Model for a single quick response"""
    text: str = Field(..., description="The actual response text")
    intent: ResponseIntent = Field(..., description="The purpose of the response")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    template: Optional[ResponseTemplate] = Field(None, description="Template with fillable blanks if applicable")
    
    class Config:
        use_enum_values = True

class QuickResponseList(BaseModel):
    """Model for a list of quick responses"""
    responses: List[QuickResponse] = Field(..., description="List of quick responses")

class QuickResponseGenerator:
    """Service to generate dynamic quick responses based on conversation context"""
    
    def __init__(self, base_provider: AIProvider):
        self.base_provider = base_provider
        
    async def generate_quick_responses(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None,
        num_responses: int = 3
    ) -> List[Dict[str, Any]]:
        """Generate quick response options based on conversation context"""
        
        # Extract conversation context
        conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
        
        # Check for meeting requests
        meeting_terms = ['meeting', 'call', 'schedule', 'demo', 'presentation']
        has_meeting_request = any(term in conversation_text.lower() for term in meeting_terms)
        
        # Generate responses based on context
        responses = []
        
        # Add discovery-focused responses
        if not has_meeting_request:
            responses.extend([
                {
                    'text': "Could you tell me more about your requirements?",
                    'intent': ResponseIntent.DISCOVERY,
                    'confidence': 0.5,
                    'template': ResponseTemplate(
                        template="I need information about {product_type} for {use_case}",
                        placeholders={
                            "product_type": "Type of product (e.g., servers, storage, networking)",
                            "use_case": "Your specific use case or application"
                        },
                        example_values={
                            "product_type": "GPU servers",
                            "use_case": "AI training"
                        },
                        context_relevance=0.5
                    ).dict()
                },
                {
                    'text': "What's your budget range?",
                    'intent': ResponseIntent.BUDGET,
                    'confidence': 0.5,
                    'template': ResponseTemplate(
                        template="My budget is {budget_amount} for {product_type}",
                        placeholders={
                            "budget_amount": "Your budget amount",
                            "product_type": "Type of product"
                        },
                        example_values={
                            "budget_amount": "$50,000",
                            "product_type": "server infrastructure"
                        },
                        context_relevance=0.5
                    ).dict()
                }
            ])
        
        # Add product-focused responses
        responses.extend([
            {
                'text': "Show me your best options",
                'intent': ResponseIntent.PRODUCT_INFO,
                'confidence': 0.6,
                'template': ResponseTemplate(
                    template="I'm interested in {product_category} for {use_case}",
                    placeholders={
                        "product_category": "Category of products",
                        "use_case": "Your specific use case"
                    },
                    example_values={
                        "product_category": "high-performance servers",
                        "use_case": "machine learning workloads"
                    },
                    context_relevance=0.6
                ).dict()
            },
            {
                'text': "Compare different options",
                'intent': ResponseIntent.COMPARISON,
                'confidence': 0.5,
                'template': ResponseTemplate(
                    template="Compare {product1} vs {product2}",
                    placeholders={
                        "product1": "First product to compare",
                        "product2": "Second product to compare"
                    },
                    example_values={
                        "product1": "RTX 4090 workstation",
                        "product2": "RTX 4080 workstation"
                    },
                    context_relevance=0.5
                ).dict()
            }
        ])
        
        # Add quote-focused response if appropriate
        if any(term in conversation_text.lower() for term in ['quote', 'price', 'cost']):
            responses.append({
                'text': "Get a detailed quote",
                'intent': ResponseIntent.QUOTE,
                'confidence': 0.7,
                'template': ResponseTemplate(
                    template="I need a quote for {product_specs}",
                    placeholders={
                        "product_specs": "Detailed product specifications"
                    },
                    example_values={
                        "product_specs": "2x RTX 4090, 128GB RAM, 2TB NVMe"
                    },
                    context_relevance=0.7
                ).dict()
            })
        
        # Sort by confidence and context relevance
        responses.sort(key=lambda x: (x['confidence'], x.get('template', {}).get('context_relevance', 0)), reverse=True)
        
        # Return top N responses
        return responses[:num_responses]
    
    def _build_conversation_context(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build context string from conversation and customer data"""
        
        context = "CONVERSATION HISTORY:\n"
        
        # Add last 3 messages for context
        recent_messages = messages[-3:] if len(messages) > 3 else messages
        for msg in recent_messages:
            context += f"{msg.role.upper()}: {msg.content}\n"
        
        # Add customer context if available
        if customer_context:
            context += "\nCUSTOMER CONTEXT:\n"
            for key, value in customer_context.items():
                context += f"{key}: {value}\n"
        
        return context
    
    def _get_fallback_responses(self) -> List[Dict[str, Any]]:
        """Get fallback responses when parsing fails"""
        return [
            {
                'text': "Could you tell me more about your requirements?",
                'intent': ResponseIntent.DISCOVERY,
                'confidence': 0.5,
                'template': ResponseTemplate(
                    template="I need information about {product_type} for {use_case}",
                    placeholders={
                        "product_type": "Type of product (e.g., servers, storage, networking)",
                        "use_case": "Your specific use case or application"
                    },
                    example_values={
                        "product_type": "GPU servers",
                        "use_case": "AI training"
                    },
                    context_relevance=0.5
                ).dict()
            },
            {
                'text': "What's your budget range?",
                'intent': ResponseIntent.BUDGET,
                'confidence': 0.5,
                'template': ResponseTemplate(
                    template="My budget is {budget_amount} for {product_type}",
                    placeholders={
                        "budget_amount": "Your budget amount",
                        "product_type": "Type of product"
                    },
                    example_values={
                        "budget_amount": "$50,000",
                        "product_type": "server infrastructure"
                    },
                    context_relevance=0.5
                ).dict()
            },
            {
                'text': "When do you need this by?",
                'intent': ResponseIntent.TIMELINE,
                'confidence': 0.5,
                'template': ResponseTemplate(
                    template="I need {product_type} by {timeline}",
                    placeholders={
                        "product_type": "Type of product",
                        "timeline": "Your required timeline"
                    },
                    example_values={
                        "product_type": "new servers",
                        "timeline": "end of Q2"
                    },
                    context_relevance=0.5
                ).dict()
            }
        ] 