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
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

# Import database models
from db.models import ChatMessage as DBChatMessage, Lead as DBLead, get_db, Base, engine

# Import AI services and models
from ai_services.factory import AIServiceFactory
from ai_services.sales_agent import SalesAgentProvider
from ai_services.base import AIMessage
from models.lead import Lead
from models.chat import MessageType, ChatRequest, ChatResponse
from routes.leads import router as leads_router
from config import settings
from ai_services.b2b_sales_agent import B2BSalesAgent
from routes import quotes

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

# Include the quotes router
app.include_router(quotes.router, prefix="/api/quotes", tags=["quotes"])

# Sales-specific models
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

class ChatMessageResponse(BaseModel):
    id: str
    content: str
    role: str
    timestamp: str
    stage: Optional[str] = None

class LeadResponse(BaseModel):
    id: str
    company_name: str
    contact_name: str
    email: str
    phone: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None
    lead_score: Optional[int] = None
    created_at: str
    last_contact: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "B2B Sales Agent API is running!"}

@app.post("/api/sales-chat")
async def sales_chat(request: SalesChatMessage, db: Session = Depends(get_db)):
    try:
        logger.info(f"Sales chat request: {request}")
        
        # Handle lead management (existing code)
        lead_id = request.lead_id
        if not lead_id:
            lead_id = str(uuid.uuid4())
            lead = DBLead(
                id=lead_id,
                company_name="Unknown",
                contact_name="Unknown",
                email="unknown@example.com",
                status="new",
                created_at=datetime.now()
            )
            db.add(lead)
            db.flush()
        
        # Save user message
        user_message = DBChatMessage(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            message_type=MessageType.USER,
            content=request.message,
            stage=request.conversation_stage or "discovery"
        )
        db.add(user_message)
        db.flush()
        
        # Prepare conversation history
        messages = []
        existing_messages = db.query(DBChatMessage).filter(
            DBChatMessage.lead_id == lead_id
        ).order_by(DBChatMessage.created_at).all()
        
        for msg in existing_messages:
            role = "user" if msg.message_type == MessageType.USER else "assistant"
            messages.append(AIMessage(role=role, content=msg.content))
        
        # Create B2B Sales Agent instead of generic AI provider
        base_provider = AIServiceFactory.create_provider(request.provider)
        b2b_agent = B2BSalesAgent(base_provider)
        
        # Get customer context from the lead
        customer_context = None
        lead_record = db.query(DBLead).filter(DBLead.id == lead_id).first()
        if lead_record:
            customer_context = {
                "company_name": lead_record.company_name,
                "contact_name": lead_record.contact_name,
                "email": lead_record.email,
                "company_size": getattr(lead_record, 'company_size', None),
                "industry": getattr(lead_record, 'industry', None),
                "budget_range": getattr(lead_record, 'budget_range', None),
                "timeline": getattr(lead_record, 'decision_timeline', None)
            }
        
        # Generate response with sales context
        response = await b2b_agent.generate_response(
            messages, 
            customer_context=customer_context
        )
        
        # Save assistant response
        response_metadata = {
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage
        }
        
        # Add quote information if generated
        if response.metadata and 'quote' in response.metadata:
            response_metadata['quote'] = response.metadata['quote']
        
        assistant_message = DBChatMessage(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            message_type=MessageType.ASSISTANT,
            content=response.content,
            stage=request.conversation_stage or "discovery",
            message_metadata=response_metadata
        )
        db.add(assistant_message)
        db.commit()
        
        # Prepare response
        chat_response = ChatResponse(
            message=response.content,
            lead_id=lead_id,
            conversation_stage=request.conversation_stage or "discovery",
            metadata=response.metadata
        )
        
        return chat_response
        
    except Exception as e:
        logger.error(f"Error in sales chat: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
async def get_products():
    """Get available products and pricing"""
    base_provider = AIServiceFactory.create_provider("azure_openai")
    sales_agent = B2BSalesAgent(base_provider)
    
    return {"products": sales_agent.product_catalog}

@app.post("/api/generate-quote")
async def generate_quote(quote_request: Dict[str, Any]):
    """Generate a detailed quotation (legacy endpoint)"""
    base_provider = AIServiceFactory.create_provider("azure_openai")
    sales_agent = B2BSalesAgent(base_provider)
    
    quote = await sales_agent.generate_quote(quote_request)
    return {"quote": quote}

@app.post("/api/chat/send")
async def send_message(request: ChatRequest):
    try:
        logger.info(f"Received chat request: {request}")
        
        # Generate or use existing lead ID
        lead_id = request.lead_id
        if not lead_id:
            lead_id = f"temp_{uuid.uuid4().hex[:8]}"
            logger.info(f"Generated temporary lead ID: {lead_id}")
        
        # Get database session
        db = next(get_db())
        
        try:
            # Check if lead exists, create if not
            lead = db.query(DBLead).filter(DBLead.id == lead_id).first()
            if not lead:
                # Create new lead with basic info
                lead = DBLead(
                    id=lead_id,
                    company_name="Unknown",
                    contact_name="Unknown",
                    email="unknown@example.com",
                    status="new"
                )
                db.add(lead)
                db.flush()  # Flush to get the ID
                logger.info(f"Created new lead: {lead_id}")
            
            # Save user message to database FIRST
            user_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                message_type=MessageType.USER,
                content=request.message,
                stage=request.conversation_stage or "discovery"
            )
            db.add(user_message)
            db.flush()  # Ensure it's saved before proceeding
            logger.info(f"Saved user message to database: {user_message.id}")
            
            # Prepare messages for AI (include conversation history)
            messages = []
            
            # Add conversation history from database
            existing_messages = db.query(DBChatMessage).filter(
                DBChatMessage.lead_id == lead_id
            ).order_by(DBChatMessage.created_at).all()
            
            for msg in existing_messages:
                role = "user" if msg.message_type == MessageType.USER else "assistant"
                messages.append(AIMessage(role=role, content=msg.content))
            
            # Get AI response
            ai_provider = AIServiceFactory.create_provider()
            response = await ai_provider.generate_response(messages)
            
            # Save assistant response to database
            assistant_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                message_type=MessageType.ASSISTANT,
                content=response.content,
                stage=request.conversation_stage or "discovery",
                message_metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage
                }
            )
            db.add(assistant_message)
            db.commit()  # Commit all changes
            logger.info(f"Saved assistant message to database: {assistant_message.id}")
            
            return ChatResponse(
                message=response.content,
                lead_id=lead_id,
                conversation_stage=request.conversation_stage or "discovery",
                metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage
                }
            )
            
        except SQLAlchemyError as db_error:
            db.rollback()
            logger.error(f"Database error: {str(db_error)}")
            # Fallback to AI response without database
            ai_provider = AIServiceFactory.create_provider()
            messages = [AIMessage(role="user", content=request.message)]
            response = await ai_provider.generate_response(messages)
            
            return ChatResponse(
                message=response.content,
                lead_id=lead_id,
                conversation_stage=request.conversation_stage or "discovery",
                metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage,
                    "warning": "Database unavailable - conversation not saved"
                }
            )
        except Exception as general_error:
            db.rollback()
            logger.error(f"General error: {str(general_error)}")
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.exception("Error in chat message")
        logger.error(f"Error in chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/chat/history/{lead_id}")
async def get_chat_history(lead_id: str):
    """Get chat history for a specific lead"""
    try:
        logger.info(f"Fetching chat history for lead: {lead_id}")
        db = next(get_db())
        try:
            messages = db.query(DBChatMessage).filter(
                DBChatMessage.lead_id == lead_id
            ).order_by(DBChatMessage.created_at).all()
            
            logger.info(f"Found {len(messages)} messages for lead {lead_id}")
            
            history = []
            for msg in messages:
                history.append({
                    "id": msg.id,
                    "role": msg.message_type.value.lower(),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "stage": msg.stage,
                    "metadata": msg.message_metadata
                })
            
            logger.info(f"Returning chat history: {history}")
            return {"history": history}
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}")
        return {"history": []}

@app.get("/api/leads")
async def get_leads():
    """Get all leads with their latest message"""
    try:
        db = next(get_db())
        try:
            leads = db.query(DBLead).all()
            result = []
            
            for lead in leads:
                # Get latest message
                latest_message = db.query(DBChatMessage).filter(
                    DBChatMessage.lead_id == lead.id
                ).order_by(DBChatMessage.created_at.desc()).first()
                
                result.append({
                    "id": lead.id,
                    "company_name": lead.company_name,
                    "contact_name": lead.contact_name,
                    "email": lead.email,
                    "status": lead.status,
                    "created_at": lead.created_at.isoformat(),
                    "last_message": latest_message.content if latest_message else None,
                    "last_message_time": latest_message.created_at.isoformat() if latest_message else None
                })
            
            return {"leads": result}
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error fetching leads: {str(e)}")
        return {"leads": []}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "B2B Sales Agent API is running"}

# Update the startup event to ensure tables are created and check database connection
@app.on_event("startup")
async def startup_event():
    """Create database tables on startup and verify connection"""
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Test database connection
        db = next(get_db())
        try:
            # Test query
            result = db.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            
            # Check if tables exist
            tables_check = db.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in tables_check]
            logger.info(f"Available tables: {tables}")
            
        except Exception as db_test_error:
            logger.error(f"Database connection test failed: {str(db_test_error)}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

# Simple AI response function (fallback when AI services aren't available)
def generate_simple_response(user_message: str) -> str:
    """Generate a simple response when AI services are not available"""
    responses = [
        f"Thank you for your message: '{user_message}'. I'm here to help with your business needs.",
        f"I understand you're asking about '{user_message}'. How can I assist you further with your requirements?",
        f"That's an interesting point about '{user_message}'. What specific aspects would you like to explore?",
        "I'm here to help you find the right solutions for your business. What are your main priorities?",
        "Let me help you with that. Could you provide more details about your specific requirements?"
    ]
    import random
    return random.choice(responses)

@app.get("/api/debug/database")
async def debug_database():
    """Debug endpoint to check database status"""
    try:
        db = next(get_db())
        try:
            # Check tables
            tables_result = db.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in tables_result]
            
            # Count records
            leads_count = db.query(DBLead).count()
            messages_count = db.query(DBChatMessage).count()
            
            # Get recent messages
            recent_messages = db.query(DBChatMessage).order_by(
                DBChatMessage.created_at.desc()
            ).limit(5).all()
            
            recent_data = []
            for msg in recent_messages:
                recent_data.append({
                    "id": msg.id,
                    "lead_id": msg.lead_id,
                    "type": msg.message_type.value,
                    "content": msg.content[:50] + "..." if len(msg.content) > 50 else msg.content,
                    "created_at": msg.created_at.isoformat()
                })
            
            return {
                "status": "connected",
                "tables": tables,
                "counts": {
                    "leads": leads_count,
                    "messages": messages_count
                },
                "recent_messages": recent_data
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/api/debug/lead/{lead_id}")
async def debug_lead_messages(lead_id: str):
    """Debug endpoint to check specific lead messages"""
    try:
        db = next(get_db())
        try:
            # Get lead info
            lead = db.query(DBLead).filter(DBLead.id == lead_id).first()
            if not lead:
                return {"error": "Lead not found"}
            
            # Get all messages for this lead
            messages = db.query(DBChatMessage).filter(
                DBChatMessage.lead_id == lead_id
            ).order_by(DBChatMessage.created_at).all()
            
            message_data = []
            for msg in messages:
                message_data.append({
                    "id": msg.id,
                    "lead_id": msg.lead_id,
                    "type": msg.message_type.value,
                    "content": msg.content,
                    "stage": msg.stage,
                    "created_at": msg.created_at.isoformat(),
                    "metadata": msg.message_metadata
                })
            
            return {
                "lead": {
                    "id": lead.id,
                    "company_name": lead.company_name,
                    "contact_name": lead.contact_name,
                    "created_at": lead.created_at.isoformat()
                },
                "messages": message_data,
                "message_count": len(message_data)
            }
        finally:
            db.close()
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
