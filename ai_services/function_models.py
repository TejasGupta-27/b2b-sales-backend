from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

class RequirementExtraction(BaseModel):
    """Model for extracting customer requirements from conversation"""
    technical_requirements: List[str] = Field(description="List of technical requirements mentioned")
    business_requirements: List[str] = Field(description="List of business requirements mentioned")
    budget_range: Optional[str] = Field(description="Budget range if mentioned")
    timeline: Optional[str] = Field(description="Timeline if mentioned")
    company_size: Optional[str] = Field(description="Company size if mentioned")
    industry: Optional[str] = Field(description="Industry if mentioned")
    use_case: Optional[str] = Field(description="Primary use case described")
    pain_points: List[str] = Field(description="Pain points mentioned")
    decision_makers: List[str] = Field(description="Decision makers identified")
    
class ConversationStage(str, Enum):
    INITIAL_DISCOVERY = "initial_discovery"
    INITIAL_CONTACT = "initial_contact"
    DEEP_DISCOVERY = "deep_discovery"
    SOLUTION_PRESENTATION = "solution_presentation"
    QUOTE_READY = "quote_ready"
    CLOSING = "closing"
    UNKNOWN = "unknown"

class ConversationAnalysis(BaseModel):
    """Model for conversation flow analysis"""
    current_stage: ConversationStage = Field(description="Current conversation stage")
    business_context_score: int = Field(description="Score 0-100 for business context understanding", ge=0, le=100)
    technical_requirements_score: int = Field(description="Score 0-100 for technical requirements clarity", ge=0, le=100)
    decision_readiness_score: int = Field(description="Score 0-100 for decision readiness", ge=0, le=100)
    quote_ready: bool = Field(description="Whether customer is ready for a quote")
    should_generate_quote: bool = Field(description="Whether to generate a quote now")
    missing_information: List[str] = Field(description="Information still needed")
    next_questions: List[str] = Field(description="Suggested next questions to ask")
    confidence_level: float = Field(description="Confidence in analysis 0-1", ge=0, le=1)

class ProductRecommendation(BaseModel):
    """Model for product recommendations"""
    product_id: str = Field(description="Product identifier")
    name: str = Field(description="Product name")
    match_score: float = Field(description="How well product matches requirements 0-1", ge=0, le=1)
    why_recommended: str = Field(description="Explanation of why this product is recommended")
    considerations: List[str] = Field(description="Important considerations for this product")

class ProductAnalysis(BaseModel):
    """Model for product analysis and recommendations"""
    recommended_approach: str = Field(description="Recommended approach: products, solutions, or hybrid")
    top_recommendations: List[ProductRecommendation] = Field(description="Top product recommendations")
    missing_requirements: List[str] = Field(description="Requirements that couldn't be addressed")
    alternative_options: List[str] = Field(description="Alternative considerations")
    total_estimated_value: float = Field(description="Total estimated value")

class QuoteLineItem(BaseModel):
    """Model for quote line items"""
    name: str = Field(description="Item name")
    description: str = Field(description="Item description")
    quantity: int = Field(description="Quantity", ge=1)
    unit_price: float = Field(description="Unit price", ge=0)
    total_price: float = Field(description="Total price for this line item", ge=0)
    specifications: Dict[str, Any] = Field(description="Technical specifications", default_factory=dict)

class CustomerInfo(BaseModel):
    """Model for customer information"""
    company: Optional[str] = Field(description="Company name")
    contact: Optional[str] = Field(description="Contact person name")
    email: Optional[str] = Field(description="Email address")
    phone: Optional[str] = Field(description="Phone number")
    industry: Optional[str] = Field(description="Industry sector")

class QuoteData(BaseModel):
    """Model for quote generation"""
    customer_info: CustomerInfo = Field(description="Customer information")
    line_items: List[QuoteLineItem] = Field(description="Quote line items")
    subtotal: float = Field(description="Subtotal amount", ge=0)
    tax_rate: float = Field(description="Tax rate as decimal", ge=0, le=1)
    tax_amount: float = Field(description="Tax amount", ge=0)
    total: float = Field(description="Total amount", ge=0)
    currency: str = Field(description="Currency code", default="USD")
    business_context: Dict[str, Any] = Field(description="Business context and requirements", default_factory=dict) 