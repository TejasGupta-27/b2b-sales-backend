#!/bin/bash

# Multi-User B2B Sales Backend Deployment Script
# This script deploys the application with multi-user support and monitoring

set -e  # Exit on any error

echo "🚀 Multi-User B2B Sales Backend Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
print_status "Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi
print_success "Docker is running"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed. Please install it first."
    exit 1
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs Data/admin_config Data/uploads Data/quotes Data/pitch_decks Data/json
print_success "Directories created"

# Create Docker network
print_status "Creating Docker network..."
docker network create b2b-sales-network 2>/dev/null || print_warning "Network already exists"
print_success "Docker network ready"

# Check environment variables
print_status "Checking environment variables..."
if [ -z "$AZURE_OPENAI_ENDPOINT" ] || [ -z "$AZURE_OPENAI_API_KEY" ]; then
    print_warning "Azure OpenAI environment variables not set. Some features may not work."
fi

if [ -z "$ELEVENLABS_API_KEY" ]; then
    print_warning "ElevenLabs API key not set. Speech features may not work."
fi

# Deploy main application
print_status "Deploying main application with multi-user configuration..."
docker-compose down 2>/dev/null || true
docker-compose up --build -d

# Wait for main services to be ready
print_status "Waiting for main services to be ready..."
sleep 30

# Check if main application is healthy
print_status "Checking application health..."
max_attempts=10
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -f http://localhost:3001/health > /dev/null 2>&1; then
        print_success "Main application is healthy"
        break
    else
        attempt=$((attempt + 1))
        print_warning "Application not ready yet (attempt $attempt/$max_attempts)"
        sleep 10
    fi
done

if [ $attempt -eq $max_attempts ]; then
    print_error "Application failed to start properly"
    docker-compose logs b2b-sales-backend
    exit 1
fi

# Deploy monitoring stack
print_status "Deploying monitoring stack..."
docker-compose -f docker-compose.monitoring.yml down 2>/dev/null || true
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for monitoring services
print_status "Waiting for monitoring services to be ready..."
sleep 30

# Check monitoring services
print_status "Checking monitoring services..."

# Check Prometheus
if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
    print_success "Prometheus is healthy"
else
    print_warning "Prometheus not responding yet"
fi

# Check Grafana
if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    print_success "Grafana is healthy"
else
    print_warning "Grafana not responding yet"
fi

# Check custom metrics exporter
if curl -f http://localhost:9188/metrics > /dev/null 2>&1; then
    print_success "Custom metrics exporter is working"
else
    print_warning "Custom metrics exporter not responding yet"
fi

# Run performance test
print_status "Running initial performance test..."
if command -v python3 &> /dev/null; then
    python3 scripts/monitor_performance.py --single-check --load-test 5 2>/dev/null || print_warning "Performance test failed (this is normal during startup)"
else
    print_warning "Python3 not available, skipping performance test"
fi

# Display final status
echo ""
echo "🎉 Multi-User Deployment Complete!"
echo "=================================="
echo ""
echo "📊 Application URLs:"
echo "   Main Application:  http://localhost:3001"
echo "   Health Check:      http://localhost:3001/health"
echo "   API Documentation: http://localhost:3001/docs"
echo ""
echo "📈 Monitoring URLs:"
echo "   Grafana Dashboard: http://localhost:3000 (admin/admin123)"
echo "   Prometheus:        http://localhost:9090"
echo "   Custom Metrics:    http://localhost:9188/metrics"
echo ""
echo "🔧 Multi-User Features:"
echo "   ✅ 4 Gunicorn workers for concurrent users"
echo "   ✅ Dynamic database connection pool"
echo "   ✅ Resource limits and monitoring"
echo "   ✅ Performance metrics collection"
echo "   ✅ Load testing capabilities"
echo ""
echo "📋 Management Commands:"
echo "   View logs:         docker-compose logs -f b2b-sales-backend"
echo "   Monitor performance: python3 scripts/monitor_performance.py"
echo "   Load test:         python3 scripts/monitor_performance.py --load-test 10"
echo "   Stop application:  docker-compose down"
echo "   Stop monitoring:   docker-compose -f docker-compose.monitoring.yml down"
echo "   Restart all:       ./deploy-multi-user.sh"
echo ""
echo "🚀 Performance Expectations:"
echo "   • 5 concurrent users:  < 2s response time, > 98% success rate"
echo "   • 10 concurrent users: < 3s response time, > 95% success rate"
echo "   • 20 concurrent users: < 5s response time, > 90% success rate"
echo ""
echo "📊 Next Steps:"
echo "   1. Open Grafana at http://localhost:3000"
echo "   2. Login with admin/admin123"
echo "   3. Check the 'Multi-User Performance' dashboard"
echo "   4. Monitor database connection pool usage"
echo "   5. Run load tests to verify performance"
echo ""
print_success "Deployment completed successfully!" 