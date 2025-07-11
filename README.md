# 🚀 B2B Sales AI Assistant Backend

An intelligent, multi-user B2B sales assistant powered by AI that helps sales teams manage leads, generate quotes, and automate conversations with advanced natural language processing and machine learning capabilities.

## 🌟 Features

### 🤖 AI-Powered Sales Assistant
- **Conversational AI** with Azure OpenAI integration
- **Smart Lead Management** with automated scoring and tracking
- **Dynamic Quote Generation** with PDF and PowerPoint exports
- **Hybrid Search** combining Elasticsearch and vector embeddings
- **Multi-language Support** with automatic language detection
- **Speech-to-Text & Text-to-Speech** capabilities

### 👥 Multi-User & Multi-Tenant Architecture
- **User Authentication** with JWT tokens and role-based access control
- **Organization-based Data Isolation** ensuring data privacy
- **Role Management** (Admin, Sales Manager, Sales Agent, Viewer)
- **Rate Limiting** and usage tracking per user
- **Multi-organization Support** with configurable limits

### 📊 Advanced Analytics & Monitoring
- **Real-time Performance Metrics** with Prometheus integration
- **Sales Analytics Dashboard** with conversion tracking
- **System Health Monitoring** with comprehensive logging
- **API Usage Tracking** and token consumption monitoring

### 🔧 Enterprise-Ready Features
- **Docker-based Deployment** with orchestration
- **Elasticsearch Integration** for fast product search
- **PostgreSQL Database** with optimized performance
- **Nginx Load Balancing** for high availability
- **Comprehensive API Documentation** with FastAPI

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Frontend      │    │   Nginx Proxy    │    │   FastAPI Backend   │
│   Application   │◄───┤   Load Balancer  │◄───┤   (Multi-tenant)    │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                                           │
                       ┌─────────────────────────────────────┼─────────────────────────────────────┐
                       │                                     │                                     │
                ┌──────▼──────┐                    ┌────────▼────────┐                 ┌────────▼────────┐
                │ AI Services │                    │  Business Logic │                 │     Storage     │
                │  Factory    │                    │    Services     │                 │    Backends     │
                └─────────────┘                    └─────────────────┘                 └─────────────────┘
                       │                                     │                                     │
        ┌──────────────┼──────────────┐           ┌─────────┼─────────┐               ┌─────────┼─────────┐
        │              │              │           │         │         │               │         │         │
   ┌────▼───┐   ┌─────▼─────┐  ┌─────▼─────┐ ┌───▼────┐ ┌─▼────┐ ┌─▼────┐     ┌────▼───┐ ┌───▼────┐ ┌─▼──────┐
   │ Azure  │   │Conversation│  │   Quote   │ │ Speech │ │ PDF  │ │Vector│     │Postgres│ │Elastic │ │ChromaDB│
   │OpenAI  │   │   Agent    │  │Generation │ │Service │ │ Gen  │ │Search│     │   DB   │ │ search │ │Vector  │
   └────────┘   └───────────┘  └───────────┘ └────────┘ └──────┘ └──────┘     └────────┘ └────────┘ └────────┘
```

## 🚀 Quick Start

### Prerequisites
- **Docker** and **Docker Compose**
- **Azure OpenAI** API access
- **ElevenLabs** API key (optional, for speech features)

### 1. Clone the Repository
```bash
git clone <repository-url>
cd b2b-sales-backend
```

### 2. Environment Setup
```bash
# Copy environment template
cp docker.env.example .env

# Edit .env with your configuration
nano .env
```

### 3. Configure Required Services

#### Azure OpenAI Setup
```bash
# Add to .env file
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_EMBEDDING_ENDPOINT=https://your-embedding-resource.openai.azure.com/
AZURE_EMBEDDING_API_KEY=your-embedding-api-key
```

#### Optional: ElevenLabs for Speech
```bash
# Add to .env file (optional)
ELEVENLABS_API_KEY=your-elevenlabs-api-key
```

### 4. Start the Application
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 5. Initialize the System
```bash
# Create initial admin user and organization
docker-compose exec b2b-sales-backend python scripts/setup_initial_data.py
```

### 6. Access the Application
- **API**: http://localhost:3001
- **API Documentation**: http://localhost:3001/docs
- **Kibana (Elasticsearch)**: http://localhost:5601
- **Adminer (Database)**: http://localhost:8080

## 🔐 Authentication

### Initial Login
```bash
# Default admin credentials (change immediately)
Email: admin@example.com
Password: admin123
```

### API Authentication
```bash
# Login to get access token
curl -X POST "http://localhost:3001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'

# Use token in subsequent requests
curl -H "Authorization: Bearer <your-token>" \
  "http://localhost:3001/api/leads"
```

## 📚 API Documentation

### Core Endpoints

#### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `GET /api/auth/me` - Get current user profile
- `GET /api/auth/usage` - View usage statistics

#### Lead Management
- `GET /api/leads` - List organization leads
- `POST /api/leads` - Create new lead
- `GET /api/leads/{id}` - Get lead details
- `PUT /api/leads/{id}` - Update lead

#### Conversational AI
- `POST /api/chat` - Start conversation
- `POST /api/chat/send` - Send message
- `GET /api/chat/history/{lead_id}` - Get chat history
- `POST /api/chat/search` - Search conversations

#### Quote Generation
- `POST /api/generate-quote` - Generate quote
- `POST /api/generate-quote-from-conversation/{lead_id}` - Generate from conversation

#### Speech Services
- `POST /api/speech/transcribe` - Speech-to-text
- `POST /api/speech/synthesize` - Text-to-speech

### Advanced Features
- `GET /api/recommendations` - AI recommendations
- `GET /api/admin/sales-metrics` - Sales analytics
- `GET /api/admin/performance` - System performance
- `GET /api/metrics` - Prometheus metrics

## 🛠️ Development Setup

### Local Development
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start supporting services
docker-compose up postgres elasticsearch -d

# Set environment variables
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/b2b_sales"
export ELASTICSEARCH_URL="http://localhost:9200"

# Run the application
python run.py
```

### Database Management
```bash
# Run database migrations
docker-compose exec b2b-sales-backend alembic upgrade head

# Reset database (development only)
docker-compose exec b2b-sales-backend python reset_database.py

# Create custom migration
docker-compose exec b2b-sales-backend alembic revision --autogenerate -m "description"
```

## 🔧 Configuration

### Key Environment Variables

#### Database Configuration
```bash
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/b2b_sales
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=b2b_sales
```

#### AI Service Configuration
```bash
DEFAULT_AI_PROVIDER=azure_openai
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1-mini
AZURE_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-large
```

#### Performance Tuning
```bash
USE_HYBRID_RETRIEVER=true
ELASTICSEARCH_WEIGHT=0.4
SEMANTIC_WEIGHT=0.6
CONVERSATION_HISTORY_LIMIT=20
MAX_CONCURRENT_REQUESTS=100
```

#### Security Settings
```bash
SECRET_KEY=your-secure-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60
```

## 📊 Monitoring & Analytics

### Health Checks
```bash
# Application health
curl http://localhost:3001/health

# System performance
curl http://localhost:3001/api/admin/system-performance

# Sales metrics
curl -H "Authorization: Bearer <token>" \
  http://localhost:3001/api/admin/sales-metrics
```

### Logging
- **Application logs**: `./logs/main.log`
- **Docker logs**: `docker-compose logs`
- **Elasticsearch logs**: Accessible via Kibana

### Metrics
- **Prometheus metrics**: http://localhost:3001/metrics
- **System metrics**: CPU, memory, disk usage
- **Business metrics**: Conversion rates, lead scores

## 🚢 Production Deployment

### Using Docker Compose
```bash
# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# With monitoring
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### Nginx Setup
```bash
# Configure reverse proxy
sudo ./setup-nginx-proxy.sh

# Enable SSL (recommended)
# Follow NGINX_SETUP_README.md for detailed instructions
```

### Performance Optimization
- **Database indexing**: Automated performance indexes
- **Caching**: Redis integration for response caching
- **Load balancing**: Nginx with multiple backend instances
- **CDN integration**: For static assets

## 🔍 Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check database status
docker compose exec postgres pg_isready -U postgres

# Reset database connections
docker compose restart postgres
```

#### Elasticsearch Issues
```bash
# Check Elasticsearch health
curl http://localhost:9200/_cluster/health

# Reindex data
curl -X GET http://localhost:3001/api/admin/reindex
```

#### AI Service Issues
```bash
# Verify Azure OpenAI configuration
curl -H "Authorization: Bearer <your-azure-key>" \
  "https://your-resource.openai.azure.com/openai/deployments?api-version=2025-01-01-preview"

# Check token usage
curl -H "Authorization: Bearer <app-token>" \
  http://localhost:3001/api/auth/usage
```

### Performance Issues
```bash
# Monitor system resources
docker stats

# Check application performance
curl http://localhost:3001/api/admin/performance

# Review logs for bottlenecks
docker-compose logs --tail=100 b2b-sales-backend
```

## 📖 Additional Documentation

- **[Multi-User Setup Guide](MULTI_USER_SETUP.md)** - Detailed authentication setup
- **[Architecture Documentation](architecture-diagram.md)** - System design details
- **[Performance Guide](PERFORMANCE_OPTIMIZATION_GUIDE.md)** - Optimization strategies
- **[Nginx Setup](NGINX_SETUP_README.md)** - Production proxy configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📋 Tech Stack

- **Backend**: FastAPI, Python 3.11+
- **Database**: PostgreSQL 15 with SQLAlchemy ORM
- **Search**: Elasticsearch 8.11 with vector capabilities
- **AI Services**: Azure OpenAI, ChromaDB, Sentence Transformers
- **Authentication**: JWT with bcrypt hashing
- **Speech**: ElevenLabs API, Whisper models
- **Containerization**: Docker & Docker Compose
- **Monitoring**: Prometheus, Grafana, Kibana
- **Documentation**: FastAPI automatic OpenAPI generation

## 📄 License

This project is licensed under the MIT License

## 🆘 Support

For support and questions:
- **Documentation**: Check the `/docs` endpoint when running
- **Issues**: Create an issue in the repository
- **Performance**: See the performance optimization guide
- **Security**: Follow security best practices in production

---

**Built with ❤️ for modern B2B sales teams**
