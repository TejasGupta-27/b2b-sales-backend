from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path
import os

class Settings(BaseSettings):
    # Disable .env file loading
    class Config:
        env_file = None
    
    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "3001"))
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    
    # New Relic Configuration
    newrelic_enabled: bool = os.getenv("NEWRELIC_ENABLED", "True").lower() == "true"
    newrelic_license_key: Optional[str] = os.getenv("NEWRELIC_LICENSE_KEY")
    newrelic_app_name: str = os.getenv("NEWRELIC_APP_NAME", "B2B Sales Backend")
    newrelic_environment: str = os.getenv("NEWRELIC_ENVIRONMENT", "development")
    
    # Performance Configuration
    enable_response_caching: bool = os.getenv("ENABLE_RESPONSE_CACHING", "True").lower() == "true"
    cache_ttl: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default
    max_concurrent_requests: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Database Configuration
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_db: str = os.getenv("POSTGRES_DB", "b2b_sales")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/b2b_sales")
    
    # Database Performance Settings
    db_echo_sql: bool = os.getenv("DB_ECHO_SQL", "False").lower() == "true"  # Disable SQL logging by default
    conversation_history_limit: int = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "20"))  # Limit chat history
    
    # Elasticsearch Configuration
    elasticsearch_url: str = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
    elasticsearch_index_products: str = os.getenv("ELASTICSEARCH_INDEX_PRODUCTS", "products")
    elasticsearch_index_solutions: str = os.getenv("ELASTICSEARCH_INDEX_SOLUTIONS", "solutions")
    
    # ChromaDB Configuration
    chroma_db_path: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    chroma_max_items_per_file: int = int(os.getenv("CHROMA_MAX_ITEMS_PER_FILE", "50"))
    
    # Data directory
    data_dir: Path = Path(os.getenv("DATA_DIR", "Data/json"))
    
    # AI Service Configuration
    default_ai_provider: str = os.getenv("DEFAULT_AI_PROVIDER", "azure_openai")
    
    # Azure OpenAI
    azure_openai_api_key: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    azure_openai_deployment_name: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1-mini")
    
    # Azure Embeddings (separate deployment)
    azure_embedding_endpoint: Optional[str] = os.getenv("AZURE_EMBEDDING_ENDPOINT")
    azure_embedding_api_key: Optional[str] = os.getenv("AZURE_EMBEDDING_API_KEY")
    azure_embedding_deployment_name: str = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")
    
    # Hugging Face
    huggingface_api_key: Optional[str] = os.getenv("HUGGINGFACE_API_KEY")
    huggingface_model: str = os.getenv("HUGGINGFACE_MODEL", "microsoft/DialoGPT-medium")
    
    # Eleven Labs Configuration
    elevenlabs_api_key: Optional[str] = os.getenv("ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Default voice (Adam)
    elevenlabs_model_id: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    elevenlabs_stt_model_id: str = os.getenv("ELEVENLABS_STT_MODEL_ID", "scribe_v1")
    elevenlabs_stability: float = float(os.getenv("ELEVENLABS_STABILITY", "0.5"))
    elevenlabs_similarity_boost: float = float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.5"))
    elevenlabs_style: float = float(os.getenv("ELEVENLABS_STYLE", "0.0"))
    elevenlabs_use_speaker_boost: bool = os.getenv("ELEVENLABS_USE_SPEAKER_BOOST", "True").lower() == "true"
    
    # Speech Service Configuration
    speech_primary_provider: str = os.getenv("SPEECH_PRIMARY_PROVIDER", "elevenlabs")  # elevenlabs or whisper
    speech_fallback_enabled: bool = os.getenv("SPEECH_FALLBACK_ENABLED", "True").lower() == "true"
    speech_tts_primary_retries: int = int(os.getenv("SPEECH_TTS_PRIMARY_RETRIES", "1"))  # Number of retries for primary TTS before fallback
    
    # Data loading configuration
    force_reload_data: bool = os.getenv("FORCE_RELOAD_DATA", "False").lower() == "true"
    skip_data_loading: bool = os.getenv("SKIP_DATA_LOADING", "False").lower() == "true"
    
    # Hybrid search configuration
    use_hybrid_retriever: bool = os.getenv("USE_HYBRID_RETRIEVER", "True").lower() == "true"
    elasticsearch_weight: float = float(os.getenv("ELASTICSEARCH_WEIGHT", "0.4"))
    semantic_weight: float = float(os.getenv("SEMANTIC_WEIGHT", "0.6"))
    
    # RRF (Reciprocal Rank Fusion) configuration for hybrid search
    use_rrf_merging: bool = os.getenv("USE_RRF_MERGING", "True").lower() == "true"
    rrf_k: float = float(os.getenv("RRF_K", "60.0"))  # RRF constant, default 60
    rrf_elasticsearch_weight: float = float(os.getenv("RRF_ELASTICSEARCH_WEIGHT", "0.5"))
    rrf_semantic_weight: float = float(os.getenv("RRF_SEMANTIC_WEIGHT", "0.5"))
    
    # Search result configuration
    max_search_results_per_source: int = int(os.getenv("MAX_SEARCH_RESULTS_PER_SOURCE", "50"))
    final_result_limit: int = int(os.getenv("FINAL_RESULT_LIMIT", "20"))
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

settings = Settings() 