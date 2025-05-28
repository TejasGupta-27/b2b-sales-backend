from enum import Enum
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class MessageType(Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None

class ChatRequest(BaseModel):
    message: str
    lead_id: Optional[str] = None
    conversation_stage: Optional[str] = "discovery"
    customer_context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    message: str
    lead_id: Optional[str] = None
    conversation_stage: str = "discovery"
    metadata: Optional[Dict[str, Any]] = None 