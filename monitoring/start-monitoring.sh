#!/bin/bash

# B2B Sales Backend Monitoring Stack Startup Script

echo "🚀 Starting B2B Sales Backend Monitoring Stack..."

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
    docker-compose up -d
    
    echo "⏳ Waiting for main services to be ready..."
    sleep 45
else
    echo "✅ Main application is already running"
fi

# Start monitoring services
echo "📊 Starting monitoring services..."
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for monitoring services to start
echo "⏳ Waiting for monitoring services to start..."
sleep 30

# Check service status
echo "🔍 Checking service status..."
docker-compose -f docker-compose.monitoring.yml ps

# Test metrics endpoint
echo "🔍 Testing metrics endpoint..."
sleep 10
if curl -f http://localhost:3001/metrics > /dev/null 2>&1; then
    echo "✅ Metrics endpoint is working"
else
    echo "⚠️ Metrics endpoint not responding yet (this is normal during startup)"
fi

echo ""
echo "✅ Monitoring stack started successfully!"
echo ""
echo "📊 Access URLs:"
echo "   Grafana Dashboard: http://48.210.58.7/monitoring/ (admin/admin123)"
echo "   Prometheus:        http://48.210.58.7/prometheus/"
echo "   Direct Grafana:    http://localhost:3000 (admin/admin123)"
echo "   Direct Prometheus: http://localhost:9090"
echo "   Main App:          http://48.210.58.7/api/"
echo "   Metrics Endpoint:  http://48.210.58.7/metrics"
echo ""
echo "📋 Next steps:"
echo "   1. Open Grafana at http://48.210.58.7/monitoring/"
echo "   2. Login with admin/admin123"
echo "   3. The B2B Sales Dashboard should be automatically loaded"
echo "   4. If not, import the dashboard from monitoring/grafana/dashboards/"
echo ""
echo "🔧 Management commands:"
echo "   View logs: docker-compose -f docker-compose.monitoring.yml logs -f"
echo "   Stop monitoring: docker-compose -f docker-compose.monitoring.yml down"
echo "   Restart monitoring: docker-compose -f docker-compose.monitoring.yml restart"
echo "   Stop everything: docker-compose down && docker-compose -f docker-compose.monitoring.yml down"
echo ""
echo "📈 Dashboard features:"
echo "   - Application health monitoring"
echo "   - Database performance metrics"
echo "   - Elasticsearch performance"
echo "   - Chat message analytics"
echo "   - Quote generation tracking"
echo "   - System resource usage"
echo "   - Error rate monitoring" 