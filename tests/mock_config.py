from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DEFAULT_LANGUAGE: str = "en"
    LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD: float = 0.8
    ENABLE_AUTO_LANGUAGE_DETECTION: bool = True

settings = Settings()
