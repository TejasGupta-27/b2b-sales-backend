# B2B Sales Backend Architecture Diagram

```mermaid
graph TB
    %% Clients
    subgraph "Clients"
        CLIENT[Frontend App]
        ADMIN[Admin Interface]
        API_CLIENT[API Clients]
    end

    %% Gateway
    subgraph "Gateway"
        NGINX[Nginx Load Balancer]
    end

    %% Application
    subgraph "FastAPI Backend"
        APP[FastAPI App]

        subgraph "Routes"
            LEADS[Leads API]
            QUOTES[Quotes API]
            CHAT[Chat API]
            ADMIN_API[Admin API]
            SPEECH[Speech API]
            RECOMMENDATIONS[Recommendations API]
        end

        subgraph "Middleware"
            CORS[CORS]
            AUTH[Authentication]
            LOG[Logging]
        end
    end

    %% Simple Conversational Agent (Main Orchestrator)
    subgraph "Simple Conversational Agent"
        SIMPLE_AGENT[Simple Conversational Agent<br/>Main Orchestrator]
        
        subgraph "Intent Analysis & Routing"
            INTENT_ANALYSIS[Conversation Intent Analysis<br/>Pydantic Model]
            LANG_DETECT[Language Detection<br/>& Localization]
            INTENT_ROUTER{Intent-Based Router}
        end
        
        subgraph "Response Generation Paths"
            QUOTE_PATH[Quote Response Generator]
            PRODUCT_PATH[Product Response Generator]
            GENERAL_PATH[General Response Generator]
        end
        
        subgraph "Specialized AI Components"
            HYBRID_RETRIEVER[Hybrid Product Retriever Agent]
            QUOTE_AGENT[Quote Generation Agent]
            CONVERSATION_MEMORY[Conversation Memory]
        end
    end

    %% AI Service Factory
    subgraph "AI Service Factory"
        AI_FACTORY[AI Service Factory]
        BASE_PROVIDER[Base AI Provider]
        
        subgraph "AI Providers"
            AZURE_PROVIDER[Azure OpenAI Provider]
            HF_PROVIDER[HuggingFace Provider]
            TOKEN_TRACKER[Token Tracker & Usage]
        end
    end

    %% External AI Services
    subgraph "External AI Services"
        AZURE_OPENAI[Azure OpenAI GPT Models]
        AZURE_EMBED[Azure Embeddings API]
        WHISPER_MODELS[Whisper Models]
    end

    %% Business Services
    subgraph "Business Services"
        ELASTICSEARCH_SVC[Elasticsearch Service]
        CHROMA_SVC[ChromaDB Service]
        PDF_SVC[PDF Generator]
        PITCH_SVC[Pitch Deck Service]
        SPEECH_SVC[Speech Service]
        PROMPT_MGR[Prompt Manager]
        METRICS_SVC[Metrics Service]
    end

    %% Data Storage
    subgraph "Storage"
        POSTGRES[(PostgreSQL DB)]
        ELASTICSEARCH[(Elasticsearch)]
        CHROMA[(ChromaDB Vector Store)]
        FILES[File Storage<br/>JSON/PDFs/Pitch Decks]
    end

    %% Monitoring
    subgraph "Monitoring"
        KIBANA[Kibana Dashboard]
        ADMINER[Adminer DB Admin]
        HEALTH[Health Checks]
    end

    %% Client Connections
    CLIENT --> NGINX
    ADMIN --> NGINX
    API_CLIENT --> NGINX
    NGINX --> APP

    %% Middleware Flow
    APP --> CORS
    APP --> AUTH
    APP --> LOG

    %% Route Connections
    APP --> LEADS
    APP --> QUOTES
    APP --> CHAT
    APP --> ADMIN_API
    APP --> SPEECH
    APP --> RECOMMENDATIONS

    %% Main Route to Simple Conversational Agent
    LEADS --> SIMPLE_AGENT
    CHAT --> SIMPLE_AGENT
    RECOMMENDATIONS --> SIMPLE_AGENT

    %% Simple Conversational Agent Internal Flow
    SIMPLE_AGENT --> INTENT_ANALYSIS
    INTENT_ANALYSIS --> LANG_DETECT
    LANG_DETECT --> INTENT_ROUTER
    
    %% Intent-Based Routing
    INTENT_ROUTER -->|Quote Intent| QUOTE_PATH
    INTENT_ROUTER -->|Product Intent| PRODUCT_PATH
    INTENT_ROUTER -->|General Intent| GENERAL_PATH
    
    %% Response Path Dependencies
    QUOTE_PATH --> QUOTE_AGENT
    QUOTE_PATH --> HYBRID_RETRIEVER
    PRODUCT_PATH --> HYBRID_RETRIEVER
    GENERAL_PATH --> CONVERSATION_MEMORY
    
    %% Component Interactions
    SIMPLE_AGENT --> CONVERSATION_MEMORY
    SIMPLE_AGENT --> BASE_PROVIDER
    HYBRID_RETRIEVER --> BASE_PROVIDER
    QUOTE_AGENT --> BASE_PROVIDER

    %% AI Factory Integration
    BASE_PROVIDER --> AI_FACTORY
    AI_FACTORY --> AZURE_PROVIDER
    AI_FACTORY --> HF_PROVIDER
    AI_FACTORY --> TOKEN_TRACKER

    %% External AI Connections
    AZURE_PROVIDER --> AZURE_OPENAI
    HYBRID_RETRIEVER --> AZURE_EMBED
    SPEECH_SVC --> WHISPER_MODELS

    %% Business Service Integration
    SIMPLE_AGENT --> PROMPT_MGR
    SIMPLE_AGENT --> METRICS_SVC
    HYBRID_RETRIEVER --> ELASTICSEARCH_SVC
    HYBRID_RETRIEVER --> CHROMA_SVC
    QUOTE_AGENT --> PDF_SVC
    QUOTE_AGENT --> PITCH_SVC
    SPEECH --> SPEECH_SVC

    %% Direct API Routes
    QUOTES --> QUOTE_AGENT
    SPEECH --> SPEECH_SVC
    ADMIN_API --> ELASTICSEARCH_SVC

    %% Data Storage Connections
    APP --> POSTGRES
    ELASTICSEARCH_SVC --> ELASTICSEARCH
    CHROMA_SVC --> CHROMA
    PDF_SVC --> FILES
    PITCH_SVC --> FILES
    APP --> FILES
    METRICS_SVC --> POSTGRES

    %% Monitoring Connections
    ELASTICSEARCH --> KIBANA
    POSTGRES --> ADMINER
    APP --> HEALTH

    %% Styling
    classDef client fill:#e3f2fd
    classDef gateway fill:#bbdefb
    classDef app fill:#e1bee7
    classDef simple_agent fill:#ffecb3
    classDef intent_analysis fill:#fff3e0
    classDef response_path fill:#f3e5f5
    classDef ai_component fill:#fff9c4
    classDef ai_factory fill:#f0f4c3
    classDef external_ai fill:#e8f5e8
    classDef service fill:#c8e6c9
    classDef storage fill:#d7ccc8
    classDef monitor fill:#f8bbd0

    class CLIENT,ADMIN,API_CLIENT client
    class NGINX gateway
    class APP,LEADS,QUOTES,CHAT,ADMIN_API,SPEECH,RECOMMENDATIONS,CORS,AUTH,LOG app
    class SIMPLE_AGENT simple_agent
    class INTENT_ANALYSIS,LANG_DETECT,INTENT_ROUTER intent_analysis
    class QUOTE_PATH,PRODUCT_PATH,GENERAL_PATH response_path
    class HYBRID_RETRIEVER,QUOTE_AGENT,CONVERSATION_MEMORY ai_component
    class AI_FACTORY,BASE_PROVIDER,AZURE_PROVIDER,HF_PROVIDER,TOKEN_TRACKER ai_factory
    class AZURE_OPENAI,AZURE_EMBED,WHISPER_MODELS external_ai
    class ELASTICSEARCH_SVC,CHROMA_SVC,PDF_SVC,PITCH_SVC,SPEECH_SVC,PROMPT_MGR,METRICS_SVC service
    class POSTGRES,ELASTICSEARCH,CHROMA,FILES storage
    class KIBANA,ADMINER,HEALTH monitor
```

## Simple Conversational Agent Architecture Analysis

### Key Architectural Components from `simple_conversational_agent.py`:

#### 1. **Simple Conversational Agent (Main Orchestrator)**
- **Conversation Orchestrator**: Manages entire conversation flow and response generation
- **Intent-Based Routing**: Uses Pydantic models to analyze and route conversations
- **Language-Aware Responses**: Detects language and provides localized responses
- **Memory Management**: Maintains conversation context and memory
- **Provider Abstraction**: Works with any base AI provider

#### 2. **Conversation Intent Analysis**
- **ConversationIntent Pydantic Model**: Structured analysis of user intent
- **Intent Types**: 'product_inquiry', 'quote_request', 'general_chat', 'technical_question', 'pricing_inquiry'
- **Confidence Scoring**: Provides confidence levels for decision-making
- **Missing Information Detection**: Identifies what information is needed
- **Conservative Product Retrieval**: Only retrieves products when explicitly needed

#### 3. **Three-Path Response Generation**
- **Quote Response Path**: Handles quote requests with missing info gathering
- **Product Response Path**: Manages product recommendations and full build suggestions
- **General Response Path**: Focuses on discovery and natural conversation flow
- **Dynamic Language Support**: Automatically detects and responds in appropriate language

#### 4. **Specialized AI Components**
- **HybridProductRetrieverAgent**: Combines Elasticsearch + ChromaDB for intelligent search
- **QuoteGenerationAgent**: Handles complex quote generation with PDF/pitch deck creation
- **Conversation Memory**: Maintains context across conversation turns

#### 5. **Intelligence Flow Management**
```mermaid
flowchart LR
    A[User Message] --> B[Simple Conversational Agent]
    B --> C[Intent Analysis<br/>Pydantic Model]
    C --> D{Intent Router}
    D -->|Quote Request| E[Quote Response Path]
    D -->|Product Inquiry| F[Product Response Path]
    D -->|General Chat| G[General Response Path]
    E --> H[Quote Generation + Enhancement]
    F --> I[Product Retrieval + Recommendation]
    G --> J[Discovery + Natural Flow]
```

#### 6. **Advanced Features**
- **Language Detection & Localization**: Supports Japanese and English responses
- **Conservative Discovery Approach**: Focuses on information gathering before product recommendations
- **Quote Enhancement**: Automatically adds quote details, PDFs, and pitch decks to responses
- **Metrics Integration**: Tracks quote generation success/failure rates
- **Error Handling**: Graceful fallbacks for AI service failures

#### 7. **Conversation Flow Strategy**
- **Natural Conversation**: Prioritizes human-like, helpful interactions
- **Discovery-First Approach**: Gathers information before making recommendations
- **Context-Aware**: Uses conversation history and customer context
- **Requirements Completion**: Tracks missing information for quotes/recommendations

## Data Flow Analysis

### 1. **Intent Analysis Flow** 