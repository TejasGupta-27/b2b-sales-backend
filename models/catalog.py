from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

class ProductCategory(str, Enum):
    SOFTWARE = "software"
    SERVICE = "service"
    INTEGRATION = "integration"
    SUPPORT = "support"

class PricingModel(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"
    ONE_TIME = "one_time"
    CUSTOM = "custom"

class Product(BaseModel):
    id: str
    name: str
    category: ProductCategory
    description: str
    features: List[str]
    benefits: List[str]
    pricing_tiers: List[Dict[str, Any]]
    minimum_users: int = 1
    maximum_users: Optional[int] = None
    implementation_time: str
    support_level: str
    ideal_for: List[str]  # Company sizes, industries, use cases

class PricingTier(BaseModel):
    name: str
    price: float
    billing_cycle: PricingModel
    features_included: List[str]
    user_limit: Optional[int] = None
    storage_gb: Optional[int] = None
    api_calls_monthly: Optional[int] = None

class QuoteRequest(BaseModel):
    customer_name: str
    company_name: str
    email: str
    phone: Optional[str] = None
    company_size: str
    industry: Optional[str] = None
    requirements: List[str]
    budget_range: Optional[str] = None
    timeline: Optional[str] = None
    additional_notes: Optional[str] = None

class Quote(BaseModel):
    id: str
    customer_info: QuoteRequest
    recommended_products: List[Dict[str, Any]]
    total_monthly_cost: float
    total_annual_cost: float
    discount_applied: float = 0.0
    implementation_timeline: str
    valid_until: str
    terms_and_conditions: List[str]
    next_steps: List[str] 