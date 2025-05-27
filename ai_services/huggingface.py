import aiohttp
import asyncio
from typing import List
from .base import AIProvider, AIMessage, AIResponse

class HuggingFaceProvider(AIProvider):
    
    @property
    def provider_name(self) -> str:
        return "huggingface"
    
    def is_configured(self) -> bool:
        return self.config.get("api_key") is not None
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        **kwargs
    ) -> AIResponse:
        if not self.is_configured():
            raise ValueError("Hugging Face provider is not properly configured")
        
        # Convert messages to a single prompt for most HF models
        prompt = self._format_messages_for_hf(messages)
        
        # Use Hugging Face Inference API
        url = f"https://api-inference.huggingface.co/models/{self.config['model']}"
        
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": kwargs.get("max_tokens", 150),
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
                "do_sample": True,
                "return_full_text": False
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Retry logic for model loading
                for attempt in range(3):
                    async with session.post(url, headers=headers, json=payload) as response:
                        if response.status == 503:
                            # Model is loading, wait and retry
                            await asyncio.sleep(2 ** attempt)
                            continue
                        elif response.status != 200:
                            error_text = await response.text()
                            raise Exception(f"Hugging Face API error: {response.status} - {error_text}")
                        
                        result = await response.json()
                        
                        # Handle different response formats
                        if isinstance(result, list) and len(result) > 0:
                            generated_text = result[0].get("generated_text", "")
                        elif isinstance(result, dict):
                            generated_text = result.get("generated_text", "")
                        else:
                            generated_text = "Sorry, I couldn't generate a response."
                        
                        return AIResponse(
                            content=generated_text.strip(),
                            model=self.config["model"],
                            provider=self.provider_name,
                            usage={"prompt_tokens": len(prompt.split()), "completion_tokens": len(generated_text.split())},
                            finish_reason="stop"
                        )
                
                raise Exception("Model is still loading after multiple attempts")
                
        except Exception as e:
            raise Exception(f"Error calling Hugging Face: {str(e)}")
    
    def _format_messages_for_hf(self, messages: List[AIMessage]) -> str:
        """Format messages for Hugging Face models"""
        formatted_parts = []
        
        for message in messages:
            if message.role == "system":
                formatted_parts.append(f"System: {message.content}")
            elif message.role == "user":
                formatted_parts.append(f"Human: {message.content}")
            elif message.role == "assistant":
                formatted_parts.append(f"Assistant: {message.content}")
        
        # Add prompt for response
        formatted_parts.append("Assistant:")
        
        return "\n".join(formatted_parts) 