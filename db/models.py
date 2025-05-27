from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, ENUM
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
import os
from models.chat import MessageType
from config import settings

Base = declarative_base()

# Create engine with the configured database URL
engine = create_engine(settings.database_url, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name = Column(String, nullable=False)
    contact_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String)
    industry = Column(String)
    company_size = Column(String)
    annual_revenue = Column(String)
    pain_points = Column(JSONB, default=list)
    budget_range = Column(String)
    decision_timeline = Column(String)
    decision_makers = Column(JSONB, default=list)
    status = Column(String, default="new")
    lead_score = Column(Integer)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contact = Column(DateTime)
    next_follow_up = Column(DateTime)
    
    # Relationship with chat messages
    chat_messages = relationship("ChatMessage", back_populates="lead", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    message_type = Column(ENUM(MessageType, name="messagetype"), nullable=False)
    content = Column(Text, nullable=False)
    stage = Column(String)
    message_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship with lead
    lead = relationship("Lead", back_populates="chat_messages") 