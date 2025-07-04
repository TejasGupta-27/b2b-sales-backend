from services.language_service import LanguageService
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

class TextToSpeechRequest(BaseModel):
    text: str
    language: Optional[str] = "en"

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
                # Log STT provider used
                stt_provider = result.get('provider', 'unknown')
                fallback_used = result.get('fallback_used', False)
                logger.info(f"🎤 Transcription completed using {stt_provider} {'(fallback)' if fallback_used else '(primary)'}")
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
                # Log STT provider used
                stt_provider = result.get('provider', 'unknown')
                fallback_used = result.get('fallback_used', False)
                logger.info(f"🎤 Transcription completed using {stt_provider} {'(fallback)' if fallback_used else '(primary)'}")
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

@router.post("/transcribe-detailed")
async def transcribe_audio_detailed(
    audio: UploadFile = File(None),
    language: Optional[str] = None,
    audio_data: Optional[AudioData] = None,
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Enhanced transcription with detailed ElevenLabs response including language detection and word timing.
    
    Accepts either:
    1. A file upload (multipart/form-data)
    2. A JSON payload with base64 encoded audio data
    
    Args:
        audio: The audio file to transcribe (for file upload)
        language: Optional language code (e.g., "en", "ja", "es")
        audio_data: JSON payload with base64 encoded audio data
        speech_service: Initialized speech service instance
        
    Returns:
        dict: Contains detailed transcription with language detection, confidence, and word timing
    """
    try:
        logger.info(f"Received detailed transcription request: file={audio is not None}, audio_data={audio_data is not None}")
        
        # Handle file upload
        if audio:
            logger.info(f"Processing file upload for detailed transcription: filename={audio.filename}, content_type={audio.content_type}")
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
                # Enhanced logging for detailed transcription
                stt_provider = result.get('provider', 'unknown')
                fallback_used = result.get('fallback_used', False)
                language_detected = result.get('language', 'unknown')
                confidence = result.get('language_probability', 0)
                words_count = result.get('words_count', 0)
                
                logger.info(f"🎤 Detailed transcription using {stt_provider} {'(fallback)' if fallback_used else '(primary)'} - "
                           f"Language: {language_detected} (confidence: {confidence:.2f}), Words: {words_count}")
                
                return {
                    **result,
                    "enhanced_features": {
                        "language_detection": result.get('language') != 'unknown',
                        "confidence_scoring": result.get('language_probability') > 0,
                        "word_timing": len(result.get('segments', [])) > 0 and len(result.get('segments', [{}])[0].get('words', [])) > 0,
                        "segments_available": len(result.get('segments', [])) > 0
                    }
                }
            except Exception as e:
                logger.error(f"Error processing file upload for detailed transcription: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing audio file: {str(e)}"
                )
        
        # Handle byte array input
        elif audio_data:
            logger.info("Processing base64 audio data for detailed transcription")
            try:
                # Decode base64 audio data
                audio_bytes = base64.b64decode(audio_data.audio_bytes)
                logger.info(f"Decoded {len(audio_bytes)} bytes from base64 for detailed transcription")
                result = await speech_service.transcribe_audio(
                    audio_bytes,
                    language=audio_data.language or language
                )
                # Enhanced logging for detailed transcription
                stt_provider = result.get('provider', 'unknown')
                fallback_used = result.get('fallback_used', False)
                language_detected = result.get('language', 'unknown')
                confidence = result.get('language_probability', 0)
                words_count = result.get('words_count', 0)
                
                logger.info(f"🎤 Detailed transcription using {stt_provider} {'(fallback)' if fallback_used else '(primary)'} - "
                           f"Language: {language_detected} (confidence: {confidence:.2f}), Words: {words_count}")
                
                return {
                    **result,
                    "enhanced_features": {
                        "language_detection": result.get('language') != 'unknown',
                        "confidence_scoring": result.get('language_probability') > 0,
                        "word_timing": len(result.get('segments', [])) > 0 and len(result.get('segments', [{}])[0].get('words', [])) > 0,
                        "segments_available": len(result.get('segments', [])) > 0
                    }
                }
            except Exception as e:
                logger.error(f"Error processing base64 audio for detailed transcription: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid audio data: {str(e)}"
                )
        else:
            logger.error("No audio data provided for detailed transcription")
            raise HTTPException(
                status_code=400,
                detail="Either file upload or audio data is required"
            )
        
    except Exception as e:
        logger.error(f"Error in detailed transcription endpoint: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Error processing detailed transcription: {str(e)}"
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
    Also includes text-to-speech for the response with multilingual support.
    """
    try:
        # Validate audio file
        if not audio.content_type.startswith(('audio/', 'video/')):
            raise HTTPException(
                status_code=400,
                detail="File must be an audio file"
            )
        
        # Transcribe the audio to text (now includes automatic language detection)
        transcription_result = await speech_service.transcribe_audio(
            audio.file,
            language=language
        )
        
        # Get enhanced language detection from transcription
        detected_language = transcription_result.get('detected_language_info')
        primary_language = detected_language.get('primary_language', 'en') if detected_language else 'en'
        language_confidence = detected_language.get('primary_confidence', 0.0) if detected_language else 0.0
        
        logger.info(f"Detected primary language: {primary_language} (confidence: {language_confidence:.2f})")
        # Log full detection details
        if detected_language:
            secondary = detected_language.get('secondary_language')
            secondary_confidence = detected_language.get('secondary_confidence', 0.0)
            all_detected = detected_language.get('all_detected', [])

            logger.info(f"🈯 Secondary language: {secondary} (confidence: {secondary_confidence:.2f})")
            logger.info("📊 Language probabilities:")
            for lang_info in all_detected:
                logger.info(f"  - {lang_info['lang']}: {lang_info['prob']:.2f}")

        
        # Log STT provider used
        stt_provider = transcription_result.get('provider', 'unknown')
        stt_fallback_used = transcription_result.get('fallback_used', False)
        logger.info(f"🎤 Voice transcription using {stt_provider} {'(fallback)' if stt_fallback_used else '(primary)'}")
        
        # Check for transcription results with better error handling
        if not transcription_result or not transcription_result.get('text'):
            # Check if this was detected as empty/silent audio
            if transcription_result and transcription_result.get('empty_audio_detected'):
                raise HTTPException(
                    status_code=400,
                    detail="No speech detected in audio. Please ensure your microphone is working and speak clearly."
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to transcribe audio. Please check audio format and quality."
                )
        
        # Get the transcribed text
        text_message = transcription_result['text'].strip()
        
        # Additional validation for very short transcriptions that might be noise
        if len(text_message) < 2:
            logger.warning(f"Very short transcription detected: '{text_message}' - might be noise")
            raise HTTPException(
                status_code=400,
                detail="Transcription too short - please speak more clearly or check audio quality."
            )
            
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
        else:
            # Check if lead exists
            lead = db.query(DBLead).filter(DBLead.id == lead_id).first()
            if not lead:
                # Create new lead with the provided ID
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
                logger.info(f"Created new lead with provided ID: {lead_id}")
        
        # Save user message with enhanced language metadata
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
                "content_type": audio.content_type,
                "detected_language": detected_language,
                "primary_language": primary_language,
                "language_confidence": language_confidence,
                "multilingual_support": True
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
                "timeline": getattr(lead_record, 'decision_timeline', None),
                "preferred_language": primary_language,  # Add language preference
                "language_confidence": language_confidence
            }
        
        # Create Enhanced B2B Sales Agent with multilingual support
        try:
            base_provider = AIServiceFactory.create_provider(settings.default_ai_provider)
            enhanced_agent = EnhancedB2BSalesAgent(
                base_provider=base_provider,
                use_hybrid_retriever=settings.use_hybrid_retriever
            )
            
            # Initialize if needed
            await enhanced_agent.initialize()
            
            # Generate multilingual response with detected language context
            if hasattr(enhanced_agent, 'generate_multilingual_response'):
                response = await enhanced_agent.generate_multilingual_response(
                    messages, 
                    customer_context=customer_context,
                    detected_language=detected_language
                )
                logger.info(f"Generated multilingual response for language: {primary_language}")
            else:
                # Fallback to regular response generation
                response = await enhanced_agent.generate_response(
                    messages, 
                    customer_context=customer_context
                )
                logger.info("Using standard response generation (multilingual method not available)")
            
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
        
        # Generate speech for the response in the detected language
        speech_result = await speech_service.text_to_speech(
            text=response.content,
            language=primary_language  # Use detected language instead of form language
        )
        
        # Log TTS provider used with language info
        tts_provider = speech_result.get('provider', 'unknown')
        tts_fallback_used = speech_result.get('fallback_used', False)
        logger.info(f"🔊 Voice synthesis using {tts_provider} {'(fallback)' if tts_fallback_used else '(primary)'} for language: {primary_language}")
        
        # Save assistant response with enhanced multilingual metadata
        response_metadata = {
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
            "enhanced_sales_agent": True,
            "is_voice_message": True,
            "transcription_metadata": transcription_result,
            "speech_metadata": speech_result,
            "detected_language": detected_language,
            "response_language": primary_language,
            "language_confidence": language_confidence,
            "multilingual_support": True,
            "language_detection_enabled": True
        }
        
        # Add product intelligence if available
        if hasattr(enhanced_agent, 'product_recommendations'):
            response_metadata['product_recommendations'] = enhanced_agent.product_recommendations
        
        # Add quote information if generated
        if response.metadata and 'quote' in response.metadata:
            response_metadata['quote'] = response.metadata['quote']
        
        # Add multilingual context if available
        if response.metadata and 'multilingual_context' in response.metadata:
            response_metadata['multilingual_context'] = response.metadata['multilingual_context']
        
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
        
        # Return enhanced response with multilingual speech support
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
                "transcription_metadata": transcription_result,
                "speech_data": speech_result,
                "detected_language": detected_language,
                "response_language": primary_language,
                "language_confidence": language_confidence,
                "multilingual_support": True,
                "language_detection_enabled": True,
                "multilingual_context": response.metadata.get('multilingual_context') if response.metadata else None
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

@router.post("/text-to-speech")
async def text_to_speech(
    request: TextToSpeechRequest,
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Convert text to speech with ElevenLabs (primary) and gTTS (fallback)
    
    Args:
        request: Text-to-speech request parameters
        speech_service: Initialized speech service instance
        
    Returns:
        dict: Contains base64 encoded audio data and metadata
    """
    try:
        result = await speech_service.text_to_speech(
            text=request.text,
            language=request.language
        )
        logger.info(f"✅ Text-to-speech completed using {result.get('provider', 'unknown')} provider")
        return result
    except Exception as e:
        logger.error(f"Error in text-to-speech endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error converting text to speech: {str(e)}"
        )

@router.get("/voices")
async def get_available_voices(
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Get available voices from ElevenLabs
    
    Returns:
        dict: Available voices information
    """
    try:
        voices = await speech_service.get_available_voices()
        return voices
    except Exception as e:
        logger.error(f"Error getting available voices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving voices: {str(e)}"
        )

@router.get("/status")
async def get_speech_service_status(
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Get status of all speech services (ElevenLabs, Whisper, gTTS)
    
    Returns:
        dict: Status information for all services
    """
    try:
        status = await speech_service.get_service_status()
        return status
    except Exception as e:
        logger.error(f"Error getting speech service status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving service status: {str(e)}"
        )

class VoiceConfigRequest(BaseModel):
    voice_id: str
    stability: Optional[float] = None
    similarity_boost: Optional[float] = None
    style: Optional[float] = None
    use_speaker_boost: Optional[bool] = None

@router.post("/configure-voice")
async def configure_elevenlabs_voice(
    request: VoiceConfigRequest,
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Configure ElevenLabs voice settings (this would require updating settings)
    
    Args:
        request: Voice configuration parameters
        
    Returns:
        dict: Configuration status
    """
    try:
        # For now, this is informational - real implementation would need
        # to update the settings or allow per-request voice configuration
        return {
            "message": "Voice configuration received",
            "voice_id": request.voice_id,
            "settings": {
                "stability": request.stability,
                "similarity_boost": request.similarity_boost,
                "style": request.style,
                "use_speaker_boost": request.use_speaker_boost
            },
            "note": "Configuration would be applied to future TTS requests"
        }
    except Exception as e:
        logger.error(f"Error configuring voice: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error configuring voice: {str(e)}"
        ) 