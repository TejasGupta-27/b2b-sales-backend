from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from .token_tracker import TokenTracker

class AIMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str

class AIResponse(BaseModel):
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class AIProvider(ABC):
    """Abstract base class for AI providers"""
    
    def __init__(self, **config):
        self.config = config
        self.usage_tracker = None
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider"""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured"""
        pass
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        **kwargs
    ) -> AIResponse:
        """Generate a response from the AI provider"""
        pass
    
    def _track_usage(self, usage: Dict[str, Any]):
        """Track token usage"""
        if self.usage_tracker:
            self.usage_tracker.track_usage(self.provider_name, usage) 