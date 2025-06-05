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

logger = logging.getLogger(__name__)

class SpeechService:
    def __init__(self, model_name: str = "medium"):
        """
        Initialize the speech service with the specified Whisper model.
        
        Args:
            model_name: Name of the Whisper model to use (tiny, base, small, medium, large)
        """
        self.model_name = model_name
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.target_sr = 16000  # Whisper expects 16kHz audio
        self._session = None
        self._timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        logger.info(f"Speech service initialized with model: {model_name} on {self.device}")
    
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
        """Initialize the Whisper model."""
        try:
            # Initialize Whisper model
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                download_root="./models"
            )
            logger.info(f"✅ Whisper model {self.model_name} loaded successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize speech service: {str(e)}")
            await self.close()  # Clean up on initialization failure
            raise
    
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
        Preprocess audio data to ensure it's in the correct format for Whisper.
        
        Args:
            audio_data: Audio data as file-like object or bytes
            
        Returns:
            tuple: (audio_array, sample_rate)
        """
        try:
            # Create a temporary file to store the audio data
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                if isinstance(audio_data, bytes):
                    temp_file.write(audio_data)
                else:
                    temp_file.write(audio_data.read())
                temp_file.flush()
                
                # Load audio with librosa (handles resampling and mono conversion)
                audio_array, sr = librosa.load(
                    temp_file.name,
                    sr=self.target_sr,  # Resample to 16kHz
                    mono=True,  # Convert to mono
                    dtype=np.float32
                )
                
                # Normalize audio
                if np.abs(audio_array).max() > 1.0:
                    audio_array = audio_array / np.abs(audio_array).max()
                
                logger.info(f"Audio preprocessed: shape={audio_array.shape}, sr={sr}, dtype={audio_array.dtype}")
                return audio_array, sr
                
        except Exception as e:
            logger.error(f"Error preprocessing audio: {str(e)}")
            raise
        finally:
            # Clean up temporary file
            if 'temp_file' in locals():
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {str(e)}")
    
    async def transcribe_audio(
        self,
        audio_data: Union[BinaryIO, bytes],
        language: Optional[str] = None
    ) -> dict:
        """
        Transcribe audio data using Whisper.
        
        Args:
            audio_data: Audio data as file-like object or bytes
            language: Optional language code (e.g., "en", "ja", "es")
            
        Returns:
            dict: Contains transcription text and metadata
        """
        if self.model is None:
            await self.initialize()
            
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
                "duration": len(audio_array)/sample_rate
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    async def text_to_speech(self, text: str, language: str = "en") -> dict:
        """
        Convert text to speech using gTTS.
        
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
                    "text_length": len(text)
                }
                
        except Exception as e:
            logger.error(f"Error in text-to-speech conversion: {str(e)}")
            raise
        finally:
            # Clean up temporary file
            if 'temp_file' in locals():
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {str(e)}") 