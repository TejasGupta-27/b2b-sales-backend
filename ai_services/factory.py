from typing import Dict, Type
from .base import AIProvider
from .azure_openai import AzureOpenAIProvider
from .huggingface import HuggingFaceProvider
from config import settings

class AIServiceFactory:
    """Factory class to create AI service providers"""
    
    _providers: Dict[str, Type[AIProvider]] = {
        "azure_openai": AzureOpenAIProvider,
        "huggingface": HuggingFaceProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_name: str = None) -> AIProvider:
        """Create an AI provider instance"""
        if provider_name is None:
            provider_name = settings.default_ai_provider
        
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown AI provider: {provider_name}")
        
        provider_class = cls._providers[provider_name]
        
        # Configure based on provider type
        if provider_name == "azure_openai":
            config = {
                "api_key": settings.azure_openai_api_key,
                "endpoint": settings.azure_openai_endpoint,
                "deployment_name": settings.azure_openai_deployment_name,
                "api_version": settings.azure_openai_api_version
            }
        elif provider_name == "huggingface":
            config = {
                "api_key": settings.huggingface_api_key,
                "model": settings.huggingface_model
            }
        else:
            config = {}
        
        return provider_class(**config)
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider names"""
        return list(cls._providers.keys())
    
    @classmethod
    def get_configured_providers(cls) -> list[str]:
        """Get list of properly configured providers"""
        configured = []
        for provider_name in cls._providers.keys():
            try:
                provider = cls.create_provider(provider_name)
                if provider.is_configured():
                    configured.append(provider_name)
            except Exception:
                continue
        return configured 