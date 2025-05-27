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
            logger.info(f"API version: {self.config.get('api_version', '2024-02-15-preview')}")
            
            # Log input messages
            logger.info(f"Input messages: {[{'role': m.role, 'content': m.content} for m in messages]}")
            
            client = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                api_key=self.config['api_key'],
                api_version=self.config.get('api_version', '2024-02-15-preview')
            )
            
            # Convert AIMessage objects to dict format expected by Azure OpenAI
            formatted_messages = [
                {
                    "role": msg.role,
                    "content": msg.content  # Remove the nested structure
                } for msg in messages
            ]
            
            # Log the formatted messages for debugging
            logger.debug(f"Formatted messages: {formatted_messages}")
            
            try:
                logger.info("Making request to Azure OpenAI API...")
                response = await client.chat.completions.create(
                    model=self.config['deployment_name'],
                    messages=formatted_messages,
                    max_tokens=kwargs.get("max_tokens", 800),
                    temperature=kwargs.get("temperature", 1),
                    top_p=kwargs.get("top_p", 1),
                    frequency_penalty=kwargs.get("frequency_penalty", 0),
                    presence_penalty=kwargs.get("presence_penalty", 0),
                    stop=kwargs.get("stop", None),
                    stream=kwargs.get("stream", False)
                )
                logger.info("Successfully received response from Azure OpenAI API")
                
            except Exception as api_error:
                logger.error(f"Azure OpenAI API error: {str(api_error)}")
                logger.error(f"Request parameters: model={self.config['deployment_name']}, messages={formatted_messages}")
                logger.error(f"Error type: {type(api_error).__name__}")
                if hasattr(api_error, 'response'):
                    logger.error(f"Response status: {api_error.response.status_code if hasattr(api_error.response, 'status_code') else 'N/A'}")
                    logger.error(f"Response body: {api_error.response.text if hasattr(api_error.response, 'text') else 'N/A'}")
                raise
            
            try:
                if not response.choices:
                    logger.error("No response choices returned from Azure OpenAI")
                    raise Exception("No response choices returned from Azure OpenAI")
                    
                choice = response.choices[0]
                logger.debug(f"Response choice: {choice}")
                
                if not choice.message:
                    logger.error("No message in response choice")
                    raise Exception("No message in response choice")
                
                # Log the response content and structure for debugging
                logger.debug(f"Response choice message: {choice.message}")
                logger.debug(f"Response choice message content: {choice.message.content}")
                logger.debug(f"Response usage: {response.usage}")
                
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
                
            except Exception as response_error:
                logger.error(f"Error processing response: {str(response_error)}")
                logger.error(f"Response object: {response}")
                logger.error(f"Response type: {type(response)}")
                raise Exception(f"Error processing Azure OpenAI response: {str(response_error)}")
                
        except Exception as e:
            logger.exception("Error in Azure OpenAI request")
            logger.error(f"Full error details: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            if hasattr(e, '__cause__'):
                logger.error(f"Caused by: {str(e.__cause__)}")
            raise Exception(f"Error calling Azure OpenAI: {str(e)}") 