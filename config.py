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
    
    # Database Configuration
    postgres_user: str = os.getenv("POSTGRES_USER", "myuser")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "mypassword")
    postgres_db: str = os.getenv("POSTGRES_DB", "chat_db")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@db:5432/chat_db")
    
    # Elasticsearch Configuration
    elasticsearch_url: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
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
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    azure_openai_deployment_name: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
    
    # Azure Embeddings (separate deployment)
    azure_embedding_endpoint: Optional[str] = os.getenv("AZURE_EMBEDDING_ENDPOINT")
    azure_embedding_api_key: Optional[str] = os.getenv("AZURE_EMBEDDING_API_KEY")
    azure_embedding_deployment_name: str = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-ada-002")
    
    # Hugging Face
    huggingface_api_key: Optional[str] = os.getenv("HUGGINGFACE_API_KEY")
    huggingface_model: str = os.getenv("HUGGINGFACE_MODEL", "microsoft/DialoGPT-medium")
    
    # Data loading configuration
    force_reload_data: bool = os.getenv("FORCE_RELOAD_DATA", "False").lower() == "true"
    skip_data_loading: bool = os.getenv("SKIP_DATA_LOADING", "False").lower() == "true"
    
    # Hybrid search configuration
    use_hybrid_retriever: bool = os.getenv("USE_HYBRID_RETRIEVER", "True").lower() == "true"
    elasticsearch_weight: float = float(os.getenv("ELASTICSEARCH_WEIGHT", "0.4"))
    semantic_weight: float = float(os.getenv("SEMANTIC_WEIGHT", "0.6"))
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

settings = Settings() 