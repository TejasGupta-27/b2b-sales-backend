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

# Import database components
from db.database import get_db, engine, create_tables, test_connection
from db.models import ChatMessage as DBChatMessage, Lead as DBLead, LeadStatus

# Import routes
from routes.leads import router as leads_router
from routes.quotes import router as quotes_router

# Import AI services
from ai_services.factory import AIServiceFactory
from ai_services.enhanced_b2b_sales_agent import EnhancedB2BSalesAgent
from ai_services.base import AIMessage

# Import models
from models.chat import MessageType, ChatRequest, ChatResponse
from models.lead import Lead

# Import services
from services.elasticsearch_service import elasticsearch_service

# Import configuration
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="B2B Sales AI Assistant",
    description="AI-powered B2B sales assistant with dynamic product intelligence",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(leads_router)
app.include_router(quotes_router, prefix="/api/quotes", tags=["quotes"])

# Keep your working models
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

@app.on_event("startup")
async def startup_event():
    """Initialize all services on startup"""
    try:
        logger.info("🚀 Starting B2B Sales AI Assistant...")
        
        # Test database connection
        if not test_connection():
            logger.error("❌ Database connection failed")
            raise Exception("Database connection failed")
        
        # Create database tables
        create_tables()
        logger.info("✅ Database initialized")
        
        # Initialize Elasticsearch
        await elasticsearch_service.initialize()
        logger.info("✅ Elasticsearch initialized")
        
        logger.info("🎉 Startup completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    await elasticsearch_service.close()

@app.get("/")
async def root():
    return {"message": "B2B Sales AI Assistant is running with dynamic product intelligence!"}

@app.post("/api/sales-chat")
async def sales_chat(request: SalesChatMessage, db: Session = Depends(get_db)):
    """Enhanced sales chat endpoint with multi-agent collaboration"""
    try:
        logger.info(f"🚀 Enhanced Sales      Chat Request: {request.message}")
        
        # Handle lead management - fix enum usage
        lead_id = request.lead_id
        if not lead_id:
            lead_id = str(uuid.uuid4())
            lead = DBLead(
                id=lead_id,
                company_name="Unknown",
                contact_name="Unknown", 
                email="unknown@example.com",
                status="NEW",  # Use uppercase to match database enum
                created_at=datetime.now()
            )
            db.add(lead)
            db.flush()
        
        # Save user message - fix enum usage
        user_message = DBChatMessage(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            message_type=MessageType.USER.value,  # Use .value to get the string
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
        
        # Create Enhanced B2B Sales Agent with Elasticsearch integration
        base_provider = AIServiceFactory.create_provider(request.provider)
        enhanced_agent = EnhancedB2BSalesAgent(base_provider)
        
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
        
        # Generate enhanced response with multi-agent collaboration
        response = await enhanced_agent.generate_response(
            messages, 
            customer_context=customer_context,
            conversation_stage=request.conversation_stage or "discovery"
        )
        
        # Save assistant response with enhanced metadata
        response_metadata = {
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
            "enhanced_sales_agent": True
        }
        
        # Add product intelligence if available
        if hasattr(enhanced_agent, 'product_recommendations'):
            response_metadata['product_recommendations'] = enhanced_agent.product_recommendations
        
        # Add quote information if generated
        if response.metadata and 'quote' in response.metadata:
            response_metadata['quote'] = response.metadata['quote']
        
        assistant_message = DBChatMessage(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            message_type=MessageType.ASSISTANT.value,  # Use .value to get the string
            content=response.content,
            stage=request.conversation_stage or "discovery",
            message_metadata=response_metadata
        )
        db.add(assistant_message)
        db.commit()
        
        # Prepare enhanced response
        chat_response = ChatResponse(
            message=response.content,
            lead_id=lead_id,
            conversation_stage=request.conversation_stage or "discovery",
            metadata={
                "enhanced_sales_agent": True,
                "provider": response.provider,
                "model": response.model,
                "usage": response.usage,
                "product_intelligence": getattr(enhanced_agent, 'product_recommendations', {}),
                "timestamp": datetime.now().isoformat()
            }
        )
        
        logger.info(f"✅ Enhanced Sales Chat Response generated for lead: {lead_id}")
        return chat_response
        
    except Exception as e:
        logger.error(f"❌ Enhanced sales chat error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Keep all your existing working endpoints
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
                # Create new lead with basic info - fix enum usage
                lead = DBLead(
                    id=lead_id,
                    company_name="Unknown",
                    contact_name="Unknown",
                    email="unknown@example.com",
                    status="NEW"  # Use uppercase to match database enum
                )
                db.add(lead)
                db.flush()
                logger.info(f"Created new lead: {lead_id}")
            
            # Save user message to database FIRST - fix enum usage
            user_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                message_type=MessageType.USER.value,  # Use .value to get the string
                content=request.message,
                stage=request.conversation_stage or "discovery"
            )
            db.add(user_message)
            db.flush()
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
            
            # Save assistant response to database - fix enum usage
            assistant_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                message_type=MessageType.ASSISTANT.value,  # Use .value to get the string
                content=response.content,
                stage=request.conversation_stage or "discovery",
                message_metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage
                }
            )
            db.add(assistant_message)
            db.commit()
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

# ... keep all your other existing endpoints ...

# Add new Elasticsearch endpoints
@app.get("/api/admin/reindex")
async def reindex_data():
    """Admin endpoint to reindex Elasticsearch data"""
    try:
        await elasticsearch_service.load_initial_data()
        return {"message": "Data reindexed successfully"}
    except Exception as e:
        logger.error(f"❌ Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/elasticsearch-status")
async def elasticsearch_status():
    """Admin endpoint to check Elasticsearch status"""
    try:
        cluster_info = await elasticsearch_service.client.info()
        
        # Get index stats
        products_stats = await elasticsearch_service.client.indices.stats(
            index=elasticsearch_service.products_index
        )
        solutions_stats = await elasticsearch_service.client.indices.stats(
            index=elasticsearch_service.solutions_index
        )
        
        return {
            "cluster_info": cluster_info,
            "indices": {
                "products": {
                    "name": elasticsearch_service.products_index,
                    "document_count": products_stats["indices"][elasticsearch_service.products_index]["total"]["docs"]["count"]
                },
                "solutions": {
                    "name": elasticsearch_service.solutions_index,
                    "document_count": solutions_stats["indices"][elasticsearch_service.solutions_index]["total"]["docs"]["count"]
                }
            },
            "status": "healthy"
        }
    except Exception as e:
        logger.error(f"❌ Elasticsearch status error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# Add the missing history management endpoints
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

@app.get("/api/conversations/{lead_id}")
async def get_conversation(lead_id: str, db: Session = Depends(get_db)):
    """Get conversation history for a lead"""
    try:
        messages = db.query(DBChatMessage).filter(
            DBChatMessage.lead_id == lead_id
        ).order_by(DBChatMessage.created_at).all()
        
        conversation = []
        for msg in messages:
            # Fix enum comparison
            role = "user" if msg.message_type == MessageType.USER.value else "assistant"
            conversation.append({
                "id": msg.id,
                "role": role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                "stage": msg.stage,
                "metadata": msg.message_metadata
            })
        
        return {"conversation": conversation}
    
    except Exception as e:
        logger.error(f"❌ Get conversation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
