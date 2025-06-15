from sqlalchemy import Column, String, Text, DateTime, Boolean, Float, Integer, JSON, ForeignKey, Enum, func, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from enum import Enum as PyEnum
import uuid

class MessageType(PyEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"

class LeadStatus(PyEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"

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
    notes = Column(Text)
    last_contact = Column(DateTime)
    next_follow_up = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationship with chat messages
    chat_messages = relationship("ChatMessage", back_populates="lead", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True)
    lead_id = Column(String, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    message_type = Column(Enum(MessageType), nullable=False)
    content = Column(Text, nullable=False)
    stage = Column(String)
    message_metadata = Column(JSON)  # Store additional metadata
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship with lead
    lead = relationship("Lead", back_populates="chat_messages")

class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(String, primary_key=True)
    quote_number = Column(String, unique=True, nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
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
    
    # Relationship with lead
    lead = relationship("Lead")

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
    
    # Relationship with lead
    lead = relationship("Lead")
    
    # Relationship with product recommendations
    product_recommendations = relationship("ProductRecommendation", back_populates="recommendation_set", cascade="all, delete-orphan") 