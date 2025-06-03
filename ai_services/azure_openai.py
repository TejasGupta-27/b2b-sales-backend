import aiohttp
import json
import logging
import os
from typing import List, Type, Optional, Union, Dict, Any
from urllib.parse import urljoin, urlparse
from pydantic import BaseModel
from openai import AsyncAzureOpenAI
from .base import AIProvider, AIMessage, AIResponse
from .function_models import *

# Configure logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Create a file handler
file_handler = logging.FileHandler(os.path.join(log_dir, 'azure_openai.log'))
file_handler.setLevel(logging.DEBUG)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Get logger and add handlers
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class AzureOpenAIProvider(AIProvider):
    
    @property
    def provider_name(self) -> str:
        return "azure_openai"
    
    def is_configured(self) -> bool:
        required_configs = {
            "api_key": self.config.get("api_key"),
            "endpoint": self.config.get("endpoint"),
            "deployment_name": self.config.get("deployment_name")
        }
        
        missing_configs = [k for k, v in required_configs.items() if not v]
        if missing_configs:
            logger.error(f"Missing required configurations: {missing_configs}")
            return False
        return True
    
    def _validate_endpoint(self, endpoint: str) -> str:
        """Validate and format the endpoint URL"""
        # Remove trailing slash if present
        endpoint = endpoint.rstrip('/')
        
        # Ensure endpoint starts with https://
        if not endpoint.startswith('https://'):
            endpoint = f'https://{endpoint}'
            
        # Validate URL structure
        parsed = urlparse(endpoint)
        if not parsed.netloc:
            raise ValueError(f"Invalid endpoint URL: {endpoint}")
            
        return endpoint
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        **kwargs
    ) -> AIResponse:
        if not self.is_configured():
            raise ValueError("Azure OpenAI provider is not properly configured")
        
        try:
            client = AsyncAzureOpenAI(
                api_key=self.config["api_key"],
                api_version=self.config.get("api_version", "2024-02-15-preview"),
                azure_endpoint=self._validate_endpoint(self.config["endpoint"])
            )
            
            openai_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            response = await client.chat.completions.create(
                model=self.config["deployment_name"],
                messages=openai_messages,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 1000),
                top_p=kwargs.get("top_p", 0.95),
                frequency_penalty=kwargs.get("frequency_penalty", 0),
                presence_penalty=kwargs.get("presence_penalty", 0)
            )
            
            choice = response.choices[0]
            
            result = AIResponse(
                content=choice.message.content or "",
                model=self.config["deployment_name"],
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                finish_reason=choice.finish_reason
            )
            
            self._track_usage(result.usage)
            return result
            
        except Exception as e:
            logger.exception("Error in Azure OpenAI request")
            raise Exception(f"Error calling Azure OpenAI: {str(e)}")
    
    async def generate_structured_response(
        self,
        messages: List[AIMessage],
        response_model: Type[BaseModel],
        **kwargs
    ) -> BaseModel:
        """Generate a structured response using function calling"""
        if not self.is_configured():
            raise ValueError("Azure OpenAI provider is not properly configured")
        
        try:
            client = AsyncAzureOpenAI(
                api_key=self.config["api_key"],
                api_version=self.config.get("api_version", "2024-02-15-preview"),
                azure_endpoint=self._validate_endpoint(self.config["endpoint"])
            )
            
            # Convert Pydantic model to OpenAI function schema
            function_schema = self._pydantic_to_function_schema(response_model)
            
            openai_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            response = await client.chat.completions.create(
                model=self.config["deployment_name"],
                messages=openai_messages,
                functions=[function_schema],
                function_call={"name": function_schema["name"]},
                temperature=kwargs.get("temperature", 0.1),  # Lower temperature for structured output
                max_tokens=kwargs.get("max_tokens", 2000)
            )
            
            choice = response.choices[0]
            
            if choice.message.function_call:
                function_args = json.loads(choice.message.function_call.arguments)
                return response_model(**function_args)
            else:
                raise ValueError("No function call in response")
            
        except Exception as e:
            logger.exception("Error in structured Azure OpenAI request")
            raise Exception(f"Error calling Azure OpenAI for structured response: {str(e)}")
    
    def _pydantic_to_function_schema(self, model: Type[BaseModel]) -> Dict[str, Any]:
        """Convert Pydantic model to OpenAI function schema with better enum handling"""
        schema = model.model_json_schema()
        
        # Enhance enum descriptions
        if 'properties' in schema:
            for prop_name, prop_schema in schema['properties'].items():
                if 'enum' in prop_schema:
                    # Add clear description of valid values
                    valid_values = ', '.join(f"'{v}'" for v in prop_schema['enum'])
                    prop_schema['description'] = f"{prop_schema.get('description', '')} Valid values: {valid_values}"
                
                # Emphasize required fields
                if prop_name in schema.get('required', []):
                    prop_schema['description'] = f"[REQUIRED] {prop_schema.get('description', '')}"
        
        return {
            "name": model.__name__.lower(),
            "description": f"Structured response for {model.__name__}. ALL required fields must be included.",
            "parameters": schema
        } 