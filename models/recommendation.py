from pydantic import BaseModel, validator, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

class ProductRecommendation(BaseModel):
    product_id: str
    name: str
    description: str
    price: float
    features: List[str]
    benefits: List[str]
    suitability_score: float
    customization_options: Optional[Dict[str, Any]] = None

class RecommendationSet(BaseModel):
    id: str
    lead_id: str
    recommendations: Union[List[ProductRecommendation], List[Dict[str, Any]]]
    created_at: datetime
    selected_recommendations: List[str] = Field(default_factory=list)
    selection_timestamps: Dict[str, datetime] = Field(default_factory=dict)
    reasoning: str
    next_steps: List[str]
    conversation_state: Optional[Dict[str, Any]] = None
    current_stage: str = "solution_presentation"
    quote_data: Optional[Dict[str, Any]] = None
    quote_generated_at: Optional[datetime] = None
    
    # New fields for improved conversation flow
    recommendation_stage: str = "presentation"  # presentation, discussion, feedback, selection
    customer_feedback: Optional[Dict[str, Any]] = None
    pricing_inquiries: List[str] = Field(default_factory=list)
    explicit_quote_requested: bool = False
    discussion_history: List[Dict[str, Any]] = Field(default_factory=list)
    alternatives_shown: List[str] = Field(default_factory=list)
    comparison_requests: List[Dict[str, Any]] = Field(default_factory=list)
    
    @validator('recommendations', pre=True)
    def validate_recommendations(cls, v):
        """Handle both dict and ProductRecommendation objects"""
        if not v:
            return []
        
        # If it's already a list of dicts (from database), return as is
        if isinstance(v, list) and len(v) > 0:
            if isinstance(v[0], dict):
                return v
            elif hasattr(v[0], 'dict'):  # ProductRecommendation objects
                return [item.dict() if hasattr(item, 'dict') else item for item in v]
        
        return v
    
    def add_customer_feedback(self, feedback: str, feedback_type: str = "general"):
        """Add customer feedback to the recommendation set"""
        if self.customer_feedback is None:
            self.customer_feedback = {}
        
        if feedback_type not in self.customer_feedback:
            self.customer_feedback[feedback_type] = []
        
        self.customer_feedback[feedback_type].append({
            "feedback": feedback,
            "timestamp": datetime.now(),
            "stage": self.recommendation_stage
        })
    
    def add_discussion_entry(self, entry_type: str, content: str, user_message: str = ""):
        """Add an entry to the discussion history"""
        self.discussion_history.append({
            "type": entry_type,  # question, concern, comparison, feedback
            "content": content,
            "user_message": user_message,
            "timestamp": datetime.now(),
            "stage": self.recommendation_stage
        })
    
    def record_pricing_inquiry(self, inquiry: str):
        """Record a pricing inquiry without triggering quote generation"""
        self.pricing_inquiries.append({
            "inquiry": inquiry,
            "timestamp": datetime.now(),
            "stage": self.recommendation_stage
        })
    
    def request_comparison(self, products: List[str], comparison_criteria: List[str] = None):
        """Record a comparison request"""
        self.comparison_requests.append({
            "products": products,
            "criteria": comparison_criteria or [],
            "timestamp": datetime.now(),
            "stage": self.recommendation_stage
        })
    
    def is_ready_for_quote(self) -> bool:
        """Determine if the customer is ready for quote generation based on conversation flow"""
        return (
            self.explicit_quote_requested or  # Explicit request
            (
                len(self.selected_recommendations) > 0 and  # Has selections
                self.recommendation_stage in ["selection", "quote_ready"] and  # In appropriate stage
                len(self.discussion_history) >= 2  # Has had meaningful discussion
            )
        )
    
    class Config:
        # Allow extra fields for compatibility
        extra = "allow" 