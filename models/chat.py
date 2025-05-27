from enum import Enum
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None

class ChatRequest(BaseModel):
    message: str
    lead_id: Optional[str] = None
    conversation_stage: Optional[str] = "discovery"
    conversation_history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    message: str
    lead_id: str
    conversation_stage: str
    metadata: Optional[Dict[str, Any]] = None 