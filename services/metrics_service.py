from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import ChatMessage as DBChatMessage, Lead as DBLead, LeadStatus

# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# Business Metrics
b2b_leads_total = Gauge(
    'b2b_leads_total',
    'Total number of leads by status',
    ['status']
)

b2b_chat_messages_total = Counter(
    'b2b_chat_messages_total',
    'Total number of chat messages',
    ['lead_id', 'message_type']
)

b2b_quotes_generated_total = Counter(
    'b2b_quotes_generated_total',
    'Total number of quotes generated',
    ['status']
)

b2b_ai_response_time_seconds = Histogram(
    'b2b_ai_response_time_seconds',
    'AI service response time in seconds',
    ['provider', 'model']
)

# Cache Metrics
b2b_cache_hits_total = Counter(
    'b2b_cache_hits_total',
    'Total cache hits'
)

b2b_cache_misses_total = Counter(
    'b2b_cache_misses_total',
    'Total cache misses'
)

# Database Metrics
b2b_db_connections_active = Gauge(
    'b2b_db_connections_active',
    'Active database connections'
)

# Elasticsearch Metrics
b2b_elasticsearch_queries_total = Counter(
    'b2b_elasticsearch_queries_total',
    'Total Elasticsearch queries',
    ['index', 'query_type']
)

b2b_elasticsearch_response_time_seconds = Histogram(
    'b2b_elasticsearch_response_time_seconds',
    'Elasticsearch response time in seconds',
    ['index', 'query_type']
)

class MetricsService:
    def __init__(self):
        self.start_time = time.time()
    
    def record_http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
    
    def record_chat_message(self, lead_id: str = None, message_type: str = "user"):
        """Record chat message metrics"""
        b2b_chat_messages_total.labels(
            lead_id=lead_id or "unknown",
            message_type=message_type
        ).inc()
    
    def record_quote_generation(self, status: str = "success"):
        """Record quote generation metrics"""
        b2b_quotes_generated_total.labels(status=status).inc()
    
    def record_ai_response_time(self, duration: float, provider: str = "unknown", model: str = "unknown"):
        """Record AI service response time"""
        b2b_ai_response_time_seconds.labels(provider=provider, model=model).observe(duration)
    
    def record_cache_hit(self):
        """Record cache hit"""
        b2b_cache_hits_total.inc()
    
    def record_cache_miss(self):
        """Record cache miss"""
        b2b_cache_misses_total.inc()
    
    def record_elasticsearch_query(self, index: str, query_type: str, duration: float):
        """Record Elasticsearch query metrics"""
        b2b_elasticsearch_queries_total.labels(index=index, query_type=query_type).inc()
        b2b_elasticsearch_response_time_seconds.labels(index=index, query_type=query_type).observe(duration)
    
    def update_lead_metrics(self, db: Session):
        """Update lead count metrics from database"""
        try:
            # Get lead counts by status
            lead_counts = db.query(
                DBLead.status,
                func.count(DBLead.id).label('count')
            ).group_by(DBLead.status).all()
            
            # Reset all gauges first
            for status in LeadStatus:
                b2b_leads_total.labels(status=status.value).set(0)
            
            # Set current values
            for status, count in lead_counts:
                b2b_leads_total.labels(status=status.value).set(count)
                
        except Exception as e:
            # Log error but don't fail the application
            print(f"Error updating lead metrics: {e}")
    
    def update_db_connection_metrics(self, db: Session):
        """Update database connection metrics"""
        try:
            # This is a simplified version - you might want to get actual connection count
            # from your database connection pool
            result = db.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            active_connections = result.scalar()
            b2b_db_connections_active.set(active_connections)
        except Exception as e:
            print(f"Error updating DB connection metrics: {e}")
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics as string"""
        return generate_latest()

# Global metrics service instance
metrics_service = MetricsService()

def get_metrics_service() -> MetricsService:
    """Get the global metrics service instance"""
    return metrics_service

async def metrics_middleware(request: Request, call_next):
    """FastAPI middleware to collect HTTP metrics"""
    start_time = time.time()
    
    # Process the request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Extract endpoint (remove query parameters)
    endpoint = request.url.path
    
    # Record metrics
    metrics_service.record_http_request(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code,
        duration=duration
    )
    
    return response

def metrics_endpoint():
    """FastAPI endpoint to expose Prometheus metrics"""
    return Response(
        content=metrics_service.get_metrics(),
        media_type=CONTENT_TYPE_LATEST
    ) 