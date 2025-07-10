from sqlalchemy import Column, String, Text, DateTime, Boolean, Float, Integer, JSON, ForeignKey, Enum, func, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from enum import Enum as PyEnum
import uuid

class MessageType(PyEnum):
    USER = "user"  # Changed to lowercase to match database
    ASSISTANT = "assistant"  # Changed to lowercase to match database 
    SYSTEM = "system"  # Changed to lowercase to match database

class LeadStatus(PyEnum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

class UserRole(PyEnum):
    ADMIN = "admin"
    SALES_AGENT = "sales_agent"
    SALES_MANAGER = "sales_manager"
    VIEWER = "viewer"

class OrganizationType(PyEnum):
    ENTERPRISE = "enterprise"
    SMB = "smb"
    STARTUP = "startup"

# New User model for multi-user support
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.SALES_AGENT)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Organization relationship
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="users")
    
    # User preferences and settings
    preferences = Column(JSON, default=dict)  # UI preferences, notifications, etc.
    api_rate_limit = Column(Integer, default=1000)  # Requests per day
    ai_token_limit = Column(Integer, default=50000)  # AI tokens per month
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime)
    
    # Relationships
    leads = relationship("Lead", back_populates="assigned_user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user")

# New Organization model for multi-tenancy
class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    domain = Column(String, unique=True, nullable=False)  # company.com
    org_type = Column(Enum(OrganizationType), default=OrganizationType.SMB)
    
    # Subscription and limits
    max_users = Column(Integer, default=5)
    max_leads = Column(Integer, default=1000)
    ai_token_limit_monthly = Column(Integer, default=100000)
    is_active = Column(Boolean, default=True)
    
    # Settings
    settings = Column(JSON, default=dict)  # Org-specific configurations
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="organization")
    leads = relationship("Lead", back_populates="organization")

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(String, primary_key=True)
    company_name = Column(String, nullable=False)
    contact_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String)
    industry = Column(String)
    company_size = Column(String)
    annual_revenue = Column(Numeric)
    website = Column(String)
    budget_range = Column(String)
    pain_points = Column(JSON)  # List of pain points
    decision_timeline = Column(String)
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW)
    lead_source = Column(String)
    lead_score = Column(Integer)
    notes = Column(Text)
    last_contact = Column(DateTime)
    next_follow_up = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Multi-user fields
    assigned_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Relationships
    assigned_user = relationship("User", back_populates="leads")
    organization = relationship("Organization", back_populates="leads")
    chat_messages = relationship("ChatMessage", back_populates="lead", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True)
    lead_id = Column(String, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Add user tracking
    message_type = Column(Enum(MessageType), nullable=False)
    content = Column(Text, nullable=False)
    stage = Column(String)
    message_metadata = Column(JSON)  # Store additional metadata
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    lead = relationship("Lead", back_populates="chat_messages")
    user = relationship("User", back_populates="chat_messages")

class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(String, primary_key=True)
    quote_number = Column(String, unique=True, nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Add user tracking
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    
    # Quote details
    items = Column(JSON, nullable=False)  # List of quote items
    subtotal = Column(Float, nullable=False)
    tax_rate = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    total = Column(Float, nullable=False)
    
    # Quote metadata
    currency = Column(String, default="USD")
    valid_until = Column(DateTime, nullable=False)
    terms = Column(Text)
    notes = Column(Text)
    
    # File information
    pdf_filename = Column(String)
    pdf_url = Column(String)
    
    # Status and tracking
    status = Column(String, default="draft")  # draft, sent, accepted, rejected, expired
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    lead = relationship("Lead")
    user = relationship("User")

class ProductRecommendation(Base):
    __tablename__ = "product_recommendations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recommendation_set_id = Column(String, ForeignKey("recommendation_sets.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    features = Column(JSON, nullable=False)  # List of features
    benefits = Column(JSON, nullable=False)  # List of benefits
    suitability_score = Column(Float, nullable=False)
    customization_options = Column(JSON)  # Optional customization options
    
    # Relationship with recommendation set
    recommendation_set = relationship("RecommendationSet", back_populates="product_recommendations")

class RecommendationSet(Base):
    __tablename__ = "recommendation_sets"
    
    id = Column(String, primary_key=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Add user tracking
    recommendations = Column(JSON, nullable=False)  # List of ProductRecommendation objects
    created_at = Column(DateTime, server_default=func.now())
    selected_recommendations = Column(JSON, default=list)  # List of selected product IDs
    selection_timestamps = Column(JSON, default=dict)  # Map of product_id to selection timestamp
    reasoning = Column(Text)
    next_steps = Column(JSON)  # List of next steps
    conversation_state = Column(JSON)  # Store conversation state and flow analysis
    current_stage = Column(String, default="solution_presentation")  # Current conversation stage
    quote_data = Column(JSON)  # Store generated quote data
    quote_generated_at = Column(DateTime)  # Timestamp when quote was generated
    
    # Relationships
    lead = relationship("Lead")
    user = relationship("User")
    product_recommendations = relationship("ProductRecommendation", back_populates="recommendation_set", cascade="all, delete-orphan")

# Add API Rate Limiting and Usage Tracking
class UserAPIUsage(Base):
    __tablename__ = "user_api_usage"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    api_calls = Column(Integer, default=0)
    ai_tokens_used = Column(Integer, default=0)
    
    # Relationship
    user = relationship("User")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    session_token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationship
    user = relationship("User") 