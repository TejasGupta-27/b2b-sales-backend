from faster_whisper import WhisperModel
import numpy as np
import io
import soundfile as sf
import tempfile
import os
from pathlib import Path
from typing import BinaryIO, Optional, Union
import logging
import torch
import librosa
import aiohttp
import asyncio
from contextlib import asynccontextmanager
from gtts import gTTS
import base64
from scipy.signal import resample_poly  # <-- Add this import
from services.language_service import LanguageService

# ElevenLabs integration
try:
    from elevenlabs import Voice, VoiceSettings
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

from config import settings

logger = logging.getLogger(__name__)

# Helper function for resampling using scipy

def resample_audio(audio_array, orig_sr, target_sr):
    from math import gcd
    factor = gcd(orig_sr, target_sr)
    up = target_sr // factor
    down = orig_sr // factor
    return resample_poly(audio_array, up, down)

class SpeechService:
    def __init__(self, model_name: str = "medium"):
        """
        Initialize the enhanced speech service with ElevenLabs and Whisper/gTTS fallback.
        
        Args:
            model_name: Name of the Whisper model to use for fallback (tiny, base, small, medium, large)
        """
        self.model_name = model_name
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.target_sr = 16000  # Whisper expects 16kHz audio
        self._session = None
        self._timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        
        # ElevenLabs setup
        self.elevenlabs_client = None
        self.use_elevenlabs = ELEVENLABS_AVAILABLE and settings.elevenlabs_api_key
        
        # Initialize language service for language detection
        self.language_service = LanguageService()
        
        if self.use_elevenlabs:
            try:
                self.elevenlabs_client = ElevenLabs(api_key=settings.elevenlabs_api_key)
                logger.info(f"✅ ElevenLabs client initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️ ElevenLabs initialization failed: {e}. Falling back to Whisper/gTTS")
                self.use_elevenlabs = False
        else:
            if not ELEVENLABS_AVAILABLE:
                logger.warning("⚠️ ElevenLabs package not installed. Install with: pip install elevenlabs")
            if not settings.elevenlabs_api_key:
                logger.warning("⚠️ ELEVENLABS_API_KEY not configured")
            
        logger.info(f"Speech service initialized - Primary: {'ElevenLabs' if self.use_elevenlabs else 'Whisper/gTTS'}, Model: {model_name}, Device: {self.device}")
    
    @asynccontextmanager
    async def _get_session(self):
        """Context manager for aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
            logger.info("✅ aiohttp session initialized")
        try:
            yield self._session
        except Exception as e:
            logger.error(f"Session error: {str(e)}")
            if self._session:
                await self._session.close()
                self._session = None
            raise
        finally:
            if self._session:
                await self._session.close()
                self._session = None
                logger.info("✅ aiohttp session closed")
    
    async def initialize(self):
        """Initialize the speech models."""
        try:
            # Always initialize Whisper for STT and as TTS fallback
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                download_root="./models"
            )
            logger.info(f"✅ Whisper model {self.model_name} loaded successfully")
            
            # Test ElevenLabs connection if available
            if self.use_elevenlabs:
                try:
                    # Test the connection by getting user info
                    user_info = await self._test_elevenlabs_connection()
                    logger.info(f"✅ ElevenLabs connection verified: {user_info.get('subscription', {}).get('tier', 'Unknown')}")
                except Exception as e:
                    logger.warning(f"⚠️ ElevenLabs connection test failed: {e}. Fallback will be used.")
                    self.use_elevenlabs = False
                
        except Exception as e:
            logger.error(f"Failed to initialize speech service: {str(e)}")
            await self.close()  # Clean up on initialization failure
            raise
    
    async def _test_elevenlabs_connection(self) -> dict:
        """Test ElevenLabs API connection."""
        if not self.elevenlabs_client:
            raise Exception("ElevenLabs client not initialized")
        
        # This is a synchronous call - if needed, wrap in asyncio.get_event_loop().run_in_executor()
        user_info = self.elevenlabs_client.user.get()
        return user_info.model_dump() if hasattr(user_info, 'model_dump') else dict(user_info)
    
    async def close(self):
        """Clean up resources."""
        # Close Whisper model
        self.model = None
        
        # Close aiohttp session
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("✅ aiohttp session closed")
    
    def _preprocess_audio(self, audio_data: Union[BinaryIO, bytes]) -> tuple[np.ndarray, int]:
        """
        Preprocess audio data to ensure it's in the correct format for Whisper (16kHz mono PCM WAV).
        """
        try:
            if isinstance(audio_data, bytes):
                audio_bytes = audio_data
            else:
                audio_data.seek(0)
                audio_bytes = audio_data.read()
            if len(audio_bytes) == 0:
                raise Exception("Empty audio data received")
            audio_array, orig_sr = librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)
            logger.info(f"Original audio: shape={audio_array.shape}, sample_rate={orig_sr}")
            target_sr = 16000
            if orig_sr != target_sr:
                # audio_array = librosa.core.resample(audio_array, orig_sr=orig_sr, target_sr=target_sr)
                audio_array = resample_audio(audio_array, orig_sr, target_sr)
                logger.info(f"Resampled audio to {target_sr} Hz")
            else:
                logger.info("Audio already at 16kHz, no resampling needed")
            return audio_array, target_sr
        except Exception as e:
            logger.error(f"Error preprocessing audio: {e}")
            raise

    def get_resampled_bytes(self, audio_data: Union[BinaryIO, bytes]) -> bytes:
        """
        Resample audio to 16kHz mono and return as WAV bytes for ElevenLabs.
        """
        try:
            if isinstance(audio_data, bytes):
                audio_bytes = audio_data
            else:
                audio_data.seek(0)
                audio_bytes = audio_data.read()
            if len(audio_bytes) == 0:
                raise Exception("Empty audio data received")
            audio_array, orig_sr = librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)
            logger.info(f"Original audio: shape={audio_array.shape}, sample_rate={orig_sr}")
            target_sr = 16000
            if orig_sr != target_sr:
                # audio_array = librosa.core.resample(audio_array, orig_sr=orig_sr, target_sr=target_sr)
                audio_array = resample_audio(audio_array, orig_sr, target_sr)
                logger.info(f"Resampled audio to {target_sr} Hz")
            else:
                logger.info("Audio already at 16kHz, no resampling needed")
            buffer = io.BytesIO()
            sf.write(buffer, audio_array, target_sr, format='WAV')
            buffer.seek(0)
            resampled_bytes = buffer.read()
            logger.info(f"Resampled audio bytes length: {len(resampled_bytes)}")
            return resampled_bytes
        except Exception as e:
            logger.error(f"Error resampling audio for ElevenLabs: {e}")
            raise

    async def _elevenlabs_speech_to_text(
        self,
        audio_data: Union[BinaryIO, bytes],
        language: Optional[str] = None
    ) -> dict:
        """
        Transcribe audio using ElevenLabs STT API. Audio is always resampled to 16kHz mono WAV.
        """
        try:
            wav_bytes = self.get_resampled_bytes(audio_data)
            logger.info(f"Sending {len(wav_bytes)} bytes to ElevenLabs STT")
            
            # ElevenLabs STT expects file-like object
            from io import BytesIO
            audio_file = BytesIO(wav_bytes)
            
            # Run ElevenLabs STT in executor since it's synchronous
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.elevenlabs_client.speech_to_text.convert(
                    file=audio_file,
                    model_id=settings.elevenlabs_stt_model_id
                )
            )
            
            # Extract detailed information from ElevenLabs response
            transcription_text = result.text if hasattr(result, 'text') else str(result)
            detected_language = getattr(result, 'language_code', language or 'en')
            language_confidence = getattr(result, 'language_probability', 1.0)
            words_list = getattr(result, 'words', [])
            
            # Log ElevenLabs response details with better formatting
            logger.info(f"ElevenLabs STT response: text_length={len(transcription_text)}, "
                       f"text_content='{transcription_text[:100]}{'...' if len(transcription_text) > 100 else ''}', "
                       f"language={detected_language}, confidence={language_confidence:.2f}, "
                       f"words_count={len(words_list)}")
            
            # If transcription is empty, log additional debug info
            if not transcription_text.strip():
                logger.warning(f"ElevenLabs returned empty transcription for {len(wav_bytes)} bytes of audio data")
                # Check if result has any debug information
                if hasattr(result, '__dict__'):
                    logger.debug(f"Full ElevenLabs result: {result.__dict__}")
            
            # Convert ElevenLabs words format to Whisper-compatible format
            processed_words = []
            if words_list:
                for word_obj in words_list:
                    if hasattr(word_obj, '__dict__'):
                        # Handle object with attributes
                        word_data = {
                            "word": getattr(word_obj, 'text', ''),
                            "start": getattr(word_obj, 'start_time', 0),
                            "end": getattr(word_obj, 'end_time', 0),
                            "probability": getattr(word_obj, 'confidence', 1.0)
                        }
                    elif isinstance(word_obj, dict):
                        # Handle dictionary format
                        word_data = {
                            "word": word_obj.get('text', ''),
                            "start": word_obj.get('start_time', 0),
                            "end": word_obj.get('end_time', 0),
                            "probability": word_obj.get('confidence', 1.0)
                        }
                    else:
                        # Fallback for unexpected format
                        word_data = {
                            "word": str(word_obj),
                            "start": 0,
                            "end": 0,
                            "probability": 1.0
                        }
                    processed_words.append(word_data)
            
            # Create segments from words (group words into sentences/segments)
            processed_segments = []
            if processed_words:
                # Simple segmentation: create one segment with all words
                segment_start = processed_words[0]['start'] if processed_words else 0
                segment_end = processed_words[-1]['end'] if processed_words else 0
                
                processed_segments.append({
                    "text": transcription_text,
                    "start": segment_start,
                    "end": segment_end,
                    "avg_logprob": 0.0,  # Not provided by ElevenLabs
                    "no_speech_prob": 1.0 - language_confidence,  # Inverse of language confidence
                    "words": processed_words
                })
            
            # Calculate duration from words or estimate
            duration = 0
            if processed_words:
                duration = processed_words[-1]['end']
            elif len(wav_bytes) > 0:
                # Rough estimation: assume 16kHz, 16-bit audio
                estimated_samples = len(wav_bytes) // 2  # 16-bit = 2 bytes per sample
                duration = estimated_samples / 16000  # 16kHz sample rate
            
            return {
                "text": transcription_text,
                "language": detected_language,
                "language_probability": language_confidence,
                "segments": processed_segments,
                "duration": duration,
                "provider": "elevenlabs",
                "model": settings.elevenlabs_stt_model_id,
                "words_count": len(processed_words),
                "elevenlabs_raw_response": {
                    "language_code": detected_language,
                    "language_probability": language_confidence,
                    "text": transcription_text,
                    "words_detected": len(processed_words)
                }
            }
            
        except Exception as e:
            logger.error(f"ElevenLabs STT error: {e}")
            raise

    async def _whisper_speech_to_text(
        self,
        audio_data: Union[BinaryIO, bytes],
        language: Optional[str] = None
    ) -> dict:
        """
        Transcribe audio data using Whisper (fallback).
        
        Args:
            audio_data: Audio data as file-like object or bytes
            language: Optional language code (e.g., "en", "ja", "es")
            
        Returns:
            dict: Contains transcription text and metadata
        """
        try:
            # Preprocess audio
            audio_array, sample_rate = self._preprocess_audio(audio_data)
            logger.info(f"Audio duration: {len(audio_array)/sample_rate:.2f} seconds")
            
            # Transcribe with Whisper
            segments, info = self.model.transcribe(
                audio_array,
                language=language,
                beam_size=5,
                vad_filter=False,  # Disabled VAD filter
                vad_parameters=dict(
                    min_silence_duration_ms=1000,
                    speech_pad_ms=30,
                    threshold=0.5
                ),
                condition_on_previous_text=True,
                temperature=0.0,
                compression_ratio_threshold=2.4,
                no_speech_threshold=0.6,
                word_timestamps=True,
                best_of=5,
                repetition_penalty=1.0
            )
            
            # Process segments
            processed_segments = []
            for segment in segments:
                processed_segments.append({
                    "text": segment.text,
                    "start": segment.start,
                    "end": segment.end,
                    "avg_logprob": segment.avg_logprob,
                    "no_speech_prob": segment.no_speech_prob,
                    "words": [
                        {
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability
                        }
                        for word in segment.words
                    ] if segment.words else []
                })
            
            # Get full text
            full_text = " ".join(segment["text"] for segment in processed_segments)
            
            return {
                "text": full_text,
                "language": info.language,
                "language_probability": info.language_probability,
                "segments": processed_segments,
                "duration": len(audio_array)/sample_rate,
                "provider": "whisper"
            }
            
        except Exception as e:
            # Improve error logging to show actual error instead of empty message
            error_msg = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
            logger.error(f"Whisper STT error: {error_msg}")
            raise Exception(f"Whisper STT error: {error_msg}")

    async def transcribe_audio(
        self,
        audio_data: Union[BinaryIO, bytes],
        language: Optional[str] = None
    ) -> dict:
        """
        Transcribe audio data using ElevenLabs STT with Whisper fallback.
        
        Args:
            audio_data: Audio data as file-like object or bytes
            language: Optional language code (e.g., "en", "ja", "es")
            
        Returns:
            dict: Contains transcription text and metadata
        """
        if self.model is None:
            await self.initialize()
            
        max_retries = 3
        retry_delay = 1  # seconds
        
        # Try ElevenLabs STT first if available
        if self.use_elevenlabs and settings.speech_primary_provider == "elevenlabs":
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting ElevenLabs STT (attempt {attempt + 1}/{max_retries})")
                    result = await self._elevenlabs_speech_to_text(audio_data, language)
                    
                    # Check if we got meaningful transcription results
                    transcription_text = result.get('text', '').strip()
                    if transcription_text:  # Non-empty transcription
                        # Detect primary and secondary language using LanguageService
                        detected_language = self.language_service.detect_language(transcription_text)
                        result.update({
                            'detected_language_info': detected_language,
                            'auto_detected_primary': detected_language['primary_language'],
                            'language_confidence': detected_language['primary_confidence']
                        })
                        # Override language if confidence is high
                        if detected_language['primary_confidence'] > 0.8:
                            result['language'] = detected_language['primary_language']

                        logger.info("✅ ElevenLabs STT successful "
                                    f"(primary={detected_language['primary_language']}, "
                                    f"secondary={detected_language.get('secondary_language')})")
                        return result
                    else:
                        logger.warning(f"ElevenLabs STT returned empty transcription (attempt {attempt + 1}/{max_retries})")
                        # Don't retry for empty results, fall back to Whisper immediately
                        break
                    
                except Exception as e:
                    logger.error(f"ElevenLabs STT failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying ElevenLabs STT in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.warning("ElevenLabs STT failed after all retries, falling back to Whisper")
            
            # If we reach here, either ElevenLabs failed or returned empty results
            logger.warning("ElevenLabs STT failed or returned empty results, falling back to Whisper")
        
        # Fallback to Whisper if ElevenLabs failed or not configured
        if settings.speech_fallback_enabled:
            for attempt in range(max_retries):
                try:
                    logger.info(f"Using Whisper STT fallback (attempt {attempt + 1}/{max_retries})")
                    result = await self._whisper_speech_to_text(audio_data, language)
                    
                    # Check Whisper results and add language detection
                    transcription_text = result.get('text', '').strip()
                    if transcription_text:  # Non-empty transcription
                        # Detect primary and secondary language using LanguageService
                        detected_language = self.language_service.detect_language(transcription_text)
                        result.update({
                            'detected_language_info': detected_language,
                            'auto_detected_primary': detected_language['primary_language'],
                            'language_confidence': detected_language['primary_confidence']
                        })
                        # Override language if confidence is high
                        if detected_language['primary_confidence'] > 0.8:
                            result['language'] = detected_language['primary_language']

                        logger.info("✅ Whisper STT fallback successful "
                                    f"(primary={detected_language['primary_language']}, "
                                    f"secondary={detected_language.get('secondary_language')})")
                        result["fallback_used"] = True
                        return result
                    else:
                        logger.warning(f"Whisper STT also returned empty transcription (attempt {attempt + 1}/{max_retries})")
                        if attempt == max_retries - 1:
                            # On the last attempt, return the empty result with metadata
                            result["fallback_used"] = True
                            result["empty_audio_detected"] = True
                            logger.warning("All STT services returned empty transcription - likely silent audio")
                            return result
                    
                except Exception as e:
                    logger.error(f"Whisper STT fallback failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying Whisper STT in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error("All STT options failed")
                        raise Exception("All speech-to-text services failed")
        else:
            raise Exception("Primary STT service failed and fallback is disabled")

    async def _elevenlabs_text_to_speech(self, text: str, language: str = "en") -> dict:
        """
        Convert text to speech using ElevenLabs.
        
        Args:
            text: The text to convert to speech
            language: The language code (e.g., "en", "ja", "es")
            
        Returns:
            dict: Contains base64 encoded audio data and metadata
        """
        try:
            # Configure voice settings
            voice_settings = VoiceSettings(
                stability=settings.elevenlabs_stability,
                similarity_boost=settings.elevenlabs_similarity_boost,
                style=settings.elevenlabs_style,
                use_speaker_boost=settings.elevenlabs_use_speaker_boost
            )
            
            # Generate speech - this is synchronous, so we might want to run it in executor
            loop = asyncio.get_event_loop()
            audio_iterator = await loop.run_in_executor(
                None,
                lambda: self.elevenlabs_client.text_to_speech.convert(
                    voice_id=settings.elevenlabs_voice_id,
                    text=text,
                    model_id=settings.elevenlabs_model_id,
                    voice_settings=voice_settings,
                    output_format="mp3_44100_128"
                )
            )
            
            # The method returns Iterator[bytes], so we need to collect all chunks
            audio_bytes = b"".join(audio_iterator)
            
            # Convert to base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            return {
                "audio_data": audio_base64,
                "format": "mp3",
                "language": language,
                "text_length": len(text),
                "provider": "elevenlabs",
                "voice_id": settings.elevenlabs_voice_id,
                "model": settings.elevenlabs_model_id
            }
            
        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {str(e)}")
            raise

    async def _gtts_text_to_speech(self, text: str, language: str = "en") -> dict:
        """
        Convert text to speech using gTTS (fallback).
        
        Args:
            text: The text to convert to speech
            language: The language code (e.g., "en", "ja", "es")
            
        Returns:
            dict: Contains base64 encoded audio data and metadata
        """
        try:
            # Create a temporary file to store the audio
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                # Generate speech using gTTS
                tts = gTTS(text=text, lang=language, slow=False)
                tts.save(temp_file.name)
                
                # Read the generated audio file
                with open(temp_file.name, 'rb') as audio_file:
                    audio_bytes = audio_file.read()
                
                # Convert to base64
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                return {
                    "audio_data": audio_base64,
                    "format": "mp3",
                    "language": language,
                    "text_length": len(text),
                    "provider": "gtts"
                }
                
        except Exception as e:
            logger.error(f"gTTS error: {str(e)}")
            raise
        finally:
            # Clean up temporary file
            if 'temp_file' in locals():
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {str(e)}")

    async def text_to_speech(self, text: str, language: str = "en") -> dict:
        """
        Convert text to speech using ElevenLabs with gTTS fallback.
        
        Args:
            text: The text to convert to speech
            language: The language code (e.g., "en", "ja", "es")
            
        Returns:
            dict: Contains base64 encoded audio data and metadata
        """
        max_retries = 3
        retry_delay = 1  # seconds
        
        # Try ElevenLabs first if available - use configurable retry count
        if self.use_elevenlabs and settings.speech_primary_provider == "elevenlabs":
            primary_retries = settings.speech_tts_primary_retries
            for attempt in range(primary_retries):
                try:
                    logger.info(f"Attempting ElevenLabs TTS (attempt {attempt + 1}/{primary_retries})")
                    result = await self._elevenlabs_text_to_speech(text, language)
                    logger.info("✅ ElevenLabs TTS successful")
                    return result
                    
                except Exception as e:
                    logger.error(f"ElevenLabs TTS failed (attempt {attempt + 1}/{primary_retries}): {str(e)}")
                    if attempt < primary_retries - 1:
                        logger.info(f"Retrying ElevenLabs in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.warning(f"ElevenLabs TTS failed after {primary_retries} attempts, falling back to gTTS")
        
        # Fallback to gTTS if ElevenLabs failed or not configured
        if settings.speech_fallback_enabled:
            for attempt in range(max_retries):
                try:
                    logger.info(f"Using gTTS fallback (attempt {attempt + 1}/{max_retries})")
                    result = await self._gtts_text_to_speech(text, language)
                    logger.info("✅ gTTS fallback successful")
                    result["fallback_used"] = True
                    return result
                    
                except Exception as e:
                    logger.error(f"gTTS fallback failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying gTTS in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error("All TTS options failed")
                        raise Exception("All text-to-speech services failed")
        else:
            raise Exception("Primary TTS service failed and fallback is disabled")

    async def get_available_voices(self) -> dict:
        """
        Get available voices from ElevenLabs.
        
        Returns:
            dict: Available voices information
        """
        if not self.use_elevenlabs:
            return {
                "error": "ElevenLabs not available",
                "fallback_info": "Using gTTS - no voice selection available"
            }
        
        try:
            loop = asyncio.get_event_loop()
            voices = await loop.run_in_executor(
                None,
                lambda: self.elevenlabs_client.voices.get_all()
            )
            
            voice_list = []
            for voice in voices.voices:
                voice_list.append({
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": voice.category,
                    "description": getattr(voice, 'description', ''),
                    "preview_url": getattr(voice, 'preview_url', ''),
                    "available_for_tiers": getattr(voice, 'available_for_tiers', [])
                })
            
            return {
                "voices": voice_list,
                "current_voice_id": settings.elevenlabs_voice_id,
                "provider": "elevenlabs"
            }
            
        except Exception as e:
            logger.error(f"Error getting ElevenLabs voices: {str(e)}")
            return {
                "error": str(e),
                "fallback_info": "Using gTTS - no voice selection available"
            }

    async def get_service_status(self) -> dict:
        """
        Get the status of all speech services.
        
        Returns:
            dict: Status information for all services
        """
        status = {
            "primary_provider": settings.speech_primary_provider,
            "fallback_enabled": settings.speech_fallback_enabled,
            "tts_primary_retries": settings.speech_tts_primary_retries,
            "whisper_model": self.model_name,
            "device": self.device
        }
        
        # ElevenLabs status
        if ELEVENLABS_AVAILABLE and settings.elevenlabs_api_key:
            try:
                user_info = await self._test_elevenlabs_connection()
                status["elevenlabs"] = {
                    "available": True,
                    "subscription_tier": user_info.get('subscription', {}).get('tier', 'Unknown'),
                    "character_count": user_info.get('subscription', {}).get('character_count', 0),
                    "character_limit": user_info.get('subscription', {}).get('character_limit', 0),
                    "voice_id": settings.elevenlabs_voice_id,
                    "tts_model_id": settings.elevenlabs_model_id,
                    "stt_model_id": settings.elevenlabs_stt_model_id,
                    "capabilities": {
                        "text_to_speech": True,
                        "speech_to_text": True,
                        "language_detection": True,
                        "word_timestamps": True,
                        "voice_cloning": True
                    }
                }
            except Exception as e:
                status["elevenlabs"] = {
                    "available": False,
                    "error": str(e)
                }
        else:
            status["elevenlabs"] = {
                "available": False,
                "reason": "API key not configured or package not installed"
            }
        
        # Whisper status
        status["whisper"] = {
            "available": self.model is not None,
            "model": self.model_name,
            "device": self.device,
            "compute_type": self.compute_type
        }
        
        # gTTS status  
        status["gtts"] = {
            "available": True,  # gTTS is always available as fallback
            "note": "Used as TTS fallback"
        }
        
        return status 