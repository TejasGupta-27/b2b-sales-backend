from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

class CompanySize(str, Enum):
    STARTUP = "startup"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"

class Lead(BaseModel):
    id: Optional[str] = None
    company_name: str
    contact_name: str
    email: EmailStr
    phone: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[CompanySize] = None
    annual_revenue: Optional[str] = None
    pain_points: List[str] = []
    budget_range: Optional[str] = None
    decision_timeline: Optional[str] = None
    decision_makers: List[str] = []
    status: LeadStatus = LeadStatus.NEW
    lead_score: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    last_contact: Optional[datetime] = None
    next_follow_up: Optional[datetime] = None
    conversation_history: List[Dict[str, Any]] = []

class LeadCreate(BaseModel):
    company_name: str
    contact_name: str
    email: EmailStr
    phone: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[CompanySize] = None

class LeadUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[CompanySize] = None
    annual_revenue: Optional[str] = None
    pain_points: Optional[List[str]] = None
    budget_range: Optional[str] = None
    decision_timeline: Optional[str] = None
    decision_makers: Optional[List[str]] = None
    status: Optional[LeadStatus] = None
    lead_score: Optional[int] = None
    notes: Optional[str] = None
    next_follow_up: Optional[datetime] = None 