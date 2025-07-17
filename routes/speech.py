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
from ai_services.simple_conversational_agent import SimpleConversationalAgent
from config import settings
from services.language_service import LanguageService
from services.auth_service import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize LanguageService
language_service = LanguageService()

class AudioData(BaseModel):
    audio_bytes: str  # base64 encoded audio data
    language: Optional[str] = None

class TextToSpeechRequest(BaseModel):
    text: str
    language: Optional[str] = "en"

class LanguageDetectionRequest(BaseModel):
    text: str

@router.post("/detect-language")
async def detect_text_language(request: LanguageDetectionRequest):
    """
    Detect the language of provided text using LanguageService.
    
    Args:
        request: Text language detection request
        
    Returns:
        dict: Language detection results with confidence scores
    """
    try:
        detection_result = language_service.detect_language(request.text)
        logger.info(f"🌐 Language detection: primary={detection_result['primary_language']} "
                   f"({detection_result['primary_confidence']:.2f}), "
                   f"secondary={detection_result.get('secondary_language', 'None')}")
        return {
            "success": True,
            "text_length": len(request.text),
            "detection_result": detection_result,
            "supported_languages": language_service.supported_languages,
            "multilingual_detected": detection_result.get('is_multilingual', False)
        }
    except Exception as e:
        logger.error(f"Error in language detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error detecting language: {str(e)}"
        )

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(None),
    language: Optional[str] = None,
    audio_data: Optional[AudioData] = None,
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Transcribe audio to text using Whisper with enhanced language detection.
    
    Accepts either:
    1. A file upload (multipart/form-data)
    2. A JSON payload with base64 encoded audio data
    
    Args:
        audio: The audio file to transcribe (for file upload)
        language: Optional language code (e.g., "en", "ja", "es")
        audio_data: JSON payload with base64 encoded audio data
        speech_service: Initialized speech service instance
        
    Returns:
        dict: Contains transcription text and enhanced language metadata
    """
    try:
        logger.info(f"Received transcription request: file={audio is not None}, audio_data={audio_data is not None}")
        
        # Handle file upload
        if audio:
            # Log uploaded file size
            audio.file.seek(0, 2)  # Move to end
            size = audio.file.tell()
            audio.file.seek(0)     # Reset to start
            logger.info(f"Uploaded file size: {size} bytes (filename={audio.filename})")
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
                
                # Enhanced language detection post-processing
                transcribed_text = result.get('text', '').strip()
                if transcribed_text:
                    # Get additional language detection from LanguageService
                    enhanced_detection = language_service.detect_language(transcribed_text)
                    result['enhanced_language_detection'] = enhanced_detection
                    
                    # Log enhanced detection
                    logger.info(f"🌐 Enhanced language detection: primary={enhanced_detection['primary_language']} "
                               f"({enhanced_detection['primary_confidence']:.2f}), "
                               f"secondary={enhanced_detection.get('secondary_language', 'None')}")
                
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
                logger.info(f"Decoded {len(audio_bytes)} bytes from base64 (from audio_data)")
                result = await speech_service.transcribe_audio(
                    audio_bytes,
                    language=audio_data.language or language
                )
                
                # Enhanced language detection post-processing
                transcribed_text = result.get('text', '').strip()
                if transcribed_text:
                    # Get additional language detection from LanguageService
                    enhanced_detection = language_service.detect_language(transcribed_text)
                    result['enhanced_language_detection'] = enhanced_detection
                    
                    # Log enhanced detection
                    logger.info(f"🌐 Enhanced language detection: primary={enhanced_detection['primary_language']} "
                               f"({enhanced_detection['primary_confidence']:.2f}), "
                               f"secondary={enhanced_detection.get('secondary_language', 'None')}")
                
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
            # Log uploaded file size
            audio.file.seek(0, 2)  # Move to end
            size = audio.file.tell()
            audio.file.seek(0)     # Reset to start
            logger.info(f"Uploaded file size: {size} bytes (filename={audio.filename})")
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
                logger.info(f"Decoded {len(audio_bytes)} bytes from base64 (from audio_data)")
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
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    speech_service: SpeechService = Depends(get_speech_service)
):
    """
    Handle voice input just like text input, with an extra transcription step.
    The transcribed text is processed through the enhanced sales chat pipeline.
    Also includes text-to-speech for the response.
    Requires authentication and uses role-based access control.
    """
    try:
        # Import required dependencies
        from services.auth_service import get_current_active_user, check_lead_access, get_lead_access_filter
        
        # Validate audio file
        if not audio.content_type.startswith(('audio/', 'video/')):
            raise HTTPException(
                status_code=400,
                detail="File must be an audio file"
            )
        # Log uploaded file size
        audio.file.seek(0, 2)  # Move to end
        size = audio.file.tell()
        audio.file.seek(0)     # Reset to start
        logger.info(f"Uploaded file size: {size} bytes (filename={audio.filename})")
        # Transcribe the audio to text
        transcription_result = await speech_service.transcribe_audio(
            audio.file,
            language=language
        )
        
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
        
        text_message = transcription_result['text'].strip()
        logger.info(f"🗣️ Transcribed voice message: '{text_message}' (Language: {transcription_result.get('language', 'auto')})")
        
        if not text_message:
            raise HTTPException(
                status_code=400,
                detail="Empty transcription - no speech detected"
            )
        
        # Automatic language detection and response language setting
        detected_language = None
        response_language = "en"  # Default fallback
        
        # Check detected language from transcription
        if transcription_result.get('language'):
            detected_language = transcription_result['language']
            response_language = detected_language if detected_language in settings.SUPPORTED_LANGUAGES else "en"
        # If language was explicitly provided
        elif language and language in settings.SUPPORTED_LANGUAGES:
            response_language = language
        # Use language service for detection if available and confidence is high
        elif hasattr(language_service, 'detect_language'):
            try:
                detection_result = language_service.detect_language(text_message)
                if (detection_result.get('confidence', 0) >= settings.LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD
                    and detection_result.get('language') in settings.SUPPORTED_LANGUAGES):
                    detected_language = detection_result['language']
                    response_language = detected_language
            except Exception as e:
                logger.warning(f"Language detection failed: {e}")
        
        logger.info(f"🌐 Language - Detected: {detected_language}, Response: {response_language}")
        
        # Handle lead management with role-based access control
        if not lead_id:
            lead_id = str(uuid.uuid4())
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
        else:
            # Verify user has access to this lead using role-based access control
            lead = check_lead_access(lead_id, current_user, db)
        
        # Save user message with user association
        logger.info(f"VOICE: About to insert message_type={MessageType.USER.value!r} ({type(MessageType.USER.value)})")
        user_message = DBChatMessage(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            user_id=current_user.id,  # Associate with current user
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
        
        # Get conversation history with role-based filtering
        lead_filters = get_lead_access_filter(current_user)
        messages = []
        existing_messages = db.query(DBChatMessage).join(DBLead).filter(
            DBChatMessage.lead_id == lead_id,
            *lead_filters  # Apply role-based filtering
        ).order_by(DBChatMessage.created_at).all()
        
        for msg in existing_messages:
            role = "user" if msg.message_type == MessageType.USER.value else "assistant"
            messages.append(AIMessage(role=role, content=msg.content))
        
        # Get customer context from the lead (already verified accessible)
        customer_context = None
        if lead:
            customer_context = {
                "company_name": lead.company_name,
                "contact_name": lead.contact_name,
                "email": lead.email,
                "company_size": getattr(lead, 'company_size', None),
                "industry": getattr(lead, 'industry', None),
                "budget_range": getattr(lead, 'budget_range', None),
                "timeline": getattr(lead, 'decision_timeline', None),
                "user_organization": current_user.organization.name if current_user.organization else "Unknown"
            }
        
        # Create Simple Conversational Agent with multilingual support
        try:
            base_provider = AIServiceFactory.create_provider(settings.default_ai_provider)
            simple_agent = SimpleConversationalAgent(
                base_provider=base_provider,
                use_hybrid_retriever=settings.use_hybrid_retriever
            )
            
            # Initialize if needed
            await simple_agent.initialize()
            
            # Generate response with language context
            response = await simple_agent.generate_response(
                messages, 
                customer_context=customer_context
            )
            logger.info(f"Generated response for detected language: {primary_language}")
            
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
        
        # Generate speech for the response
        speech_result = await speech_service.text_to_speech(
            text=response.content,
            language=language or "en"
        )
        
        # Log TTS provider used
        tts_provider = speech_result.get('provider', 'unknown')
        tts_fallback_used = speech_result.get('fallback_used', False)
        logger.info(f"🔊 Voice synthesis using {tts_provider} {'(fallback)' if tts_fallback_used else '(primary)'}")
        
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
        if hasattr(simple_agent, 'product_recommendations'):
            response_metadata['product_recommendations'] = simple_agent.product_recommendations
        
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
        
        # Return enhanced response with speech
        return ChatResponse(
            message=response.content,
            lead_id=lead_id,
            conversation_stage=conversation_stage,
            metadata={
                "enhanced_sales_agent": True,
                "provider": response.provider,
                "model": response.model,
                "usage": response.usage,
                "product_intelligence": getattr(simple_agent, 'product_recommendations', {}),
                "timestamp": datetime.now().isoformat(),
                "is_voice_message": True,
                "transcription_metadata": transcription_result,
                "speech_data": speech_result
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
    Enhanced with automatic language detection if language not specified.
    
    Args:
        request: Text-to-speech request parameters
        speech_service: Initialized speech service instance
        
    Returns:
        dict: Contains base64 encoded audio data and metadata
    """
    try:
        # Auto-detect language if not specified or if confidence is low
        target_language = request.language
        detected_language_info = None
        
        if not target_language or target_language == "auto":
            # Auto-detect the language
            detected_language_info = language_service.detect_language(request.text)
            target_language = detected_language_info['primary_language']
            logger.info(f"🌐 Auto-detected language: {target_language} "
                       f"(confidence: {detected_language_info['primary_confidence']:.2f})")
        elif target_language in ["en", "ja", "es", "fr", "de", "it", "pt", "ko", "zh"]:
            # Validate the detected language matches the request if confidence is high
            detected_language_info = language_service.detect_language(request.text)
            if detected_language_info['primary_confidence'] > 0.8:
                if detected_language_info['primary_language'] != target_language:
                    logger.warning(f"⚠️ Language mismatch: requested={target_language}, "
                                 f"detected={detected_language_info['primary_language']} "
                                 f"(confidence: {detected_language_info['primary_confidence']:.2f})")
                    # Use detected language if confidence is very high
                    if detected_language_info['primary_confidence'] > 0.9:
                        target_language = detected_language_info['primary_language']
                        logger.info(f"🔄 Switching to detected language: {target_language}")
        
        result = await speech_service.text_to_speech(
            text=request.text,
            language=target_language
        )
        
        # Add language detection metadata to result
        if detected_language_info:
            result['language_detection'] = detected_language_info
            result['auto_detected_language'] = target_language != request.language
        
        logger.info(f"✅ Text-to-speech completed using {result.get('provider', 'unknown')} provider for language: {target_language}")
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

@router.get("/language-support")
async def get_language_support():
    """
    Get information about supported languages across all speech services.
    
    Returns:
        dict: Comprehensive language support information
    """
    try:
        return {
            "language_detection": {
                "supported_languages": language_service.supported_languages,
                "detection_method": "langdetect with polyglot fallback",
                "multilingual_support": True,
                "confidence_threshold": 0.8
            },
            "speech_to_text": {
                "elevenlabs_supported": [
                    "en", "ja", "zh", "de", "hi", "fr", "ko", "pt", "it", "es", 
                    "id", "nl", "tr", "fi", "sv", "bg", "hr", "cs", "da", "et",
                    "lv", "lt", "mt", "no", "pl", "ro", "sk", "sl", "uk", "ar"
                ],
                "whisper_supported": [
                    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo",
                    "br", "bs", "ca", "cs", "cy", "da", "de", "el", "en", "es",
                    "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw",
                    "he", "hi", "hr", "ht", "hu", "hy", "id", "is", "it", "ja",
                    "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo",
                    "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
                    "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt",
                    "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq",
                    "sr", "su", "sv", "sw", "ta", "te", "tg", "th", "tk", "tl",
                    "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "zh"
                ]
            },
            "text_to_speech": {
                "elevenlabs_supported": ["en", "ja", "zh", "de", "hi", "fr", "ko", "pt", "it", "es"],
                "gtts_supported": [
                    "af", "ar", "bg", "bn", "bs", "ca", "cs", "cy", "da", "de",
                    "el", "en", "es", "et", "fi", "fr", "gu", "hi", "hr", "hu",
                    "id", "is", "it", "ja", "jw", "km", "kn", "ko", "la", "lv",
                    "mk", "ml", "mr", "my", "ne", "nl", "no", "pl", "pt", "ro",
                    "ru", "si", "sk", "sq", "sr", "su", "sv", "sw", "ta", "te",
                    "th", "tl", "tr", "uk", "ur", "vi", "zh"
                ]
            },
            "recommended_languages": ["en", "ja", "es", "fr", "de", "it", "pt", "ko", "zh"],
            "auto_detection_enabled": True
        }
    except Exception as e:
        logger.error(f"Error getting language support info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving language support: {str(e)}"
        ) 