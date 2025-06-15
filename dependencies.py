from fastapi import Depends
from services.speech_service import SpeechService

async def get_speech_service():
    """Dependency to get speech service instance."""
    service = SpeechService(model_name="medium")
    await service.initialize()
    try:
        yield service
    except Exception as e:
        raise e
    finally:
        await service.close() 