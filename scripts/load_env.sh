#!/bin/bash

# API Configuration
export API_HOST="0.0.0.0"
export API_PORT="3001"
export DEBUG="true"
export CORS_ORIGINS="http://localhost:3000"

# Database Configuration
export POSTGRES_USER="myuser"
export POSTGRES_PASSWORD="mypassword"
export POSTGRES_DB="chat_db"
export DATABASE_URL="postgresql://myuser:mypassword@db:5432/chat_db"

# Elasticsearch Configuration
export ELASTICSEARCH_URL="http://localhost:9200"
export ELASTICSEARCH_INDEX_PRODUCTS="products"
export ELASTICSEARCH_INDEX_SOLUTIONS="solutions"

# ChromaDB Configuration
export CHROMA_DB_PATH="./chroma_db"
export CHROMA_MAX_ITEMS_PER_FILE="50"

# Data directory
export DATA_DIR="Data/json"

# AI Service Configuration
export DEFAULT_AI_PROVIDER="azure_openai"

# Azure OpenAI
export AZURE_OPENAI_API_VERSION="2024-02-15-preview"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4"

# Azure Embeddings
export AZURE_EMBEDDING_DEPLOYMENT_NAME="text-embedding-ada-002"

# Hugging Face
export HUGGINGFACE_MODEL="microsoft/DialoGPT-medium"

# Data loading configuration
export FORCE_RELOAD_DATA="false"
export SKIP_DATA_LOADING="false"

# Hybrid search configuration
export USE_HYBRID_RETRIEVER="true"
export ELASTICSEARCH_WEIGHT="0.4"
export SEMANTIC_WEIGHT="0.6"

# Load sensitive variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading sensitive variables from .env file..."
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "Environment variables loaded successfully!" 