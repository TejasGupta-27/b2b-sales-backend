from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path

class Settings(BaseSettings):
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 3001
    debug: bool = True
    cors_origins: str = "http://localhost:3000"
    
    # Database Configuration
    postgres_user: str = "myuser"
    postgres_password: str = "mypassword"
    postgres_db: str = "chat_db"
    database_url: str = "postgresql://myuser:mypassword@db:5432/chat_db"
    
    # Elasticsearch Configuration
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_products: str = "products"
    elasticsearch_index_solutions: str = "solutions"
    
    # ChromaDB Configuration
    chroma_db_path: str = "./chroma_db"
    chroma_max_items_per_file: int = 50  # Limit items per JSON file
    
    # Data directory
    data_dir: Path = Path("Data/json")
    
    # AI Service Configuration
    default_ai_provider: str = "azure_openai"
    
    # Azure OpenAI
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment_name: str = "gpt-4"
    
    # Azure Embeddings (separate deployment)
    azure_embedding_endpoint: Optional[str] = None
    azure_embedding_api_key: Optional[str] = None
    azure_embedding_deployment_name: str = "text-embedding-ada-002"
    
    # Hugging Face
    huggingface_api_key: Optional[str] = None
    huggingface_model: str = "microsoft/DialoGPT-medium"
    
    # Data loading configuration
    force_reload_data: bool = False
    skip_data_loading: bool = False
    
    # Hybrid search configuration
    use_hybrid_retriever: bool = True
    elasticsearch_weight: float = 0.4  # Weight for keyword search
    semantic_weight: float = 0.6       # Weight for semantic search
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    class Config:
        env_file = ".env"

settings = Settings() 