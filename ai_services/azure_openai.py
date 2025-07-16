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
                try:
                    # First try to parse the JSON directly
                    function_args = json.loads(choice.message.function_call.arguments)
                except json.JSONDecodeError as json_error:
                    logger.warning(f"Initial JSON parsing failed: {json_error}")
                    logger.debug(f"Raw arguments: {choice.message.function_call.arguments[:500]}...")
                    
                    # Try to fix the malformed JSON
                    fixed_json = self._fix_json_arguments(choice.message.function_call.arguments)
                    if fixed_json:
                        try:
                            function_args = json.loads(fixed_json)
                            logger.info("Successfully parsed JSON after fixing")
                        except json.JSONDecodeError as fix_error:
                            logger.error(f"JSON fixing failed: {fix_error}")
                            raise Exception(f"Failed to parse function call arguments even after attempting fixes. Original error: {json_error}")
                    else:
                        raise Exception(f"Failed to fix malformed JSON. Original error: {json_error}")
                
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

    def _fix_json_arguments(self, json_str: str) -> str:
        """Attempt to fix common JSON parsing issues"""
        try:
            import re
            
            # Log the problematic JSON for debugging
            logger.debug(f"Attempting to fix malformed JSON: {json_str[:500]}...")
            
            # Remove any trailing commas before closing braces/brackets
            fixed = re.sub(r',(\s*[}\]])', r'\1', json_str)
            
            # Fix common quote issues
            # Remove any unescaped quotes in the middle of strings
            fixed = re.sub(r'([^\\])"([^"]*?)([^\\])"', r'\1"\2\3"', fixed)
            
            # Try to balance quotes by adding missing closing quotes
            quote_count = fixed.count('"')
            if quote_count % 2 != 0:
                # Find the last unescaped quote and add a closing quote
                last_quote_pos = fixed.rfind('"')
                if last_quote_pos != -1:
                    # Check if it's already escaped
                    if last_quote_pos == 0 or fixed[last_quote_pos - 1] != '\\':
                        fixed = fixed + '"'
            
            # Fix common escape sequence issues
            # Replace any unescaped backslashes that aren't part of valid escape sequences
            fixed = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', fixed)
            
            # Fix newlines and other control characters in strings
            fixed = fixed.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            
            # Remove any null bytes or other invalid characters
            fixed = fixed.replace('\x00', '')
            
            # Try to fix malformed object/array structures
            # Count braces and brackets to ensure they're balanced
            brace_count = fixed.count('{') - fixed.count('}')
            bracket_count = fixed.count('[') - fixed.count(']')
            
            if brace_count > 0:
                fixed = fixed + '}' * brace_count
            elif brace_count < 0:
                # Remove extra closing braces
                fixed = re.sub(r'}+$', '}', fixed)
            
            if bracket_count > 0:
                fixed = fixed + ']' * bracket_count
            elif bracket_count < 0:
                # Remove extra closing brackets
                fixed = re.sub(r'\]+$', ']', fixed)
            
            logger.debug(f"Fixed JSON: {fixed[:500]}...")
            return fixed
            
        except Exception as e:
            logger.error(f"Failed to fix JSON arguments: {e}")
            return None 