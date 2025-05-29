import aiohttp
import json
import logging
import os
from typing import List
from urllib.parse import urljoin, urlparse
from .base import AIProvider, AIMessage, AIResponse

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
            from openai import AsyncAzureOpenAI
            
            # Validate and format the endpoint
            endpoint = self._validate_endpoint(self.config['endpoint'])
            
            # Log the configuration (excluding sensitive data)
            logger.info(f"Initializing Azure OpenAI client with endpoint: {endpoint}")
            logger.info(f"Using deployment: {self.config['deployment_name']}")
            
            client = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                api_key=self.config['api_key'],
                api_version=self.config.get('api_version', '2024-02-15-preview')
            )
            
            # Convert AIMessage objects to dict format expected by Azure OpenAI
            formatted_messages = [
                {
                    "role": msg.role,
                    "content": msg.content
                } for msg in messages
            ]
            
            try:
                logger.info("Making request to Azure OpenAI API...")
                response = await client.chat.completions.create(
                    model=self.config['deployment_name'],
                    messages=formatted_messages,
                    max_tokens=kwargs.get("max_tokens", 800),
                    temperature=kwargs.get("temperature", 0.7),  # Lower temperature
                    top_p=kwargs.get("top_p", 1),
                    frequency_penalty=kwargs.get("frequency_penalty", 0),
                    presence_penalty=kwargs.get("presence_penalty", 0),
                    stop=kwargs.get("stop", None),
                    stream=kwargs.get("stream", False)
                )
                logger.info("Successfully received response from Azure OpenAI API")
                
            except Exception as api_error:
                # Check if it's a content filter error
                if hasattr(api_error, 'response') and 'content_filter' in str(api_error):
                    logger.warning("Content filter triggered - using fallback response")
                    return AIResponse(
                        content="I apologize, but I need to rephrase my response. Let me help you with your business technology needs. What specific requirements can I assist you with today?",
                        model=self.config["deployment_name"],
                        provider=self.provider_name,
                        usage={"prompt_tokens": 0, "completion_tokens": 20, "total_tokens": 20},
                        finish_reason="content_filter_fallback"
                    )
                
                logger.error(f"Azure OpenAI API error: {str(api_error)}")
                raise
            
            # Process successful response
            if not response.choices:
                logger.error("No response choices returned from Azure OpenAI")
                raise Exception("No response choices returned from Azure OpenAI")
                
            choice = response.choices[0]
            
            if not choice.message:
                logger.error("No message in response choice")
                raise Exception("No message in response choice")
            
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
            
            # Track usage
            self._track_usage(result.usage)
            
            return result
            
        except Exception as e:
            logger.exception("Error in Azure OpenAI request")
            raise Exception(f"Error calling Azure OpenAI: {str(e)}") 