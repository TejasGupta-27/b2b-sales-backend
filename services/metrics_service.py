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

# Error and Performance Metrics
b2b_errors_total = Counter(
    'b2b_errors_total',
    'Total errors by type',
    ['error_type', 'endpoint']
)

b2b_system_health = Gauge(
    'b2b_system_health',
    'System health status',
    ['component']
)

b2b_response_time_percentile = Histogram(
    'b2b_response_time_percentile',
    'Response time percentiles',
    ['endpoint', 'percentile']
)

# Business Performance Metrics
b2b_conversion_rate = Gauge(
    'b2b_conversion_rate',
    'Lead conversion rate',
    ['stage']
)

b2b_revenue_metrics = Counter(
    'b2b_revenue_metrics',
    'Revenue related metrics',
    ['type', 'status']
)

class MetricsService:
    def __init__(self):
        self.start_time = time.time()
    
    def record_http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        
        # Record response time percentiles
        if duration < 0.1:
            b2b_response_time_percentile.labels(endpoint=endpoint, percentile="p50").observe(duration)
        if duration < 0.5:
            b2b_response_time_percentile.labels(endpoint=endpoint, percentile="p90").observe(duration)
        if duration < 1.0:
            b2b_response_time_percentile.labels(endpoint=endpoint, percentile="p95").observe(duration)
        b2b_response_time_percentile.labels(endpoint=endpoint, percentile="p99").observe(duration)
        
        # Record errors
        if status >= 400:
            error_type = "4xx" if status < 500 else "5xx"
            b2b_errors_total.labels(error_type=error_type, endpoint=endpoint).inc()
    
    def record_chat_message(self, lead_id: str = None, message_type: str = "user"):
        """Record chat message metrics"""
        b2b_chat_messages_total.labels(
            lead_id=lead_id or "unknown",
            message_type=message_type
        ).inc()
    
    def record_quote_generation(self, status: str = "success"):
        """Record quote generation metrics"""
        b2b_quotes_generated_total.labels(status=status).inc()
        
        # Record revenue metrics for successful quotes
        if status == "success":
            b2b_revenue_metrics.labels(type="quote_generated", status="success").inc()
    
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
    
    def record_error(self, error_type: str, endpoint: str = "unknown"):
        """Record application errors"""
        b2b_errors_total.labels(error_type=error_type, endpoint=endpoint).inc()
    
    def update_system_health(self, component: str, status: int):
        """Update system health status (1=healthy, 0=unhealthy)"""
        b2b_system_health.labels(component=component).set(status)
    
    def update_conversion_rate(self, stage: str, rate: float):
        """Update lead conversion rate"""
        b2b_conversion_rate.labels(stage=stage).set(rate)
    
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
            
            # Calculate conversion rates
            total_leads = sum(count for _, count in lead_counts)
            if total_leads > 0:
                # Calculate conversion from NEW to QUALIFIED
                new_count = next((count for status, count in lead_counts if status == LeadStatus.NEW), 0)
                qualified_count = next((count for status, count in lead_counts if status == LeadStatus.QUALIFIED), 0)
                if new_count > 0:
                    conversion_rate = (qualified_count / new_count) * 100
                    self.update_conversion_rate("new_to_qualified", conversion_rate)
                
                # Calculate conversion from QUALIFIED to PROPOSAL
                proposal_count = next((count for status, count in lead_counts if status == LeadStatus.PROPOSAL), 0)
                if qualified_count > 0:
                    conversion_rate = (proposal_count / qualified_count) * 100
                    self.update_conversion_rate("qualified_to_proposal", conversion_rate)
                
                # Calculate conversion from PROPOSAL to CLOSED_WON
                closed_won_count = next((count for status, count in lead_counts if status == LeadStatus.CLOSED_WON), 0)
                if proposal_count > 0:
                    conversion_rate = (closed_won_count / proposal_count) * 100
                    self.update_conversion_rate("proposal_to_closed_won", conversion_rate)
                
        except Exception as e:
            # Log error but don't fail the application
            print(f"Error updating lead metrics: {e}")
            self.record_error("lead_metrics_update", "metrics_service")
    
    def update_db_connection_metrics(self, db: Session):
        """Update database connection metrics"""
        try:
            # This is a simplified version - you might want to get actual connection count
            # from your database connection pool
            result = db.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            active_connections = result.scalar()
            b2b_db_connections_active.set(active_connections)
            
            # Update system health for database
            self.update_system_health("database", 1)
        except Exception as e:
            print(f"Error updating DB connection metrics: {e}")
            self.update_system_health("database", 0)
            self.record_error("db_connection_metrics", "metrics_service")
    
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