from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Depends, Form
from typing import Optional, Union
from services.speech_service import SpeechService
from pydantic import BaseModel
import base64
import logging
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import ChatMessage as DBChatMessage, MessageType, Lead as DBLead, LeadStatus
from models.chat import ChatRequest, ChatResponse
from ai_services.factory import AIServiceFactory
from ai_services.base import AIMessage
import uuid
from datetime import datetime
from dependencies import get_speech_service
from ai_services.enhanced_b2b_sales_agent import EnhancedB2BSalesAgent
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class AudioData(BaseModel):
    audio_bytes: str  # base64 encoded audio data
    language: Optional[str] = None

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(None),
    language: Optional[str] = None,
    audio_data: Optional[AudioData] = None,
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Transcribe audio to text using Whisper.
    
    Accepts either:
    1. A file upload (multipart/form-data)
    2. A JSON payload with base64 encoded audio data
    
    Args:
        audio: The audio file to transcribe (for file upload)
        language: Optional language code (e.g., "en", "ja", "es")
        audio_data: JSON payload with base64 encoded audio data
        speech_service: Initialized speech service instance
        
    Returns:
        dict: Contains transcription text and metadata
    """
    try:
        logger.info(f"Received transcription request: file={audio is not None}, audio_data={audio_data is not None}")
        
        # Handle file upload
        if audio:
            logger.info(f"Processing file upload: filename={audio.filename}, content_type={audio.content_type}")
            if not audio.content_type.startswith(('audio/', 'video/')):
                raise HTTPException(
                    status_code=400,
                    detail="File must be an audio file"
                )
            try:
                result = await speech_service.transcribe_audio(
                    audio.file,
                    language=language
                )
                return result
            except Exception as e:
                logger.error(f"Error processing file upload: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing audio file: {str(e)}"
                )
        
        # Handle byte array input
        elif audio_data:
            logger.info("Processing base64 audio data")
            try:
                # Decode base64 audio data
                audio_bytes = base64.b64decode(audio_data.audio_bytes)
                logger.info(f"Decoded {len(audio_bytes)} bytes from base64")
                result = await speech_service.transcribe_audio(
                    audio_bytes,
                    language=audio_data.language or language
                )
                return result
            except Exception as e:
                logger.error(f"Error processing base64 audio: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid audio data: {str(e)}"
                )
        else:
            logger.error("No audio data provided")
            raise HTTPException(
                status_code=400,
                detail="Either file upload or audio data is required"
            )
        
    except Exception as e:
        logger.error(f"Error in transcribe_audio endpoint: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio: {str(e)}"
        )

@router.post("/chat/voice")
async def handle_voice_message(
    audio: UploadFile = File(...),
    lead_id: Optional[str] = Form(None),
    conversation_stage: Optional[str] = Form("discovery"),
    language: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Handle voice input just like text input, with an extra transcription step.
    The transcribed text is processed through the enhanced sales chat pipeline.
    """
    try:
        # Validate audio file
        if not audio.content_type.startswith(('audio/', 'video/')):
            raise HTTPException(
                status_code=400,
                detail="File must be an audio file"
            )
        
        # Transcribe the audio to text
        transcription_result = await speech_service.transcribe_audio(
            audio.file,
            language=language
        )
        
        if not transcription_result or not transcription_result.get('text'):
            raise HTTPException(
                status_code=400,
                detail="Failed to transcribe audio"
            )
        
        # Get the transcribed text
        text_message = transcription_result['text']
        logger.info(f"Transcribed text: {text_message}")
        
        # Handle lead management
        if not lead_id:
            lead_id = str(uuid.uuid4())
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
            content=text_message,
            stage=conversation_stage,
            message_metadata={
                "is_voice_message": True,
                "transcription_metadata": transcription_result,
                "original_filename": audio.filename,
                "content_type": audio.content_type
            }
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
        
        # Get customer context
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
        
        # Create Enhanced B2B Sales Agent
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
            base_provider = AIServiceFactory.create_provider()
            response = await base_provider.generate_response(messages)
            
            # Add error metadata
            if not response.metadata:
                response.metadata = {}
            response.metadata['agent_error'] = str(agent_error)
            response.metadata['fallback_used'] = True
        
        # Save assistant response
        response_metadata = {
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
            "enhanced_sales_agent": True,
            "is_voice_message": True,
            "transcription_metadata": transcription_result
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
            stage=conversation_stage,
            message_metadata=response_metadata
        )
        db.add(assistant_message)
        db.commit()
        
        # Return enhanced response
        return ChatResponse(
            message=response.content,
            lead_id=lead_id,
            conversation_stage=conversation_stage,
            metadata={
                "enhanced_sales_agent": True,
                "provider": response.provider,
                "model": response.model,
                "usage": response.usage,
                "product_intelligence": getattr(enhanced_agent, 'product_recommendations', {}),
                "timestamp": datetime.now().isoformat(),
                "is_voice_message": True,
                "transcription_metadata": transcription_result
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing voice message: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Error processing voice message: {str(e)}"
        ) 