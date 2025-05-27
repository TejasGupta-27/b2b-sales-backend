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

class AIProvider(ABC):
    """Base class for all AI service providers"""
    
    def __init__(self, **kwargs):
        self.config = kwargs
        self.token_tracker = TokenTracker()
    
    def _track_usage(self, usage: Dict[str, Any]):
        """Track token usage for the request"""
        if usage:
            self.token_tracker.track_usage(
                provider=self.provider_name,
                model=self.config.get("deployment_name", "unknown"),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0)
            )

    @abstractmethod
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        **kwargs
    ) -> AIResponse:
        """Generate response from the AI provider"""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured"""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider"""
        pass 