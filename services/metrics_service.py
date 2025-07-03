from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import ChatMessage as DBChatMessage, Lead as DBLead, LeadStatus
import json
import os
from pathlib import Path
from datetime import datetime

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

b2b_db_health = Gauge(
    'b2b_db_health',
    'Database health status (1=healthy, 0=unhealthy)'
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

# Token Usage Metrics
b2b_token_usage_total = Gauge(
    'b2b_token_usage_total',
    'Total token usage',
    ['provider', 'model']
)

b2b_token_usage_daily = Gauge(
    'b2b_token_usage_daily',
    'Daily token usage',
    ['provider', 'model', 'date']
)

# Quotation Value Metrics
b2b_quotation_value_total = Gauge(
    'b2b_quotation_value_total',
    'Total monetary value of all quotations generated',
    ['currency']
)

class MetricsService:
    def __init__(self):
        self.start_time = time.time()
        self.token_usage_file = Path("Data/token_usage.json")
        self.quotation_values_file = Path("Data/quotation_values.json")
        
        # Track quotation values internally by currency (load from file)
        self._quotation_totals = self._load_quotation_totals()
        
        # Initialize quotation value metrics with persisted values
        for currency, total in self._quotation_totals.items():
            b2b_quotation_value_total.labels(currency=currency).set(total)
    
    def _load_quotation_totals(self) -> Dict[str, float]:
        """Load quotation totals from persistent storage"""
        try:
            if self.quotation_values_file.exists():
                with open(self.quotation_values_file, 'r') as f:
                    data = json.load(f)
                    totals = data.get('totals_by_currency', {"USD": 0.0})
                    print(f"💰 Loaded quotation totals from file: {totals}")
                    return totals
            else:
                print(f"💰 No quotation values file found, starting with defaults: {{'USD': 0.0}}")
                return {"USD": 0.0}
        except Exception as e:
            print(f"❌ Error loading quotation totals: {e}")
            return {"USD": 0.0}
    
    def _save_quotation_totals(self):
        """Save quotation totals to persistent storage"""
        try:
            # Ensure directory exists
            self.quotation_values_file.parent.mkdir(exist_ok=True)
            
            data = {
                "totals_by_currency": self._quotation_totals,
                "last_updated": time.time(),
                "last_updated_iso": datetime.now().isoformat()
            }
            
            with open(self.quotation_values_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving quotation totals: {e}")
            self.record_error("quotation_totals_save", "metrics_service")
    
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
    
    def record_quote_generation(self, status: str = "success", quote_value: float = None, currency: str = "USD"):
        """Record quote generation metrics with optional value tracking"""
        b2b_quotes_generated_total.labels(status=status).inc()
        
        # Record revenue metrics for successful quotes
        if status == "success":
            b2b_revenue_metrics.labels(type="quote_generated", status="success").inc()
            
            # Track quotation value if provided
            if quote_value is not None and quote_value > 0:
                # Initialize currency tracking if needed
                if currency not in self._quotation_totals:
                    self._quotation_totals[currency] = 0.0
                
                # Add to internal total
                self._quotation_totals[currency] += quote_value
                
                # Update Prometheus metric
                b2b_quotation_value_total.labels(currency=currency).set(self._quotation_totals[currency])
                
                # Save to persistent storage
                self._save_quotation_totals()
                
                print(f"💰 Quotation value updated: {quote_value} {currency} (Total: {self._quotation_totals[currency]} {currency})")
    
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
    
    def update_token_usage_metrics(self):
        """Update token usage metrics from token_usage.json"""
        try:
            if self.token_usage_file.exists():
                with open(self.token_usage_file, 'r') as f:
                    token_data = json.load(f)
                
                # Update total token usage
                total_tokens = token_data.get('total_tokens', 0)
                b2b_token_usage_total.labels(provider="azure_openai", model="gpt-4.1-mini").set(total_tokens)
                
                # Update daily usage
                daily_usage = token_data.get('daily_usage', {})
                for date, usage_data in daily_usage.items():
                    tokens = usage_data.get('tokens', 0)
                    b2b_token_usage_daily.labels(
                        provider="azure_openai", 
                        model="gpt-4.1-mini", 
                        date=date
                    ).set(tokens)
                
                # Update provider usage
                provider_usage = token_data.get('provider_usage', {})
                for provider, provider_data in provider_usage.items():
                    provider_tokens = provider_data.get('total_tokens', 0)
                    b2b_token_usage_total.labels(provider=provider, model="total").set(provider_tokens)
                    
                    # Update model-specific usage
                    models = provider_data.get('models', {})
                    for model, model_data in models.items():
                        model_tokens = model_data.get('total_tokens', 0)
                        b2b_token_usage_total.labels(provider=provider, model=model).set(model_tokens)
                        
        except Exception as e:
            print(f"Error updating token usage metrics: {e}")
            self.record_error("token_usage_metrics", "metrics_service")
    
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
        """Update database connection metrics with proper health check"""
        try:
            # Test database connection with a simple query
            result = db.execute("SELECT 1")
            result.fetchone()
            
            # If we get here, database is healthy
            b2b_db_health.set(1)
            self.update_system_health("database", 1)
            
            # Get active connections count
            try:
                result = db.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                active_connections = result.scalar()
                b2b_db_connections_active.set(active_connections)
            except Exception as e:
                print(f"Warning: Could not get active connections count: {e}")
                b2b_db_connections_active.set(0)
                
        except Exception as e:
            print(f"Database health check failed: {e}")
            b2b_db_health.set(0)
            self.update_system_health("database", 0)
            self.record_error("db_connection_metrics", "metrics_service")
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics as string"""
        metrics_bytes = generate_latest()
        return metrics_bytes.decode('utf-8')
    
    def update_quotation_metrics(self):
        """Update quotation value metrics from persistent storage (useful for admin operations)"""
        try:
            # Reload from file
            self._quotation_totals = self._load_quotation_totals()
            
            # Update Prometheus metrics
            for currency, total in self._quotation_totals.items():
                b2b_quotation_value_total.labels(currency=currency).set(total)
                
            print(f"💰 Quotation metrics updated from file: {self._quotation_totals}")
            
        except Exception as e:
            print(f"❌ Error updating quotation metrics: {e}")
            self.record_error("quotation_metrics_update", "metrics_service")

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