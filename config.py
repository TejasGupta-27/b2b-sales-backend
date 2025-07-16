from pydantic_settings import BaseSettings
from typing import List, Optional, ClassVar
from pathlib import Path
import os

class Settings(BaseSettings):
    # Disable .env file loading
    class Config:
        env_file = None
    
    # Authentication & Security Configuration
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-please-use-a-secure-random-key")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    password_min_length: int = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    
    # Multi-user & Organization Settings
    enable_user_registration: bool = os.getenv("ENABLE_USER_REGISTRATION", "True").lower() == "true"
    default_organization_max_users: int = int(os.getenv("DEFAULT_ORG_MAX_USERS", "5"))
    default_organization_max_leads: int = int(os.getenv("DEFAULT_ORG_MAX_LEADS", "1000"))
    default_user_api_rate_limit: int = int(os.getenv("DEFAULT_USER_API_RATE_LIMIT", "1000"))
    default_user_ai_token_limit: int = int(os.getenv("DEFAULT_USER_AI_TOKEN_LIMIT", "50000"))
    
    # Rate Limiting
    enable_rate_limiting: bool = os.getenv("ENABLE_RATE_LIMITING", "True").lower() == "true"
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    rate_limit_burst: int = int(os.getenv("RATE_LIMIT_BURST", "100"))
    
    # Multilingual Configuration
    SUPPORTED_LANGUAGES: ClassVar[list[str]] = ["en", "ja", "es", "fr", "de", "it", "pt", "ko", "zh"]
    DEFAULT_LANGUAGE: ClassVar[str] = "en"
    LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD: ClassVar[float] = 0.8
    ENABLE_AUTO_LANGUAGE_DETECTION: ClassVar[bool] = True
    
    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "3001"))
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    
    # Performance Configuration
    enable_response_caching: bool = os.getenv("ENABLE_RESPONSE_CACHING", "True").lower() == "true"
    cache_ttl: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default
    max_concurrent_requests: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Database Configuration
    postgres_user: str = os.getenv("POSTGRES_USER", "myuser")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "mypassword")
    postgres_db: str = os.getenv("POSTGRES_DB", "chat_db")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@db:5432/chat_db")
    
    # Database Performance Settings
    db_echo_sql: bool = os.getenv("DB_ECHO_SQL", "False").lower() == "true"  # Disable SQL logging by default
    conversation_history_limit: int = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "20"))  # Limit chat history
    
    # Elasticsearch Configuration
    elasticsearch_url: str = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
    elasticsearch_index_products: str = os.getenv("ELASTICSEARCH_INDEX_PRODUCTS", "products")
    elasticsearch_index_solutions: str = os.getenv("ELASTICSEARCH_INDEX_SOLUTIONS", "solutions")
    
    # Vector Search Configuration  
    use_hybrid_retriever: bool = os.getenv("USE_HYBRID_RETRIEVER", "true").lower() == "true"
    elasticsearch_weight: float = float(os.getenv("ELASTICSEARCH_WEIGHT", "0.4"))
    semantic_weight: float = float(os.getenv("SEMANTIC_WEIGHT", "0.6"))

    # RRF (Reciprocal Rank Fusion) Configuration
    enable_ai_enhanced_search: bool = os.getenv("ENABLE_AI_ENHANCED_SEARCH", "true").lower() == "true"
    use_rrf_merging: bool = os.getenv("USE_RRF_MERGING", "true").lower() == "true"
    rrf_k: float = float(os.getenv("RRF_K", "60"))
    rrf_elasticsearch_weight: float = float(os.getenv("RRF_ELASTICSEARCH_WEIGHT", "0.5"))
    rrf_semantic_weight: float = float(os.getenv("RRF_SEMANTIC_WEIGHT", "0.5"))
    final_result_limit: int = int(os.getenv("FINAL_RESULT_LIMIT", "20"))
    
    # Data Configuration
    data_dir: str = os.getenv("DATA_DIR", "Data/json")
    force_reload_data: bool = os.getenv("FORCE_RELOAD_DATA", "false").lower() == "true"
    skip_data_loading: bool = os.getenv("SKIP_DATA_LOADING", "false").lower() == "true"
    chroma_max_items_per_file: int = int(os.getenv("CHROMA_MAX_ITEMS_PER_FILE", "50"))
    
    # AI Service Configuration
    default_ai_provider: str = os.getenv("DEFAULT_AI_PROVIDER", "azure_openai")
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    azure_openai_deployment_name: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1-mini")
    
    # Azure Embedding Configuration
    azure_embedding_endpoint: str = os.getenv("AZURE_EMBEDDING_ENDPOINT", "")
    azure_embedding_api_key: str = os.getenv("AZURE_EMBEDDING_API_KEY", "")
    azure_embedding_deployment_name: str = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")
    
    # ChromaDB Configuration
    chroma_db_path: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    
    # Speech Configuration  
    disable_speech_service: bool = os.getenv("DISABLE_SPEECH_SERVICE", "false").lower() == "true"
    disable_speech_on_high_cpu: bool = os.getenv("DISABLE_SPEECH_ON_HIGH_CPU", "true").lower() == "true"
    cpu_threshold_for_speech_disable: float = float(os.getenv("CPU_THRESHOLD_FOR_SPEECH_DISABLE", "80.0"))
    
    # ElevenLabs Configuration
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    elevenlabs_model_id: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    elevenlabs_stt_model_id: str = os.getenv("ELEVENLABS_STT_MODEL_ID", "eleven_multilingual_v1")
    elevenlabs_stability: float = float(os.getenv("ELEVENLABS_STABILITY", "0.5"))
    elevenlabs_similarity_boost: float = float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.5"))
    elevenlabs_style: float = float(os.getenv("ELEVENLABS_STYLE", "0.0"))
    elevenlabs_use_speaker_boost: bool = os.getenv("ELEVENLABS_USE_SPEAKER_BOOST", "true").lower() == "true"
    
    # Speech Service Configuration
    speech_primary_provider: str = os.getenv("SPEECH_PRIMARY_PROVIDER", "elevenlabs")
    speech_fallback_enabled: bool = os.getenv("SPEECH_FALLBACK_ENABLED", "true").lower() == "true"
    speech_tts_primary_retries: int = int(os.getenv("SPEECH_TTS_PRIMARY_RETRIES", "1"))
    
    # Debug Configuration
    enable_debug_vector_endpoints: bool = os.getenv("ENABLE_DEBUG_VECTOR_ENDPOINTS", "false").lower() == "true"
    
    # Logging Configuration
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file_enabled: bool = os.getenv("LOG_FILE_ENABLED", "True").lower() == "true"
    log_file_path: str = os.getenv("LOG_FILE_PATH", "logs/app.log")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS origins string to list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def is_ai_service_configured(self) -> bool:
        """Check if AI service is properly configured"""
        if self.default_ai_provider == "azure_openai":
            return bool(self.azure_openai_endpoint and self.azure_openai_api_key)
        return False
    
    def is_embedding_service_configured(self) -> bool:
        """Check if embedding service is properly configured"""
        return bool(self.azure_embedding_endpoint and self.azure_embedding_api_key)
    
    def is_speech_service_configured(self) -> bool:
        """Check if speech service is properly configured"""
        return bool(self.elevenlabs_api_key)

# Create global settings instance
settings = Settings() 