from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
from sqlalchemy import text, func, and_
import asyncio
import time
import psutil

# Import database components
from db.database import get_db, engine, create_tables, test_connection, reset_database, cleanup_conflicting_data
from db.models import ChatMessage as DBChatMessage, Lead as DBLead, LeadStatus, User as DBUser

# Import routes
from routes.leads import router as leads_router
from routes.quotes import router as quotes_router
from routes.speech import router as speech_router
from routes.recommendations import router as recommendations_router
from routes.admin import router as admin_router
from routes.auth import router as auth_router  # Add authentication routes

# Import AI services
from ai_services.factory import AIServiceFactory
from ai_services.simple_conversational_agent import SimpleConversationalAgent
from ai_services.quote_generation_agent import QuoteGenerationAgent
from ai_services.base import AIMessage

# Import models
from models.chat import MessageType, ChatRequest, ChatResponse
from models.lead import Lead

# Import services
from services.cache_service import get_cache_service, start_cache_cleanup_task
from services.elasticsearch_vector_service import get_elasticsearch_service
from services.elasticsearch_vector_service import get_elasticsearch_vector_service
from services.metrics_service import metrics_middleware, metrics_endpoint, get_metrics_service

# Import authentication
from services.auth_service import get_current_active_user, auth_service, check_lead_access, get_lead_access_filter

# Import configuration
from config import settings

# Import speech service
from services.speech_service import SpeechService
from dependencies import get_speech_service

# Import PDF generator
from services.pdf_generator import PDFGenerator

# Import pitch deck service
from services.pitch_deck_service import PitchDeckService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add file handler for main application logs
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
main_log_handler = logging.FileHandler(log_dir / "main.log")
main_log_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
main_log_handler.setFormatter(formatter)
logger.addHandler(main_log_handler)

# Create FastAPI app
app = FastAPI(
    title="B2B Sales AI Assistant",
    description="AI-powered B2B sales assistant with dynamic product intelligence and multi-user support",
    version="3.0.0"  # Updated version for multi-user support
)

# Add metrics middleware
app.middleware("http")(metrics_middleware)

# Add compression middleware for better response times
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - Add authentication first
app.include_router(auth_router)  # Authentication routes (no auth required)
app.include_router(leads_router)
app.include_router(quotes_router, prefix="/api/quotes", tags=["quotes"])
app.include_router(speech_router, prefix="/api/speech", tags=["speech"])
app.include_router(recommendations_router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(admin_router)

# Add metrics endpoint
app.get("/metrics")(metrics_endpoint)

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

# Add Elasticsearch Vector service initialization
vector_service = None

# Global service instances for caching
speech_service = None
ai_provider = None
conversational_agent = None
quote_agent = None
elasticsearch_service = None

# Add simple context helper function
def _add_simple_context(messages: List[AIMessage], customer_context: Optional[Dict[str, Any]]) -> List[AIMessage]:
    """Add simple context without complex analysis"""
    context_parts = []
    
    if customer_context:
        context_parts.append(f"Customer: {customer_context.get('company_name', 'Unknown')} in {customer_context.get('industry', 'business')}")
    
    context_parts.append("You are a helpful B2B sales assistant. Be conversational, friendly, and human-like. Focus on understanding customer needs and providing relevant information.")
    
    if context_parts:
        context_message = AIMessage(role="system", content=" ".join(context_parts))
        return [context_message] + messages
    
    return messages

def get_cached_ai_provider():
    """Get cached AI provider instance"""
    global ai_provider
    if ai_provider is None:
        ai_provider = AIServiceFactory.create_provider(settings.default_ai_provider)
    return ai_provider

def get_cached_conversational_agent():
    """Get cached conversational agent instance"""
    global conversational_agent
    if conversational_agent is None:
        base_provider = get_cached_ai_provider()
        conversational_agent = SimpleConversationalAgent(base_provider)
    return conversational_agent

def get_cached_quote_agent():
    """Get cached quote generation agent instance"""
    global quote_agent
    if quote_agent is None:
        base_provider = get_cached_ai_provider()
        quote_agent = QuoteGenerationAgent(base_provider)
    return quote_agent

def get_cached_speech_service():
    """Get cached speech service instance"""
    global speech_service
    return speech_service

def get_cached_elasticsearch_service():
    """Get cached elasticsearch service instance"""
    global elasticsearch_service
    if elasticsearch_service is None:
        elasticsearch_service = get_elasticsearch_service()
    return elasticsearch_service

def get_cached_vector_service():
    """Get cached vector service instance"""
    global vector_service
    return vector_service

def get_cpu_usage():
    """Get current CPU usage percentage"""
    try:
        return psutil.cpu_percent(interval=1)
    except Exception:
        return 0.0

def should_disable_speech_service():
    """Check if speech service should be disabled based on CPU usage"""
    if settings.disable_speech_service:
        return True
    
    if settings.disable_speech_on_high_cpu:
        cpu_usage = get_cpu_usage()
        if cpu_usage > settings.cpu_threshold_for_speech_disable:
            logger.warning(f"CPU usage is {cpu_usage:.1f}% - disabling speech service for performance")
            return True
    
    return False

def save_quote_to_database(quote: Dict[str, Any], lead_id: str = None, user_id: str = None, db: Session = None) -> str:
    """Save quote to database for persistence with user association"""
    try:
        from db.models import Quote
        from datetime import datetime, timedelta
        
        # Extract quote data
        quote_id = quote.get('quote_id', str(uuid.uuid4()))
        quote_number = quote.get('quote_number', f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        # Extract customer info
        customer_info = quote.get('customer_info', {})
        customer_name = customer_info.get('contact_name', 'Unknown Customer')
        customer_email = customer_info.get('email', 'unknown@example.com')
        company_name = customer_info.get('company_name', 'Unknown Company')
        
        # Extract financial data
        financials = quote.get('financials', {})
        subtotal = financials.get('subtotal', 0.0)
        tax_rate = financials.get('tax_rate', 0.0)
        tax_amount = financials.get('tax_amount', 0.0)
        total = financials.get('total', 0.0)
        currency = financials.get('currency', 'USD')
        
        # Extract line items
        line_items = quote.get('line_items', [])
        
        # Set valid until date (30 days from now)
        valid_until = datetime.now() + timedelta(days=30)
        
        # Create quote object
        db_quote = Quote(
            id=quote_id,
            quote_number=quote_number,
            lead_id=lead_id or "unknown",
            user_id=user_id,  # Associate with user
            customer_name=customer_name,
            customer_email=customer_email,
            company_name=company_name,
            items=line_items,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=total,
            currency=currency,
            valid_until=valid_until,
            terms=quote.get('terms_and_conditions', []),
            notes=quote.get('implementation_notes', []),
            pdf_filename=quote.get('pdf_path'),
            pdf_url=quote.get('pdf_url'),
            status="draft"
        )
        
        if db:
            db.add(db_quote)
            db.commit()
            db.refresh(db_quote)
            logger.info(f"✅ Quote saved to database: {quote_id} - ${total} {currency} (User: {user_id})")
            return quote_id
        else:
            logger.warning("⚠️ No database session provided, quote not saved to database")
            return quote_id
            
    except Exception as e:
        logger.error(f"❌ Failed to save quote to database: {e}")
        return quote.get('quote_id', str(uuid.uuid4()))

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global vector_service, speech_service, conversational_agent, quote_agent, elasticsearch_service
    
    try:
        logger.info("🚀 Starting B2B Sales AI Assistant...")
        
        # Test database connection first
        if not test_connection():
            logger.error("❌ Database connection failed")
            raise Exception("Database connection failed")
        
        # Clean up any conflicting data from previous setups
        cleanup_conflicting_data()
        
        # Create tables using SQLAlchemy models as source of truth
        create_tables()
        
        # Initialize cache service and start cleanup task
        cache_service = get_cache_service()
        asyncio.create_task(start_cache_cleanup_task())
        logger.info("✅ Cache service initialized")
        
        # Initialize Elasticsearch first (with error handling)
        try:
            elasticsearch_service = get_elasticsearch_service()
            await elasticsearch_service.initialize()
            logger.info("✅ Elasticsearch initialized successfully")
            
            # If hybrid retriever is enabled, the vector service is already initialized
            if settings.use_hybrid_retriever:
                vector_service = elasticsearch_service
                logger.info("✅ Vector service initialized (hybrid retriever enabled)")
            else:
                logger.info("ℹ️ Vector service not initialized (hybrid retriever disabled)")
                
        except Exception as es_error:
            logger.error(f"❌ Elasticsearch initialization failed: {es_error}")
            logger.warning("⚠️ Continuing without Elasticsearch - some features may be limited")
        
        # Initialize speech service only if not disabled
        if not should_disable_speech_service():
            try:
                speech_service = SpeechService()
                await speech_service.initialize()
                logger.info("✅ Speech service initialized")
            except Exception as speech_error:
                logger.error(f"❌ Speech service initialization failed: {speech_error}")
                logger.warning("⚠️ Continuing without speech service - text-to-speech will be disabled")
        else:
            logger.info("ℹ️ Speech service disabled for performance optimization")
        
        # Pre-initialize AI agents for better performance
        try:
            # Initialize conversational agent
            conversational_agent = get_cached_conversational_agent()
            await conversational_agent.initialize()
            logger.info("✅ Conversational agent pre-initialized")
            
            # Initialize quote agent
            quote_agent = get_cached_quote_agent()
            logger.info("✅ Quote generation agent pre-initialized")
            
        except Exception as ai_error:
            logger.error(f"❌ AI agent initialization failed: {ai_error}")
            logger.warning("⚠️ AI agents will be initialized on first request")
        
        # Start periodic metrics update task
        asyncio.create_task(periodic_metrics_update())
        logger.info("✅ Metrics update task started")
        
        logger.info("🎉 B2B Sales AI Assistant startup completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

async def periodic_metrics_update():
    """Periodically update lead and database metrics"""
    while True:
        try:
            await asyncio.sleep(60)  # Update every minute
            
            # Get database session
            db = next(get_db())
            try:
                metrics_service = get_metrics_service()
                
                # Update lead metrics
                metrics_service.update_lead_metrics(db)
                
                # Update database connection metrics
                metrics_service.update_db_connection_metrics(db)
                
                # Update token usage metrics
                metrics_service.update_token_usage_metrics()
                
                # Update organization metrics
                metrics_service.update_organization_metrics(db)
                
                # Update user metrics
                metrics_service.update_user_metrics(db)
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in periodic metrics update: {e}")
            await asyncio.sleep(60)  # Wait before retrying

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        elasticsearch_service = get_elasticsearch_service()
        await elasticsearch_service.close()
        logger.info("✅ Elasticsearch connection closed")
        if speech_service:
            await speech_service.close()
            logger.info("✅ SpeechService closed")
    except Exception as e:
        logger.warning(f"⚠️ Error during shutdown: {e}")

@app.get("/")
async def root():
    return {"message": "B2B Sales AI Assistant is running with dynamic product intelligence!"}

@app.post("/api/chat")
async def sales_chat(
    request: SalesChatMessage, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Optimized sales chat endpoint with reduced latency and user authentication"""
    metrics_service = get_metrics_service()
    start_time = time.time()
    
    try:
        # Get cached speech service
        speech_service = get_cached_speech_service()
        
        try:
            # Handle lead management - Associate with current user
            lead_id = request.lead_id or str(uuid.uuid4())
            if not request.lead_id:
                # Create new lead associated with current user and organization
                lead = DBLead(
                    id=lead_id,
                    company_name="Unknown",
                    contact_name="Unknown",
                    email="unknown@example.com",
                    status=LeadStatus.NEW,
                    assigned_user_id=current_user.id,  # Associate with current user
                    organization_id=current_user.organization_id,  # Associate with user's organization
                    created_at=datetime.now()
                )
                db.add(lead)
                db.commit()
                logger.info(f"Created new lead: {lead_id} for user: {current_user.id}")
                
                # Update lead metrics immediately after creation
                metrics_service.update_lead_metrics(db)
            else:
                # Verify user has access to this lead using role-based access control
                existing_lead = check_lead_access(lead_id, current_user, db)
            
            # Save user message with user association
            user_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                user_id=current_user.id,  # Associate with current user
                message_type=MessageType.USER.value,
                content=request.message,
                stage=request.conversation_stage or "discovery"
            )
            db.add(user_message)
            db.commit()
            
            # Record chat message metric
            metrics_service.record_chat_message(lead_id=lead_id, message_type="user")
            
            # Record AI token usage for the user
            auth_service.record_api_usage(current_user.id, ai_tokens=0, db=db)
            
            # Get conversation history with role-based filtering
            lead_filters = get_lead_access_filter(current_user)
            
            messages = []
            existing_messages = db.query(DBChatMessage).join(DBLead).filter(
                DBChatMessage.lead_id == lead_id,
                *lead_filters  # Apply role-based filtering
            ).order_by(DBChatMessage.created_at.desc()).limit(10).all()  # Reduced to last 10 messages
            
            # Reverse to get chronological order
            for msg in reversed(existing_messages):
                role = "user" if msg.message_type == MessageType.USER.value else "assistant"
                messages.append(AIMessage(role=role, content=msg.content))
            
            # Get customer context from the lead
            customer_context = None
            lead_record = db.query(DBLead).filter(
                DBLead.id == lead_id,
                *lead_filters  # Apply role-based filtering
            ).first()
            if lead_record:
                customer_context = {
                    "company_name": lead_record.company_name,
                    "contact_name": lead_record.contact_name,
                    "email": lead_record.email,
                    "company_size": getattr(lead_record, 'company_size', None),
                    "industry": getattr(lead_record, 'industry', None),
                    "budget_range": getattr(lead_record, 'budget_range', None),
                    "timeline": getattr(lead_record, 'decision_timeline', None),
                    "user_organization": current_user.organization.name if current_user.organization else "Unknown"
                }
            
            # Check cache first for similar conversations (user-specific cache key)
            cache_service = get_cache_service()
            cache_key = f"chat_response:{current_user.id}:{hash(request.message + str(customer_context))}"
            cached_response = await cache_service.get(cache_key)
            
            if cached_response:
                logger.info("✅ Serving response from cache")
                response_content = cached_response
                response_metadata = {"cached": True, "provider": "cache", "user_id": current_user.id}
                metrics_service.record_cache_hit()
            else:
                # Record cache miss
                metrics_service.record_cache_miss()
                
                # Use cached conversational agent
                conversational_agent = get_cached_conversational_agent()
                
                # Initialize the agent if needed (should be pre-initialized)
                if not hasattr(conversational_agent, '_initialized'):
                    await conversational_agent.initialize()
                    conversational_agent._initialized = True
                
                # Let the conversational agent handle all types of requests naturally
                ai_start_time = time.time()
                response = await conversational_agent.generate_response(
                    messages, customer_context
                )
                ai_duration = time.time() - ai_start_time
                
                # Record AI token usage
                if hasattr(response, 'usage') and response.usage:
                    total_tokens = response.usage.get('total_tokens', 0)
                    auth_service.record_api_usage(current_user.id, ai_tokens=total_tokens, db=db)
                
                # Record AI response time
                metrics_service.record_ai_response_time(
                    duration=ai_duration,
                    provider=response.provider,
                    model=response.model
                )
                
                response_content = response.content
                response_metadata = {
                    "provider": response.provider,
                    "model": response.model,
                    "usage": response.usage,
                    "agent_type": "simple_conversational",
                    "cached": False,
                    "user_id": current_user.id,
                    "organization_id": current_user.organization_id
                }
                
                # Cache the response for 2 minutes (user-specific)
                await cache_service.set(cache_key, response_content, ttl=120)
            
            # Generate speech in parallel (non-blocking) only if speech service is available
            speech_result = None
            if speech_service:
                try:
                    speech_task = asyncio.create_task(
                        speech_service.text_to_speech(text=response_content, language="en")
                    )
                    
                    # Wait for speech generation first
                    speech_result = await speech_task
                    logger.info(f"🎤 Speech generated for response: {len(speech_result.get('audio_data', ''))} chars")
                    
                    # Update metadata with speech data
                    response_metadata['speech_data'] = speech_result
                except Exception as speech_error:
                    logger.warning(f"Speech generation failed: {speech_error}")
                    response_metadata['speech_error'] = str(speech_error)
            
            # Save assistant response with speech data included and user association
            assistant_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                user_id=current_user.id,  # Associate with current user
                message_type=MessageType.ASSISTANT.value,
                content=response_content,
                stage=request.conversation_stage or "discovery",
                message_metadata=response_metadata
            )
            db.add(assistant_message)
            db.commit()
            logger.info(f"💾 Assistant message saved with speech data: {assistant_message.id} (User: {current_user.id})")
            
            # Record assistant message metric
            metrics_service.record_chat_message(lead_id=lead_id, message_type="assistant")
            
            # Prepare enhanced response
            chat_response = ChatResponse(
                message=response_content,
                lead_id=lead_id,
                conversation_stage=request.conversation_stage or "discovery",
                metadata=response_metadata
            )
            
            logger.info(f"✅ Optimized Sales Chat Response generated for lead: {lead_id} (User: {current_user.id})")
            return chat_response
            
        finally:
            pass
            
    except Exception as e:
        logger.exception("Error in optimized sales chat endpoint")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Keep all your existing working endpoints
@app.get("/api/products")
async def get_products():
    """Get products with caching for improved performance"""
    cache_service = get_cache_service()
    
    # Try to get from cache first
    cached_products = await cache_service.get("products_list")
    if cached_products:
        logger.info("Serving products from cache")
        return cached_products
    
    try:
        elasticsearch_service = get_elasticsearch_service()
        products = await elasticsearch_service.get_random_products(size=50)
        
        # Cache for 5 minutes
        await cache_service.set("products_list", products, ttl=300)
        
        return products
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        return []

@app.post("/api/generate-quote")
async def generate_quote(quote_request: Dict[str, Any]):
    """Generate a detailed quotation and pitch deck using QuoteGenerationAgent"""
    metrics_service = get_metrics_service()
    start_time = time.time()
    
    try:
        # Use cached quote generation agent
        quote_agent = get_cached_quote_agent()
        
        # Extract conversation messages from the request
        conversation_messages = quote_request.get('conversation_messages', [])
        customer_context = quote_request.get('customer_context', {})
        
        # If no conversation messages provided, create a basic one from the request
        if not conversation_messages:
            requirements = quote_request.get('requirements', {})
            customer_info = quote_request.get('customer_info', {})
            
            # Create a basic conversation message from the requirements
            basic_message = f"Customer needs: {requirements.get('description', 'Business technology solution')}"
            if customer_info.get('company_name'):
                basic_message += f" for {customer_info['company_name']}"
            if customer_info.get('industry'):
                basic_message += f" in {customer_info['industry']} industry"
            
            conversation_messages = [AIMessage(role="user", content=basic_message)]
        
        # Generate the quote using the QuoteGenerationAgent
        quote = await quote_agent.generate_quote_from_conversation(
            conversation_messages=conversation_messages,
            customer_context=customer_context
        )
        
        # Check if quote generation was successful
        if not quote:
            metrics_service.record_quote_generation(status="failed")
            raise HTTPException(status_code=500, detail="Quote generation failed - no quote returned")
        
        # Record comprehensive quote metrics
        try:
            # Extract quote details for metrics
            quote_data = {
                'total_value': quote.get('financials', {}).get('total', 0.0) if quote.get('financials') else quote.get('total_amount', 0.0),
                'currency': quote.get('financials', {}).get('currency', 'USD') if quote.get('financials') else quote.get('currency', 'USD'),
                'line_items': quote.get('line_items', []),
                'quote_requested_at': quote.get('created_at', datetime.now().isoformat()),
                'generated_at': datetime.now().isoformat()
            }
            
            # Record detailed quote metrics
            metrics_service.record_quote_with_details(quote_data)
            
            # Record sales velocity metrics
            metrics_service.record_sales_velocity(
                metric_type="quote_generation_rate",
                value=1.0  # Increment counter
            )
            
            # Record average quote value
            if quote_data['total_value'] > 0:
                metrics_service.record_average_quote_value(
                    category="general",
                    period="daily",
                    average_value=quote_data['total_value']
                )
            
            # Record quote request to generation time
            if 'quote_requested_at' in quote_data:
                try:
                    request_time = datetime.fromisoformat(quote_data['quote_requested_at'])
                    generation_time = datetime.fromisoformat(quote_data['generated_at'])
                    duration_seconds = (generation_time - request_time).total_seconds()
                    metrics_service.record_quote_request_to_generation(
                        lead_id="quote_generation",
                        duration_seconds=duration_seconds
                    )
                except:
                    pass  # Skip if timestamp parsing fails
            
            # Record cross-sell and upsell opportunities if detected
            line_items = quote_data.get('line_items', [])
            categories = [item.get('category', 'unknown') for item in line_items]
            
            if len(set(categories)) > 1:
                # Multiple categories indicate cross-sell opportunity
                for i, category1 in enumerate(categories):
                    for category2 in categories[i+1:]:
                        if category1 != category2:
                            metrics_service.record_cross_sell_opportunity(
                                primary_category=category1,
                                cross_sell_category=category2
                            )
            
            # Record customer satisfaction (estimated based on quote generation success)
            if quote.get('pdf_generated'):
                metrics_service.record_customer_satisfaction(
                    lead_id="quote_generation",
                    interaction_type="quote_generation",
                    satisfaction_score=0.8  # High satisfaction for successful quote generation
                )
            
            logger.info(f"📊 Recorded comprehensive quote metrics: {len(line_items)} line items, ${quote_data['total_value']} {quote_data['currency']}")
            
        except Exception as quote_metrics_error:
            logger.warning(f"⚠️ Failed to record quote metrics: {quote_metrics_error}")
        
        if 'error' in quote:
            metrics_service.record_quote_generation(status="failed")
            raise HTTPException(status_code=500, detail=quote['error'])
        
        # Record successful quote generation
        metrics_service.record_quote_generation(status="success")
        
        # Save quote to database for persistence
        try:
            save_quote_to_database(quote, lead_id=None, user_id=None, db=None)
        except Exception as db_error:
            logger.warning(f"⚠️ Failed to save quote to database: {db_error}")
        
        # Generate unique IDs
        quote_id = quote.get('quote_id', str(uuid.uuid4()))
        deck_id = str(uuid.uuid4())
        
        # Generate pitch deck if quote was successful
        pitch_deck_path = None
        if quote.get('pdf_generated'):
            try:
                # Generate pitch deck
                pitch_deck_service = PitchDeckService()
                deck_structure = await pitch_deck_service.extract_ppt_structure(quote.get('quote_text', ''))
                
                # Generate the pitch deck
                deck_path = f"Data/pitch_decks/pitch_deck_{deck_id}.pptx"
                os.makedirs(os.path.dirname(deck_path), exist_ok=True)
                
                # Generate the PowerPoint file
                await pitch_deck_service.generate_ppt(deck_structure, deck_path)
                pitch_deck_path = deck_path
            except Exception as deck_error:
                logger.warning(f"Pitch deck generation failed: {deck_error}")
        
        return {
            "quote": quote,
            "quote_id": quote_id,
            "quote_link": quote.get('pdf_url', f"/api/quotes/download-pdf/{quote_id}"),
            "pitch_deck_id": deck_id if pitch_deck_path else None,
            "pitch_deck_link": f"/api/quotes/download-pitch-deck/{deck_id}" if pitch_deck_path else None,
            "generated_by": "QuoteGenerationAgent",
            "pdf_generated": quote.get('pdf_generated', False),
            "pdf_path": quote.get('pdf_path'),
            "generation_method": quote.get('generation_method', 'unknown')
        }
    except Exception as e:
        logger.error(f"Quote generation failed: {e}")
        metrics_service.record_quote_generation(status="error")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/send")
async def send_message(
    request: ChatRequest, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Send message endpoint with user authentication and organization isolation"""
    metrics_service = get_metrics_service()
    
    try:
        # Get cached speech service
        speech_service = get_cached_speech_service()
        
        try:
            # Handle lead management - Associate with current user
            lead_id = request.lead_id or str(uuid.uuid4())
            if not request.lead_id:
                # Create new lead associated with current user and organization
                lead = DBLead(
                    id=lead_id,
                    company_name="Unknown",
                    contact_name="Unknown",
                    email="unknown@example.com",
                    status=LeadStatus.NEW,
                    assigned_user_id=current_user.id,  # Associate with current user
                    organization_id=current_user.organization_id,  # Associate with user's organization
                    created_at=datetime.now()
                )
                db.add(lead)
                db.commit()
                logger.info(f"Created new lead: {lead_id} for user: {current_user.id}")
                
                # Update lead metrics immediately after creation
                metrics_service.update_lead_metrics(db)
            else:
                # Verify user has access to this lead using role-based access control
                existing_lead = check_lead_access(lead_id, current_user, db)
            
            # Save user message with user association
            user_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                user_id=current_user.id,  # Associate with current user
                message_type=MessageType.USER.value,
                content=request.message,
                stage=request.conversation_stage or "discovery"
            )
            db.add(user_message)
            db.commit()
            
            # Record user message metric
            metrics_service.record_chat_message(lead_id=lead_id, message_type="user")
            
            # Get conversation history with role-based filtering
            lead_filters = get_lead_access_filter(current_user)
            
            messages = []
            existing_messages = db.query(DBChatMessage).join(DBLead).filter(
                DBChatMessage.lead_id == lead_id,
                *lead_filters  # Apply role-based filtering
            ).order_by(DBChatMessage.created_at).limit(20).all()  # Limit to last 20 messages
            
            for msg in existing_messages:
                role = "user" if msg.message_type == MessageType.USER.value else "assistant"
                messages.append(AIMessage(role=role, content=msg.content))
            
            # Get AI response using cached provider
            ai_provider = get_cached_ai_provider()
            ai_start_time = time.time()
            response = await ai_provider.generate_response(messages)
            ai_duration = time.time() - ai_start_time
            
            # Record AI token usage
            if hasattr(response, 'usage') and response.usage:
                total_tokens = response.usage.get('total_tokens', 0)
                auth_service.record_api_usage(current_user.id, ai_tokens=total_tokens, db=db)
            
            # Record AI response time
            metrics_service.record_ai_response_time(
                duration=ai_duration,
                provider=response.provider,
                model=response.model
            )
            
            # Generate speech for the response only if speech service is available
            speech_result = None
            if speech_service:
                try:
                    speech_result = await speech_service.text_to_speech(
                        text=response.content,
                        language="en"  # Default to English for now
                    )
                except Exception as speech_error:
                    logger.warning(f"Speech generation failed: {speech_error}")
            
            # Save assistant response to database with user association
            assistant_message = DBChatMessage(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                user_id=current_user.id,  # Associate with current user
                message_type=MessageType.ASSISTANT.value,
                content=response.content,
                stage=request.conversation_stage or "discovery",
                message_metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage,
                    "speech_data": speech_result,
                    "user_id": current_user.id,
                    "organization_id": current_user.organization_id
                }
            )
            db.add(assistant_message)
            db.commit()
            logger.info(f"Saved assistant message to database: {assistant_message.id} (User: {current_user.id})")
            
            # Record assistant message metric
            metrics_service.record_chat_message(lead_id=lead_id, message_type="assistant")
            
            return ChatResponse(
                message=response.content,
                lead_id=lead_id,
                conversation_stage=request.conversation_stage or "discovery",
                metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage,
                    "speech_data": speech_result,
                    "user_id": current_user.id,
                    "organization_id": current_user.organization_id
                }
            )
            
        finally:
            pass
            
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
async def get_chat_history(
    lead_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get chat history for a specific lead with role-based access control"""
    try:
        logger.info(f"Fetching chat history for lead: {lead_id} (User: {current_user.id})")
        
        # Verify user has access to this lead using role-based access control
        lead = check_lead_access(lead_id, current_user, db)
        
        # Get messages for this lead
        messages = db.query(DBChatMessage).filter(
            DBChatMessage.lead_id == lead_id
        ).order_by(DBChatMessage.created_at).all()
        
        logger.info(f"Found {len(messages)} messages for lead {lead_id}")
        
        history = []
        for msg in messages:
            metadata = msg.message_metadata or {}
            
            # Extract voice data from metadata
            voice_data = None
            has_voice = False
            
            # For assistant messages, get speech_data
            if msg.message_type == MessageType.ASSISTANT.value:
                speech_data = metadata.get('speech_data') or metadata.get('speech_metadata')
                if speech_data and speech_data.get('audio_data'):
                    voice_data = speech_data
                    has_voice = True
                    logger.debug(f"🎤 Found voice data for assistant message {msg.id}: {len(speech_data.get('audio_data', ''))} chars")
                else:
                    logger.debug(f"⚠️ No voice data found for assistant message {msg.id}")
            
            # For user messages, get transcription metadata
            elif msg.message_type == MessageType.USER.value:
                transcription_metadata = metadata.get('transcription_metadata')
                if transcription_metadata:
                    voice_data = {
                        "type": "transcription",
                        "data": transcription_metadata
                    }
                    has_voice = True
                    logger.debug(f"🎤 Found transcription data for user message {msg.id}")
                else:
                    logger.debug(f"⚠️ No transcription data found for user message {msg.id}")
            
            history.append({
                "id": msg.id,
                "role": msg.message_type.value.lower(),
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "stage": msg.stage,
                "metadata": metadata,
                "has_voice": has_voice,
                "voice_data": voice_data,
                "user_id": msg.user_id  # Include user who sent the message
            })
        
        logger.info(f"Returning chat history with voice data: {len([h for h in history if h['has_voice']])} voice messages")
        return {"history": history}
            
    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}")
        return {"history": []}

@app.get("/api/leads")
async def get_leads(
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get leads based on user role - sales agents see only their assigned leads, managers see all organization leads"""
    try:
        # Use a single JOIN query instead of N+1 individual queries
        from sqlalchemy import func, and_
        
        # Get role-based filters
        lead_filters = get_lead_access_filter(current_user)
        
        # Subquery to get the latest message timestamp for each lead
        latest_message_subquery = db.query(
            DBChatMessage.lead_id,
            func.max(DBChatMessage.created_at).label('latest_time')
        ).group_by(DBChatMessage.lead_id).subquery()
        
        # Main query with JOIN to get leads and their latest messages - filtered by role
        results = db.query(
            DBLead,
            DBChatMessage.content.label('last_message_content'),
            DBChatMessage.created_at.label('last_message_time')
        ).filter(
            *lead_filters  # Apply role-based filtering
        ).outerjoin(
            latest_message_subquery,
            DBLead.id == latest_message_subquery.c.lead_id
        ).outerjoin(
            DBChatMessage,
            and_(
                DBChatMessage.lead_id == DBLead.id,
                DBChatMessage.created_at == latest_message_subquery.c.latest_time
            )
        ).all()
        
        # Format results
        formatted_results = []
        for lead, last_message_content, last_message_time in results:
            formatted_results.append({
                "id": lead.id,
                "company_name": lead.company_name,
                "contact_name": lead.contact_name,
                "email": lead.email,
                "status": lead.status,
                "assigned_user_id": lead.assigned_user_id,
                "created_at": lead.created_at.isoformat(),
                "last_message": last_message_content,
                "last_message_time": last_message_time.isoformat() if last_message_time else None
            })
        
        logger.info(f"Returning {len(formatted_results)} leads for organization: {current_user.organization_id}")
        return {"leads": formatted_results}
            
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
async def get_conversation(
    lead_id: str, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get conversation history for a lead with role-based access control"""
    try:
        # Verify user has access to this lead using role-based access control
        lead = check_lead_access(lead_id, current_user, db)
        
        messages = db.query(DBChatMessage).filter(
            DBChatMessage.lead_id == lead_id
        ).order_by(DBChatMessage.created_at).all()
        
        conversation = []
        for msg in messages:
            # Fix enum comparison
            role = "user" if msg.message_type == MessageType.USER.value else "assistant"
            
            metadata = msg.message_metadata or {}
            
            # Extract voice data from metadata
            voice_data = None
            has_voice = False
            
            # For assistant messages, get speech_data
            if msg.message_type == MessageType.ASSISTANT.value:
                speech_data = metadata.get('speech_data') or metadata.get('speech_metadata')
                if speech_data and speech_data.get('audio_data'):
                    voice_data = speech_data
                    has_voice = True
            
            # For user messages, get transcription metadata
            elif msg.message_type == MessageType.USER.value:
                transcription_metadata = metadata.get('transcription_metadata')
                if transcription_metadata:
                    voice_data = {
                        "type": "transcription",
                        "data": transcription_metadata
                    }
                    has_voice = True
            
            conversation.append({
                "id": msg.id,
                "role": role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                "stage": msg.stage,
                "metadata": metadata,
                "has_voice": has_voice,
                "voice_data": voice_data,
                "user_id": msg.user_id  # Include user who sent the message
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
        
        if vector_service:
            stats["vector_service"] = await vector_service.get_collection_stats()
        
        return stats
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/sync-vector")
async def sync_vector_data():
    """Manually sync limited data from JSON files to Elasticsearch Vector Service with duplicate prevention"""
    try:
        if not vector_service:
            return {"error": "Elasticsearch Vector Service not initialized"}
        
        # Use safe sync method to prevent duplicates
        result = await vector_service.sync_data_safely(max_per_file=50, clear_existing=False)
        stats = await vector_service.get_collection_stats()
        
        return {
            "message": "Elasticsearch Vector Service safe sync completed (prevents duplicates)",
            "sync_result": result,
            "final_stats": stats
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/sync-vector-force")
async def sync_vector_data_force():
    """Force sync Elasticsearch Vector Service data by clearing existing and reloading"""
    try:
        if not vector_service:
            return {"error": "Elasticsearch Vector Service not initialized"}
        
        # Clear existing data and reload
        result = await vector_service.sync_data_safely(max_per_file=50, clear_existing=True)
        stats = await vector_service.get_collection_stats()
        
        return {
            "message": "Elasticsearch Vector Service force sync completed (cleared and reloaded)",
            "sync_result": result,
            "final_stats": stats
        }
        
    except Exception as e:
        return {"error": str(e)}

# Add new endpoint for limited population
@app.post("/api/debug/populate-vector-limited")
async def populate_vector_limited(max_per_file: int = 50):
    """Populate Elasticsearch Vector Service with limited data from JSON files"""
    try:
        if not vector_service:
            return {"error": "Elasticsearch Vector Service not initialized"}
        
        result = await vector_service.load_data_from_json(max_per_file=max_per_file)
        stats = await vector_service.get_collection_stats()
        
        return {
            "message": f"Elasticsearch Vector Service limited population completed (max {max_per_file} per file)",
            "loading_result": result,
            "final_stats": stats
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/vector-status")
async def get_vector_status():
    """Get detailed Elasticsearch Vector Service status and perform test search"""
    try:
        if not settings.enable_debug_vector_endpoints:
            return {
                "status": "disabled",
                "message": "Debug vector endpoints are disabled (ENABLE_DEBUG_VECTOR_ENDPOINTS=false)"
            }
            
        if not vector_service:
            return {
                "status": "not_initialized",
                "error": "Elasticsearch Vector Service not available",
                "reason": "Either hybrid retrieval is disabled or Azure embeddings not configured"
            }
        
        # Get collection stats
        stats = await vector_service.get_collection_stats()
        
        # Perform test searches if data exists and testing is enabled
        test_results = {}
        if stats["products_count"] > 0:
            try:
                test_products = await vector_service.semantic_search_products("laptop computer", n_results=3)
                test_results["product_search"] = {
                    "query": "laptop computer",
                    "results_count": len(test_products),
                    "sample_results": [p.get("name", "Unknown") for p in test_products[:3]]
                }
            except Exception as search_error:
                test_results["product_search"] = {"error": str(search_error)}
        
        if stats["solutions_count"] > 0:
            try:
                test_solutions = await vector_service.semantic_search_solutions("business automation", n_results=3)
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
async def search_chat_messages(
    request: ChatSearchRequest, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search chat messages by content with optional fuzzy search and role-based access control"""
    try:
        # Get role-based filters for leads
        lead_filters = get_lead_access_filter(current_user)
        
        # Build the base query with role-based filtering
        query = db.query(DBChatMessage).join(DBLead).filter(
            *lead_filters  # Apply role-based filtering instead of just organization
        )
        
        # Add lead_id filter if provided (and verify access)
        if request.lead_id:
            # Verify user has access to this lead using role-based access control
            lead = check_lead_access(request.lead_id, current_user, db)
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
                "user_id": msg.user_id,
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
            "search_type": "fuzzy" if request.use_fuzzy else "exact",
            "organization_id": current_user.organization_id
        }
        
    except Exception as e:
        logger.error(f"Error searching chat messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching messages: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/admin/performance")
async def get_performance_stats():
    """Get comprehensive performance statistics"""
    try:
        # Get cache statistics
        cache_service = get_cache_service()
        cache_stats = await cache_service.get_stats()
        
        # Get database connection pool stats
        db_pool_stats = {
            "pool_size": engine.pool.size(),
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
            "invalid": engine.pool.invalid()
        }
        
        # Test Elasticsearch health
        try:
            elasticsearch_service = get_elasticsearch_service()
            es_health = await elasticsearch_service.get_cluster_health()
        except Exception as e:
            es_health = {"status": "error", "error": str(e)}
        
        # Calculate performance metrics
        performance_metrics = {
            "timestamp": datetime.now().isoformat(),
            "cache": {
                "hit_rate": f"{(cache_stats['active_entries'] / max(cache_stats['total_entries'], 1)) * 100:.1f}%",
                "total_entries": cache_stats['total_entries'],
                "active_entries": cache_stats['active_entries'],
                "cache_size_mb": f"{cache_stats['cache_size_mb']:.2f}MB"
            },
            "database": {
                "connection_pool": db_pool_stats,
                "pool_utilization": f"{(db_pool_stats['checked_out'] / max(db_pool_stats['pool_size'], 1)) * 100:.1f}%"
            },
            "elasticsearch": es_health,
            "system": {
                "optimization_status": "enabled",
                "conversational_agent": "active",
                "caching_enabled": settings.enable_response_caching,
                "hybrid_retriever": settings.use_hybrid_retriever
            },
            "recommendations": []
        }
        
        # Add performance recommendations
        if db_pool_stats['checked_out'] > db_pool_stats['pool_size'] * 0.8:
            performance_metrics["recommendations"].append("High database connection usage - consider increasing pool size")
        
        if cache_stats['total_entries'] > 1000:
            performance_metrics["recommendations"].append("Large cache size - consider reducing TTL or implementing cache eviction")
        
        if es_health.get('status') != 'green':
            performance_metrics["recommendations"].append("Elasticsearch cluster not healthy - check cluster status")
        
        return performance_metrics
        
    except Exception as e:
        logger.error(f"Error getting performance stats: {e}")
        return {"error": str(e)}

@app.post("/api/generate-quote-from-conversation/{lead_id}")
async def generate_quote_from_conversation(
    lead_id: str, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate a quote from existing conversation history with role-based access control"""
    metrics_service = get_metrics_service()
    start_time = time.time()
    
    try:
        # Verify user has access to this lead using role-based access control
        lead = check_lead_access(lead_id, current_user, db)
        
        # Get conversation history for the lead (only from accessible leads)
        messages = db.query(DBChatMessage).filter(
            DBChatMessage.lead_id == lead_id
        ).order_by(DBChatMessage.created_at).all()
        
        if not messages:
            metrics_service.record_quote_generation(status="failed")
            raise HTTPException(status_code=404, detail="No conversation history found for this lead")
        
        # Convert to AIMessage format
        conversation_messages = []
        for msg in messages:
            role = "user" if msg.message_type == MessageType.USER.value else "assistant"
            conversation_messages.append(AIMessage(role=role, content=msg.content))
        
        # Get customer context from lead (already verified accessible)
        lead_record = lead  # We already have the lead from check_lead_access
        customer_context = None
        if lead_record:
            customer_context = {
                "company_name": lead_record.company_name,
                "contact_name": lead_record.contact_name,
                "email": lead_record.email,
                "company_size": getattr(lead_record, 'company_size', None),
                "industry": getattr(lead_record, 'industry', None),
                "budget_range": getattr(lead_record, 'budget_range', None),
                "timeline": getattr(lead_record, 'decision_timeline', None),
                "user_organization": current_user.organization.name if current_user.organization else "Unknown"
            }
        
        # Use cached quote generation agent
        quote_agent = get_cached_quote_agent()
        
        # Generate the quote using the QuoteGenerationAgent
        quote = await quote_agent.generate_quote_from_conversation(
            conversation_messages=conversation_messages,
            customer_context=customer_context
        )
        
        # Check if quote generation was successful
        if not quote:
            metrics_service.record_quote_generation(status="failed")
            raise HTTPException(status_code=500, detail="Quote generation failed - no quote returned")
        
        if 'error' in quote:
            metrics_service.record_quote_generation(status="failed")
            raise HTTPException(status_code=500, detail=quote['error'])
        
        # Record successful quote generation
        metrics_service.record_quote_generation(status="success")
        
        # Record AI token usage
        if hasattr(quote, 'usage') and quote.usage:
            total_tokens = quote.usage.get('total_tokens', 0)
            auth_service.record_api_usage(current_user.id, ai_tokens=total_tokens, db=db)
        
        # Save quote to database for persistence
        try:
            save_quote_to_database(quote, lead_id=lead_id, user_id=current_user.id, db=db)
        except Exception as db_error:
            logger.warning(f"⚠️ Failed to save quote to database: {db_error}")
        
        # Generate pitch deck if quote was successful
        deck_id = str(uuid.uuid4())
        pitch_deck_path = None
        if quote.get('pdf_generated'):
            try:
                # Generate pitch deck
                pitch_deck_service = PitchDeckService()
                deck_structure = await pitch_deck_service.extract_ppt_structure(quote.get('quote_text', ''))
                
                # Generate the pitch deck
                deck_path = f"Data/pitch_decks/pitch_deck_{deck_id}.pptx"
                os.makedirs(os.path.dirname(deck_path), exist_ok=True)
                
                # Generate the PowerPoint file
                await pitch_deck_service.generate_ppt(deck_structure, deck_path)
                pitch_deck_path = deck_path
            except Exception as deck_error:
                logger.warning(f"Pitch deck generation failed: {deck_error}")
        
        return {
            "quote": quote,
            "lead_id": lead_id,
            "user_id": current_user.id,
            "organization_id": current_user.organization_id,
            "conversation_messages_count": len(conversation_messages),
            "quote_link": quote.get('pdf_url', f"/api/quotes/download-pdf/{quote.get('quote_id', 'unknown')}"),
            "pitch_deck_id": deck_id if pitch_deck_path else None,
            "pitch_deck_link": f"/api/quotes/download-pitch-deck/{deck_id}" if pitch_deck_path else None,
            "generated_by": "QuoteGenerationAgent",
            "pdf_generated": quote.get('pdf_generated', False),
            "pdf_path": quote.get('pdf_path'),
            "generation_method": quote.get('generation_method', 'unknown')
        }
    except Exception as e:
        logger.error(f"Quote generation from conversation failed: {e}")
        metrics_service.record_quote_generation(status="error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/system-performance")
async def get_system_performance():
    """Get system performance metrics including CPU usage"""
    try:
        cpu_usage = get_cpu_usage()
        memory = psutil.virtual_memory()
        
        # Get database connection pool stats
        db_pool_stats = {
            "pool_size": engine.pool.size(),
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
            "invalid": engine.pool.invalid()
        }
        
        # Check if speech service should be disabled
        speech_disabled = should_disable_speech_service()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_usage_percent": cpu_usage,
                "memory_usage_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "memory_total_gb": memory.total / (1024**3)
            },
            "database": {
                "connection_pool": db_pool_stats,
                "pool_utilization": f"{(db_pool_stats['checked_out'] / max(db_pool_stats['pool_size'], 1)) * 100:.1f}%"
            },
            "services": {
                "speech_service_enabled": speech_service is not None and not speech_disabled,
                "speech_service_disabled_reason": "CPU threshold exceeded" if speech_disabled and cpu_usage > settings.cpu_threshold_for_speech_disable else None,
                "conversational_agent_initialized": conversational_agent is not None,
                "quote_agent_initialized": quote_agent is not None,
                "elasticsearch_initialized": elasticsearch_service is not None
            },
            "performance_recommendations": []
        }
        
    except Exception as e:
        logger.error(f"Error getting system performance: {e}")
        return {"error": str(e)}

@app.get("/api/admin/sales-metrics")
async def get_sales_metrics():
    """Get comprehensive sales metrics for dashboard and analytics"""
    try:
        metrics_service = get_metrics_service()
        
        # Get current metrics from Prometheus
        metrics_data = metrics_service.get_metrics()
        
        # Parse metrics string to extract values
        lines = metrics_data.split('\n')
        for line in lines:
            if line.startswith('b2b_product_recommendations_total'):
                # Extract total recommendations
                if 'status="generated"' in line:
                    try:
                        value = int(line.split(' ')[-1])
                        sales_metrics["product_recommendations"]["total_generated"] += value
                    except:
                        pass
            
            elif line.startswith('b2b_quotes_generated_total'):
                # Extract total quotes
                try:
                    value = int(line.split(' ')[-1])
                    sales_metrics["quotations"]["total_generated"] += value
                except:
                    pass
            
            elif line.startswith('b2b_quotation_value_total'):
                # Extract quotation value
                if 'currency="USD"' in line:
                    try:
                        value = float(line.split(' ')[-1])
                        sales_metrics["quotations"]["total_value_usd"] = value
                    except:
                        pass
            
            elif line.startswith('b2b_sales_funnel_stage'):
                # Extract sales funnel stages
                if 'stage="discovery"' in line:
                    try:
                        value = int(line.split(' ')[-1])
                        sales_metrics["sales_funnel"]["discovery"] = value
                    except:
                        pass
                elif 'stage="solution_presentation"' in line:
                    try:
                        value = int(line.split(' ')[-1])
                        sales_metrics["sales_funnel"]["solution_presentation"] = value
                    except:
                        pass
                elif 'stage="quote_generation"' in line:
                    try:
                        value = int(line.split(' ')[-1])
                        sales_metrics["sales_funnel"]["quote_generation"] = value
                    except:
                        pass
        
        # Calculate derived metrics
        if sales_metrics["product_recommendations"]["total_generated"] > 0:
            # Estimate selection rate (this would need more detailed tracking)
            sales_metrics["product_recommendations"]["selection_rate"] = 0.25  # Placeholder
        
        if sales_metrics["quotations"]["total_generated"] > 0:
            sales_metrics["quotations"]["average_value"] = (
                sales_metrics["quotations"]["total_value_usd"] / 
                sales_metrics["quotations"]["total_generated"]
            )
            sales_metrics["quotations"]["success_rate"] = 0.85  # Placeholder
        
        # Add performance recommendations
        sales_metrics["recommendations"] = []
        
        if sales_metrics["product_recommendations"]["selection_rate"] < 0.2:
            sales_metrics["recommendations"].append("Low product selection rate - improve recommendation quality")
        
        if sales_metrics["quotations"]["success_rate"] < 0.8:
            sales_metrics["recommendations"].append("Low quote success rate - review quote generation process")
        
        if sales_metrics["sales_funnel"]["discovery"] > sales_metrics["sales_funnel"]["quote_generation"] * 3:
            sales_metrics["recommendations"].append("High discovery to quote ratio - optimize conversion process")
        
        return sales_metrics
        
    except Exception as e:
        logger.error(f"Error getting sales metrics: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
