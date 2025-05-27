from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import aiofiles
from datetime import datetime
import uuid
from pathlib import Path
import logging

# Import AI services
from ai_services.factory import AIServiceFactory
from ai_services.sales_agent import SalesAgentProvider
from ai_services.base import AIMessage
from models.lead import Lead
from routes.leads import router as leads_router
from config import settings
from ai_services.b2b_sales_agent import B2BSalesAgent

# Configure logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'main.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(title="B2B Sales Agent API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include lead management routes
app.include_router(leads_router)

# Updated Pydantic models
class SalesChatMessage(BaseModel):
    message: str
    lead_id: Optional[str] = None
    conversation_stage: str = "discovery"
    provider: Optional[str] = None

class SalesChatResponse(BaseModel):
    id: str
    content: str
    timestamp: datetime
    provider: str
    model: str
    lead_id: Optional[str] = None
    conversation_stage: str
    insights: Optional[dict] = None
    suggested_actions: List[str] = []

class SalesConversation(BaseModel):
    message: str
    customer_context: Optional[Dict[str, Any]] = None

class SalesResponse(BaseModel):
    content: str
    quote: Optional[Dict[str, Any]] = None
    recommendations: List[Dict[str, Any]] = []
    next_steps: List[str] = []

@app.get("/")
async def root():
    return {"message": "B2B Sales Agent API is running!"}

@app.post("/api/sales-chat", response_model=SalesResponse)
async def sales_chat(conversation: SalesConversation):
    """B2B Sales conversation endpoint"""
    
    try:
        # Create base AI provider
        base_provider = AIServiceFactory.create_provider("azure_openai")
        
        # Create B2B sales agent
        sales_agent = B2BSalesAgent(base_provider)
        
        # Prepare messages
        messages = [
            AIMessage(role="user", content=conversation.message)
        ]
        
        # Generate response
        response = await sales_agent.generate_response(
            messages=messages,
            customer_context=conversation.customer_context,
            max_tokens=1000,
            temperature=0.7
        )
        
        # Extract recommendations and next steps
        recommendations = []
        next_steps = []
        quote = None
        
        # Ensure response has required fields
        if not hasattr(response, 'content'):
            raise ValueError("Response missing required 'content' field")
            
        # Create SalesResponse object
        sales_response = SalesResponse(
            content=response.content,
            quote=quote,
            recommendations=recommendations,
            next_steps=next_steps
        )
        
        logger.debug(f"Returning sales response: {sales_response}")
        return sales_response
        
    except Exception as e:
        logger.error(f"Error in sales conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in sales conversation: {str(e)}")

@app.get("/api/products")
async def get_products():
    """Get available products and pricing"""
    base_provider = AIServiceFactory.create_provider("azure_openai")
    sales_agent = B2BSalesAgent(base_provider)
    
    return {"products": sales_agent.product_catalog}

@app.post("/api/generate-quote")
async def generate_quote(quote_request: Dict[str, Any]):
    """Generate a detailed quotation"""
    base_provider = AIServiceFactory.create_provider("azure_openai")
    sales_agent = B2BSalesAgent(base_provider)
    
    quote = sales_agent._generate_quote(quote_request)
    return quote

async def get_lead_by_id(lead_id: str) -> Optional[Lead]:
    """Helper function to get lead by ID"""
    try:
        leads_file = Path("Data/leads.json")
        if not leads_file.exists():
            return None
        
        with open(leads_file, 'r') as f:
            leads_data = json.load(f)
        
        lead_data = next((l for l in leads_data if l["id"] == lead_id), None)
        return Lead(**lead_data) if lead_data else None
    except Exception:
        return None

async def update_lead_conversation(lead_id: str, user_message: str, ai_response: str, stage: str):
    """Update lead conversation history"""
    try:
        leads_file = Path("Data/leads.json")
        if not leads_file.exists():
            return
        
        with open(leads_file, 'r') as f:
            leads_data = json.load(f)
        
        lead_index = next((i for i, l in enumerate(leads_data) if l["id"] == lead_id), None)
        if lead_index is None:
            return
        
        # Add conversation entries
        timestamp = datetime.now().isoformat()
        
        leads_data[lead_index]["conversation_history"].extend([
            {
                "timestamp": timestamp,
                "message": user_message,
                "stage": stage,
                "type": "user"
            },
            {
                "timestamp": timestamp,
                "message": ai_response,
                "stage": stage,
                "type": "assistant"
            }
        ])
        
        leads_data[lead_index]["last_contact"] = timestamp
        leads_data[lead_index]["updated_at"] = timestamp
        
        with open(leads_file, 'w') as f:
            json.dump(leads_data, f, indent=2, default=str)
    
    except Exception as e:
        print(f"Error updating lead conversation: {e}")

# Add other existing endpoints...

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
