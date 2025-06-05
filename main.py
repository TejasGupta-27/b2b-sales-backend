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
from routes.speech import router as speech_router

# Import AI services
from ai_services.factory import AIServiceFactory
from ai_services.enhanced_b2b_sales_agent import EnhancedB2BSalesAgent
from ai_services.hybrid_product_retriever_agent import HybridProductRetrieverAgent
from ai_services.base import AIMessage

# Import models
from models.chat import MessageType, ChatRequest, ChatResponse
from models.lead import Lead

# Import services
from services.elasticsearch_service import get_elasticsearch_service
from services.chroma_service import ChromaDBService

# Import configuration
from config import settings

# Import speech service
from services.speech_service import SpeechService
from dependencies import get_speech_service

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

# Speech service dependency
async def get_speech_service():
    """Dependency to get speech service instance."""
    service = SpeechService(model_name="medium")
    await service.initialize()
    try:
        yield service
    finally:
        await service.close()

# Include routers
app.include_router(leads_router)
app.include_router(quotes_router, prefix="/api/quotes", tags=["quotes"])
app.include_router(speech_router, prefix="/api/speech", tags=["speech"])

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

class ChatSearchRequest(BaseModel):
    query: str
    lead_id: Optional[str] = None
    limit: Optional[int] = 10
    offset: Optional[int] = 0
    use_fuzzy: Optional[bool] = False
    similarity_threshold: Optional[float] = 0.3

# Add ChromaDB service initialization
chroma_service = None

# Initialize speech service
speech_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global chroma_service, speech_service
    
    try:
        logger.info("🚀 Starting B2B Sales AI Assistant...")
        
        # Test database connection (remove await since it's not async)
        test_connection()
        
        # Create database tables
        create_tables()
        
        # Initialize Elasticsearch (with error handling)
        try:
            elasticsearch_service = get_elasticsearch_service()
            await elasticsearch_service.initialize()
            logger.info("✅ Elasticsearch initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Elasticsearch initialization failed: {e}")
            logger.info("🔄 Continuing with fallback data...")
        
        # Initialize ChromaDB if hybrid retriever is enabled
        if settings.use_hybrid_retriever and settings.azure_embedding_endpoint:
            try:
                chroma_service = ChromaDBService(
                    azure_embedding_endpoint=settings.azure_embedding_endpoint,
                    azure_embedding_key=settings.azure_embedding_api_key
                )
                await chroma_service.initialize()
                logger.info("✅ ChromaDB initialized successfully")
                
                # Check if ChromaDB is empty and needs population
                stats = await chroma_service.get_collection_stats()
                if stats["products_count"] == 0 and stats["solutions_count"] == 0:
                    logger.info("🔄 ChromaDB is empty, loading data from JSON files...")
                    result = await chroma_service.load_limited_data_from_json(max_per_file=50)
                    logger.info(f"✅ ChromaDB data loading completed: {result}")
                elif settings.force_reload_data:
                    logger.info("🔄 Force reload enabled, reloading ChromaDB data...")
                    result = await chroma_service.load_limited_data_from_json(max_per_file=50)
                    logger.info(f"✅ ChromaDB force reload completed: {result}")
                else:
                    logger.info(f"✅ ChromaDB already has data: {stats}")
                
            except Exception as chroma_error:
                logger.error(f"❌ ChromaDB initialization failed: {chroma_error}")
                chroma_service = None
                logger.info("🔄 Continuing without ChromaDB...")
        else:
            logger.info("⚠️ ChromaDB disabled or Azure embeddings not configured")
        
        logger.info("✅ Application startup completed")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        elasticsearch_service = get_elasticsearch_service()
        await elasticsearch_service.close()
        logger.info("✅ Elasticsearch connection closed")
    except Exception as e:
        logger.warning(f"⚠️ Error during shutdown: {e}")

@app.get("/")
async def root():
    return {"message": "B2B Sales AI Assistant is running with dynamic product intelligence!"}

@app.post("/api/chat")
async def sales_chat(request: SalesChatMessage, db: Session = Depends(get_db)):
    """Enhanced sales chat endpoint with hybrid retrieval"""
    try:
        # Get speech service
        speech_service = SpeechService(model_name="medium")
        await speech_service.initialize()
        
        try:
            # Handle lead management
            lead_id = request.lead_id or str(uuid.uuid4())
            if not request.lead_id:
                lead = DBLead(
                    id=lead_id,
                    company_name="Unknown",
                    contact_name="Unknown",
                    email="unknown@example.com",
                    status=LeadStatus.NEW,
                    created_at=datetime.now()
                )
                db.add(lead)
                db.commit()
                logger.info(f"Created new lead: {lead_id}")
            
            # Save user message
            user_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                message_type=MessageType.USER.value,
                content=request.message,
                stage=request.conversation_stage or "discovery"
            )
            db.add(user_message)
            db.commit()
            
            # Get conversation history
            messages = []
            existing_messages = db.query(DBChatMessage).filter(
                DBChatMessage.lead_id == lead_id
            ).order_by(DBChatMessage.created_at).all()
            
            for msg in existing_messages:
                role = "user" if msg.message_type == MessageType.USER.value else "assistant"
                messages.append(AIMessage(role=role, content=msg.content))
            
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
            
            # Create Enhanced B2B Sales Agent with better error handling
            try:
                base_provider = AIServiceFactory.create_provider(settings.default_ai_provider)
                enhanced_agent = EnhancedB2BSalesAgent(
                    base_provider=base_provider,
                    use_hybrid_retriever=settings.use_hybrid_retriever
                )
                
                # Initialize if needed
                await enhanced_agent.initialize()
                
                # Generate response with error handling
                response = await enhanced_agent.generate_response(
                    messages, 
                    customer_context=customer_context
                )
                
            except Exception as agent_error:
                logger.error(f"Agent error: {agent_error}")
                # Fallback to basic response
                base_provider = AIServiceFactory.create_provider(request.provider)
                response = await base_provider.generate_response(messages)
                
                # Add error metadata
                if not response.metadata:
                    response.metadata = {}
                response.metadata['agent_error'] = str(agent_error)
                response.metadata['fallback_used'] = True
            
            # Generate speech for the response
            speech_result = await speech_service.text_to_speech(
                text=response.content,
                language="en"  # Default to English for now
            )
            
            # Save assistant response with enhanced metadata
            response_metadata = {
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
                "enhanced_sales_agent": True,
                "speech_data": speech_result
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
                message_type=MessageType.ASSISTANT.value,
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
                    "timestamp": datetime.now().isoformat(),
                    "speech_data": speech_result
                }
            )
            
            logger.info(f"✅ Enhanced Sales Chat Response generated for lead: {lead_id}")
            return chat_response
            
        finally:
            await speech_service.close()
            
    except Exception as e:
        logger.exception("Error in sales chat endpoint")
        db.rollback()  # Add rollback on error
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Keep all your existing working endpoints
@app.get("/api/products")
async def get_products():
    """Get available products and pricing"""
    base_provider = AIServiceFactory.create_provider("azure_openai")
    sales_agent = EnhancedB2BSalesAgent(base_provider)
    
    return {"products": sales_agent.product_catalog}

@app.post("/api/generate-quote")
async def generate_quote(quote_request: Dict[str, Any]):
    """Generate a detailed quotation (legacy endpoint)"""
    base_provider = AIServiceFactory.create_provider("azure_openai")
    sales_agent = EnhancedB2BSalesAgent(base_provider)
    
    quote = await sales_agent.generate_quote(quote_request)
    return {"quote": quote}

@app.post("/api/chat/send")
async def send_message(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        # Get speech service
        speech_service = SpeechService(model_name="medium")
        await speech_service.initialize()
        
        try:
            # Handle lead management
            lead_id = request.lead_id or str(uuid.uuid4())
            if not request.lead_id:
                lead = DBLead(
                    id=lead_id,
                    company_name="Unknown",
                    contact_name="Unknown",
                    email="unknown@example.com",
                    status=LeadStatus.NEW,
                    created_at=datetime.now()
                )
                db.add(lead)
                db.commit()
                logger.info(f"Created new lead: {lead_id}")
            
            # Save user message
            user_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                message_type=MessageType.USER.value,
                content=request.message,
                stage=request.conversation_stage or "discovery"
            )
            db.add(user_message)
            db.commit()
            
            # Get conversation history
            messages = []
            existing_messages = db.query(DBChatMessage).filter(
                DBChatMessage.lead_id == lead_id
            ).order_by(DBChatMessage.created_at).all()
            
            for msg in existing_messages:
                role = "user" if msg.message_type == MessageType.USER.value else "assistant"
                messages.append(AIMessage(role=role, content=msg.content))
            
            # Get AI response
            ai_provider = AIServiceFactory.create_provider()
            response = await ai_provider.generate_response(messages)
            
            # Generate speech for the response
            speech_result = await speech_service.text_to_speech(
                text=response.content,
                language="en"  # Default to English for now
            )
            
            # Save assistant response to database
            assistant_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                message_type=MessageType.ASSISTANT.value,
                content=response.content,
                stage=request.conversation_stage or "discovery",
                message_metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage,
                    "speech_data": speech_result
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
                    "usage": response.usage,
                    "speech_data": speech_result
                }
            )
            
        finally:
            await speech_service.close()
            
    except Exception as e:
        logger.error(f"Error in send_message endpoint: {str(e)}")
        db.rollback()  # Add rollback on error
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

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

@app.get("/api/admin/data-status")
async def get_data_status():
    """Get status of loaded data"""
    try:
        stats = await elasticsearch_service.get_product_stats()
        categories = await elasticsearch_service.get_product_categories()
        
        return {
            "elasticsearch_status": "healthy",
            "product_stats": stats,
            "available_categories": categories,
            "data_source": "json_files" if stats["total_products"] > 3 else "sample_data"
        }
    except Exception as e:
        logger.error(f"❌ Data status error: {e}")
        return {
            "elasticsearch_status": "unhealthy",
            "error": str(e)
        }

@app.get("/api/debug/elasticsearch")
async def debug_elasticsearch():
    """Debug endpoint to check Elasticsearch status and data"""
    try:
        # Check connection
        info = await elasticsearch_service.client.info()
        
        # Get product count
        products_count = await elasticsearch_service.client.count(index=elasticsearch_service.products_index)
        solutions_count = await elasticsearch_service.client.count(index=elasticsearch_service.solutions_index)
        
        # Get sample products
        sample_products = await elasticsearch_service.search_products("", size=5)
        
        # Get categories
        categories = await elasticsearch_service.get_product_categories()
        
        return {
            "elasticsearch_info": info,
            "indices": {
                "products": {
                    "count": products_count['count'],
                    "index_name": elasticsearch_service.products_index
                },
                "solutions": {
                    "count": solutions_count['count'],
                    "index_name": elasticsearch_service.solutions_index
                }
            },
            "sample_products": sample_products,
            "available_categories": categories,
            "status": "healthy"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.post("/api/debug/force-reload")
async def force_reload_elasticsearch():
    """Force reload Elasticsearch data"""
    try:
        await elasticsearch_service.reindex_all_data()
        stats = await elasticsearch_service.get_product_stats()
        return {
            "message": "Data reloaded successfully",
            "stats": stats
        }
    except Exception as e:
        return {
            "error": str(e)
        }

@app.get("/api/debug/hybrid-stats")
async def get_hybrid_stats():
    """Get statistics about hybrid search capabilities"""
    try:
        stats = {
            "elasticsearch": await elasticsearch_service.get_product_stats(),
            "hybrid_enabled": settings.use_hybrid_retriever,
            "azure_embeddings_configured": bool(settings.azure_embedding_endpoint)
        }
        
        if chroma_service:
            stats["chroma"] = await chroma_service.get_collection_stats()
        
        return stats
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/sync-chroma")
async def sync_chroma_data():
    """Manually sync limited data from JSON files to ChromaDB"""
    try:
        if not chroma_service:
            return {"error": "ChromaDB not initialized"}
        
        # Use limited loading instead of full Elasticsearch sync
        result = await chroma_service.load_limited_data_from_json(max_per_file=50)
        stats = await chroma_service.get_collection_stats()
        
        return {
            "message": "ChromaDB limited sync completed (50 items per JSON file)",
            "loading_result": result,
            "stats": stats
        }
        
    except Exception as e:
        return {"error": str(e)}

# Add new endpoint for limited population
@app.post("/api/debug/populate-chroma-limited")
async def populate_chroma_limited(max_per_file: int = 50):
    """Populate ChromaDB with limited data from JSON files"""
    try:
        if not chroma_service:
            return {"error": "ChromaDB not initialized"}
        
        result = await chroma_service.load_limited_data_from_json(max_per_file=max_per_file)
        stats = await chroma_service.get_collection_stats()
        
        return {
            "message": f"ChromaDB limited population completed (max {max_per_file} per file)",
            "loading_result": result,
            "final_stats": stats
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/chroma-status")
async def get_chroma_status():
    """Get detailed ChromaDB status and perform test search"""
    try:
        if not chroma_service:
            return {
                "status": "not_initialized",
                "error": "ChromaDB service not available",
                "reason": "Either hybrid retrieval is disabled or Azure embeddings not configured"
            }
        
        # Get collection stats
        stats = await chroma_service.get_collection_stats()
        
        # Perform test searches if data exists
        test_results = {}
        if stats["products_count"] > 0:
            try:
                test_products = await chroma_service.semantic_search_products("laptop computer", n_results=3)
                test_results["product_search"] = {
                    "query": "laptop computer",
                    "results_count": len(test_products),
                    "sample_results": [p.get("name", "Unknown") for p in test_products[:3]]
                }
            except Exception as search_error:
                test_results["product_search"] = {"error": str(search_error)}
        
        if stats["solutions_count"] > 0:
            try:
                test_solutions = await chroma_service.semantic_search_solutions("business automation", n_results=3)
                test_results["solution_search"] = {
                    "query": "business automation", 
                    "results_count": len(test_solutions),
                    "sample_results": [s.get("name", "Unknown") for s in test_solutions[:3]]
                }
            except Exception as search_error:
                test_results["solution_search"] = {"error": str(search_error)}
        
        return {
            "status": "healthy",
            "stats": stats,
            "test_searches": test_results,
            "azure_endpoint_configured": bool(settings.azure_embedding_endpoint),
            "hybrid_retrieval_enabled": settings.use_hybrid_retriever
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.post("/api/chat/search")
async def search_chat_messages(request: ChatSearchRequest, db: Session = Depends(get_db)):
    """Search chat messages by content with optional fuzzy search"""
    try:
        # Build the base query
        query = db.query(DBChatMessage)
        
        # Add lead_id filter if provided
        if request.lead_id:
            query = query.filter(DBChatMessage.lead_id == request.lead_id)
        
        if request.use_fuzzy:
            # Use trigram similarity for fuzzy search
            similarity_query = text("""
                content % :search_query AND 
                similarity(content, :search_query) > :similarity_threshold
            """)
            query = query.filter(similarity_query).params(
                search_query=request.query,
                similarity_threshold=request.similarity_threshold
            )
            # Order by similarity score
            query = query.order_by(text("similarity(content, :search_query) DESC"))
        else:
            # Use full-text search
            search_query = f"to_tsquery('english', :search_query)"
            query = query.filter(text(f"to_tsvector('english', content) @@ {search_query}"))
            query = query.params(search_query=request.query.replace(' ', ' & '))
            # Order by creation time
            query = query.order_by(DBChatMessage.created_at.desc())
        
        # Get total count
        total_count = query.count()
        
        # Add pagination
        query = query.offset(request.offset).limit(request.limit)
        
        # Execute query
        messages = query.all()
        
        # Format results
        results = []
        for msg in messages:
            result = {
                "id": msg.id,
                "lead_id": msg.lead_id,
                "role": msg.message_type.value.lower(),
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "stage": msg.stage,
                "metadata": msg.message_metadata
            }
       
            if request.use_fuzzy:
                similarity_score = db.execute(
                    text("SELECT similarity(content, :query) FROM chat_messages WHERE id = :id"),
                    {"query": request.query, "id": msg.id}
                ).scalar()
                result["similarity_score"] = round(similarity_score, 3)
            
            results.append(result)
        
        return {
            "results": results,
            "total": total_count,
            "offset": request.offset,
            "limit": request.limit,
            "search_type": "fuzzy" if request.use_fuzzy else "exact"
        }
        
    except Exception as e:
        logger.error(f"Error searching chat messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching messages: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
