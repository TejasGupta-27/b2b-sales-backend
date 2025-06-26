from fastapi import Depends
from services.speech_service import SpeechService

# Assume speech_service is initialized in main.py
import main

async def get_speech_service():
    """Dependency to get the global speech service instance."""
    if main.speech_service is None:
        raise RuntimeError("SpeechService not initialized. Check application startup.")
    yield main.speech_service 