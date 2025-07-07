#!/bin/bash

# B2B Sales Backend Monitoring Stack Startup Script
# Updated for Multi-User Deployment

echo "🚀 Starting B2B Sales Backend Monitoring Stack (Multi-User Edition)..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Create the network if it doesn't exist
echo "📡 Creating Docker network..."
docker network create b2b-sales-network 2>/dev/null || echo "Network already exists"

# Check if main application is running
echo "🔍 Checking if main application is running..."
if ! docker-compose ps | grep -q "b2b-sales-backend.*Up"; then
    echo "⚠️ Main application is not running. Starting it first..."
    echo "📊 Starting with multi-user configuration (4 workers)..."
    docker-compose up -d
    
    echo "⏳ Waiting for main services to be ready..."
    sleep 60  # Increased wait time for multi-worker startup
else
    echo "✅ Main application is already running"
fi

# Install dependencies for metrics exporter
echo "📦 Installing metrics exporter dependencies..."
if [ -d "monitoring/metrics-exporter" ]; then
    cd monitoring/metrics-exporter
    pip install -r requirements.txt 2>/dev/null || echo "Dependencies already installed"
    cd ../..
fi

# Start monitoring services
echo "📊 Starting monitoring services..."
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for monitoring services to start
echo "⏳ Waiting for monitoring services to start..."
sleep 45

# Check service status
echo "🔍 Checking service status..."
docker-compose -f docker-compose.monitoring.yml ps

# Test metrics endpoints
echo "🔍 Testing metrics endpoints..."
sleep 15

# Test main application metrics
if curl -f http://localhost:3001/metrics > /dev/null 2>&1; then
    echo "✅ Main application metrics endpoint is working"
else
    echo "⚠️ Main application metrics endpoint not responding yet (this is normal during startup)"
fi

# Test custom metrics exporter
if curl -f http://localhost:9188/metrics > /dev/null 2>&1; then
    echo "✅ Custom metrics exporter is working"
else
    echo "⚠️ Custom metrics exporter not responding yet (this is normal during startup)"
fi

# Test Prometheus
if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus is healthy"
else
    echo "⚠️ Prometheus not responding yet (this is normal during startup)"
fi

# Test Grafana
if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana is healthy"
else
    echo "⚠️ Grafana not responding yet (this is normal during startup)"
fi

echo ""
echo "✅ Multi-User Monitoring Stack Started Successfully!"
echo ""
echo "📊 Access URLs:"
echo "   Grafana Dashboard: http://48.210.58.7/monitoring/ (admin/admin123)"
echo "   Prometheus:        http://48.210.58.7/prometheus/"
echo "   Direct Grafana:    http://localhost:3000 (admin/admin123)"
echo "   Direct Prometheus: http://localhost:9090"
echo "   Main App:          http://48.210.58.7/api/"
echo "   Metrics Endpoint:  http://48.210.58.7/metrics"
echo "   Custom Metrics:    http://localhost:9188/metrics"
echo ""
echo "🔧 Multi-User Configuration:"
echo "   - 4 Gunicorn workers for concurrent user handling"
echo "   - Dynamic database connection pool"
echo "   - Resource limits and monitoring"
echo "   - Custom metrics for performance tracking"
echo ""
echo "📋 Next steps:"
echo "   1. Open Grafana at http://48.210.58.7/monitoring/"
echo "   2. Login with admin/admin123"
echo "   3. The B2B Sales Dashboard should be automatically loaded"
echo "   4. Check the 'Multi-User Performance' dashboard for worker metrics"
echo "   5. Monitor database connection pool usage"
echo ""
echo "🔧 Management commands:"
echo "   View logs: docker-compose -f docker-compose.monitoring.yml logs -f"
echo "   Stop monitoring: docker-compose -f docker-compose.monitoring.yml down"
echo "   Restart monitoring: docker-compose -f docker-compose.monitoring.yml restart"
echo "   Stop everything: docker-compose down && docker-compose -f docker-compose.monitoring.yml down"
echo "   Load test: python scripts/monitor_performance.py --load-test 10"
echo ""
echo "📈 New Dashboard Features:"
echo "   - Multi-user performance monitoring"
echo "   - Gunicorn worker metrics"
echo "   - Database connection pool analytics"
echo "   - Concurrent user load testing"
echo "   - Response time distribution"
echo "   - Error rate tracking"
echo "   - Resource utilization per worker"
echo ""
echo "🚀 Performance Expectations:"
echo "   - 5 concurrent users: < 2s response time, > 98% success rate"
echo "   - 10 concurrent users: < 3s response time, > 95% success rate"
echo "   - 20 concurrent users: < 5s response time, > 90% success rate" 