from pydantic import BaseModel
from typing import List, Dict, Any, Optional
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
    recommendations: List[ProductRecommendation]
    created_at: datetime
    selected_recommendation: Optional[str] = None
    selection_timestamp: Optional[datetime] = None
    reasoning: str
    next_steps: List[str] 