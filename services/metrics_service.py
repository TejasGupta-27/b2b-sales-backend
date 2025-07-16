from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, text
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

# Sales-Focused Metrics
b2b_product_recommendations_total = Counter(
    'b2b_product_recommendations_total',
    'Total product recommendations generated',
    ['category', 'status']
)

b2b_product_selections_total = Counter(
    'b2b_product_selections_total',
    'Total product selections by customers',
    ['category', 'product_id']
)

b2b_quotation_line_items_total = Counter(
    'b2b_quotation_line_items_total',
    'Total line items in quotations',
    ['category', 'status']
)

b2b_quotation_quantities_total = Counter(
    'b2b_quotation_quantities_total',
    'Total quantities of products in quotations',
    ['category', 'product_id']
)

b2b_sales_funnel_stage = Gauge(
    'b2b_sales_funnel_stage',
    'Number of leads at each sales funnel stage',
    ['stage', 'status']
)

b2b_customer_engagement_score = Gauge(
    'b2b_customer_engagement_score',
    'Customer engagement score based on interaction patterns',
    ['lead_id', 'engagement_type']
)

b2b_conversation_duration_minutes = Histogram(
    'b2b_conversation_duration_minutes',
    'Duration of sales conversations in minutes',
    ['lead_id', 'outcome']
)

b2b_product_view_duration_seconds = Histogram(
    'b2b_product_view_duration_seconds',
    'Time spent viewing product recommendations',
    ['category', 'product_id']
)

b2b_quote_request_to_generation_seconds = Histogram(
    'b2b_quote_request_to_generation_seconds',
    'Time from quote request to generation',
    ['lead_id']
)

b2b_recommendation_quality_score = Gauge(
    'b2b_recommendation_quality_score',
    'Quality score of product recommendations',
    ['category', 'recommendation_set_id']
)

b2b_customer_satisfaction_score = Gauge(
    'b2b_customer_satisfaction_score',
    'Customer satisfaction score based on feedback',
    ['lead_id', 'interaction_type']
)

b2b_sales_velocity = Gauge(
    'b2b_sales_velocity',
    'Sales velocity metrics (deals per day, average deal size, etc.)',
    ['metric_type']
)

b2b_top_products_recommended = Counter(
    'b2b_top_products_recommended',
    'Most frequently recommended products',
    ['product_id', 'product_name', 'category']
)

b2b_top_products_selected = Counter(
    'b2b_top_products_selected',
    'Most frequently selected products',
    ['product_id', 'product_name', 'category']
)

b2b_average_quote_value = Gauge(
    'b2b_average_quote_value',
    'Average quote value by category and time period',
    ['category', 'period']
)

b2b_conversion_by_category = Counter(
    'b2b_conversion_by_category',
    'Conversion rates by product category',
    ['category', 'from_stage', 'to_stage']
)

b2b_customer_lifetime_value = Gauge(
    'b2b_customer_lifetime_value',
    'Customer lifetime value metrics',
    ['lead_id', 'calculation_type']
)

b2b_sales_cycle_duration_days = Histogram(
    'b2b_sales_cycle_duration_days',
    'Duration of sales cycles in days',
    ['category', 'deal_size_range']
)

b2b_quote_acceptance_rate = Gauge(
    'b2b_quote_acceptance_rate',
    'Quote acceptance rate by category and time period',
    ['category', 'period']
)

b2b_product_bundle_recommendations = Counter(
    'b2b_product_bundle_recommendations',
    'Product bundle recommendations',
    ['bundle_type', 'category_combination']
)

b2b_customer_feedback_sentiment = Gauge(
    'b2b_customer_feedback_sentiment',
    'Customer feedback sentiment scores',
    ['lead_id', 'feedback_type']
)

b2b_sales_rep_performance = Gauge(
    'b2b_sales_rep_performance',
    'Sales representative performance metrics',
    ['rep_id', 'metric_type']
)

b2b_lead_source_effectiveness = Counter(
    'b2b_lead_source_effectiveness',
    'Lead source effectiveness metrics',
    ['source', 'conversion_stage']
)

b2b_product_cross_sell_opportunities = Counter(
    'b2b_product_cross_sell_opportunities',
    'Cross-sell opportunities identified',
    ['primary_category', 'cross_sell_category']
)

b2b_upsell_opportunities = Counter(
    'b2b_upsell_opportunities',
    'Upsell opportunities identified',
    ['category', 'upsell_type']
)

b2b_customer_churn_risk = Gauge(
    'b2b_customer_churn_risk',
    'Customer churn risk assessment',
    ['lead_id', 'risk_factors']
)

b2b_sales_forecast_accuracy = Gauge(
    'b2b_sales_forecast_accuracy',
    'Sales forecast accuracy metrics',
    ['forecast_period', 'category']
)

b2b_competitive_analysis_metrics = Counter(
    'b2b_competitive_analysis_metrics',
    'Competitive analysis metrics',
    ['competitor', 'metric_type']
)

b2b_market_trend_indicators = Gauge(
    'b2b_market_trend_indicators',
    'Market trend indicators',
    ['trend_type', 'category']
)

# Add new organization and user metrics after the existing metrics definitions

# Organization Metrics
b2b_organizations_total = Gauge(
    'b2b_organizations_total',
    'Total number of organizations by type and status',
    ['org_type', 'is_active']
)

b2b_organization_users_count = Gauge(
    'b2b_organization_users_count',
    'Number of users per organization',
    ['organization_id', 'organization_name', 'org_type']
)

b2b_organization_leads_count = Gauge(
    'b2b_organization_leads_count',
    'Number of leads per organization',
    ['organization_id', 'organization_name', 'org_type', 'lead_status']
)

b2b_organization_quota_utilization = Gauge(
    'b2b_organization_quota_utilization',
    'Organization quota utilization percentage',
    ['organization_id', 'organization_name', 'quota_type']
)

b2b_organization_activity_score = Gauge(
    'b2b_organization_activity_score',
    'Organization activity score based on recent actions',
    ['organization_id', 'organization_name', 'org_type']
)

b2b_organization_revenue_metrics = Gauge(
    'b2b_organization_revenue_metrics',
    'Revenue metrics per organization',
    ['organization_id', 'organization_name', 'metric_type', 'currency']
)

# User Metrics
b2b_users_total = Gauge(
    'b2b_users_total',
    'Total number of users by role and status',
    ['role', 'is_active', 'is_verified']
)

b2b_user_session_duration = Histogram(
    'b2b_user_session_duration',
    'User session duration in minutes',
    ['user_id', 'user_role', 'organization_id']
)

b2b_user_api_usage = Counter(
    'b2b_user_api_usage',
    'API usage per user',
    ['user_id', 'user_email', 'organization_id', 'endpoint', 'method']
)

b2b_user_activity_score = Gauge(
    'b2b_user_activity_score',
    'User activity score based on recent actions',
    ['user_id', 'user_email', 'user_role', 'organization_id']
)

b2b_user_leads_managed = Gauge(
    'b2b_user_leads_managed',
    'Number of leads managed by each user',
    ['user_id', 'user_email', 'user_role', 'organization_id', 'lead_status']
)

b2b_user_quotes_generated = Counter(
    'b2b_user_quotes_generated',
    'Number of quotes generated by each user',
    ['user_id', 'user_email', 'organization_id', 'quote_status']
)

b2b_user_last_login = Gauge(
    'b2b_user_last_login',
    'Timestamp of user last login (Unix timestamp)',
    ['user_id', 'user_email', 'user_role', 'organization_id']
)

b2b_user_token_consumption = Gauge(
    'b2b_user_token_consumption',
    'AI token consumption per user',
    ['user_id', 'user_email', 'organization_id', 'provider', 'model']
)

b2b_user_performance_metrics = Gauge(
    'b2b_user_performance_metrics',
    'User performance metrics (conversion rates, etc.)',
    ['user_id', 'user_email', 'organization_id', 'metric_type']
)

# Multi-tenancy Metrics
b2b_tenant_isolation_health = Gauge(
    'b2b_tenant_isolation_health',
    'Tenant isolation health check (1=healthy, 0=issues)',
    ['organization_id', 'check_type']
)

b2b_cross_tenant_activity = Counter(
    'b2b_cross_tenant_activity',
    'Cross-tenant activity monitoring for security',
    ['source_org_id', 'target_org_id', 'activity_type']
)

# User Engagement Metrics
b2b_user_feature_usage = Counter(
    'b2b_user_feature_usage',
    'Feature usage per user',
    ['user_id', 'organization_id', 'feature', 'action']
)

b2b_user_chat_interactions = Counter(
    'b2b_user_chat_interactions',
    'Chat interactions per user',
    ['user_id', 'organization_id', 'interaction_type']
)

b2b_user_recommendation_engagement = Gauge(
    'b2b_user_recommendation_engagement',
    'User engagement with product recommendations',
    ['user_id', 'organization_id', 'engagement_type']
)

# Organization Subscription Metrics
b2b_organization_subscription_health = Gauge(
    'b2b_organization_subscription_health',
    'Organization subscription health and limits',
    ['organization_id', 'organization_name', 'limit_type']
)

b2b_organization_feature_adoption = Gauge(
    'b2b_organization_feature_adoption',
    'Feature adoption rate per organization',
    ['organization_id', 'organization_name', 'feature', 'adoption_rate']
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
    
    # Sales-Focused Methods
    def record_product_recommendation(self, category: str, product_id: str, product_name: str, status: str = "generated"):
        """Record product recommendation metrics"""
        b2b_product_recommendations_total.labels(category=category, status=status).inc()
        b2b_top_products_recommended.labels(
            product_id=product_id, 
            product_name=product_name, 
            category=category
        ).inc()
    
    def record_product_selection(self, category: str, product_id: str, product_name: str, quantity: int = 1):
        """Record product selection metrics"""
        b2b_product_selections_total.labels(category=category, product_id=product_id).inc()
        b2b_top_products_selected.labels(
            product_id=product_id, 
            product_name=product_name, 
            category=category
        ).inc()
        b2b_quotation_quantities_total.labels(category=category, product_id=product_id).inc(quantity)
    
    def record_quotation_line_item(self, category: str, status: str = "added"):
        """Record quotation line item metrics"""
        b2b_quotation_line_items_total.labels(category=category, status=status).inc()
    
    def record_sales_funnel_stage(self, stage: str, status: str, count: int = 1):
        """Record sales funnel stage metrics"""
        b2b_sales_funnel_stage.labels(stage=stage, status=status).set(count)
    
    def record_customer_engagement(self, lead_id: str, engagement_type: str, score: float):
        """Record customer engagement metrics"""
        b2b_customer_engagement_score.labels(lead_id=lead_id, engagement_type=engagement_type).set(score)
    
    def record_conversation_duration(self, lead_id: str, duration_minutes: float, outcome: str):
        """Record conversation duration metrics"""
        b2b_conversation_duration_minutes.labels(lead_id=lead_id, outcome=outcome).observe(duration_minutes)
    
    def record_product_view_duration(self, category: str, product_id: str, duration_seconds: float):
        """Record product view duration metrics"""
        b2b_product_view_duration_seconds.labels(category=category, product_id=product_id).observe(duration_seconds)
    
    def record_quote_request_to_generation(self, lead_id: str, duration_seconds: float):
        """Record time from quote request to generation"""
        b2b_quote_request_to_generation_seconds.labels(lead_id=lead_id).observe(duration_seconds)
    
    def record_recommendation_quality(self, category: str, recommendation_set_id: str, quality_score: float):
        """Record recommendation quality metrics"""
        b2b_recommendation_quality_score.labels(category=category, recommendation_set_id=recommendation_set_id).set(quality_score)
    
    def record_customer_satisfaction(self, lead_id: str, interaction_type: str, satisfaction_score: float):
        """Record customer satisfaction metrics"""
        b2b_customer_satisfaction_score.labels(lead_id=lead_id, interaction_type=interaction_type).set(satisfaction_score)
    
    def record_sales_velocity(self, metric_type: str, value: float):
        """Record sales velocity metrics"""
        b2b_sales_velocity.labels(metric_type=metric_type).set(value)
    
    def record_average_quote_value(self, category: str, period: str, average_value: float):
        """Record average quote value metrics"""
        b2b_average_quote_value.labels(category=category, period=period).set(average_value)
    
    def record_conversion_by_category(self, category: str, from_stage: str, to_stage: str):
        """Record conversion metrics by category"""
        b2b_conversion_by_category.labels(category=category, from_stage=from_stage, to_stage=to_stage).inc()
    
    def record_customer_lifetime_value(self, lead_id: str, calculation_type: str, clv: float):
        """Record customer lifetime value metrics"""
        b2b_customer_lifetime_value.labels(lead_id=lead_id, calculation_type=calculation_type).set(clv)
    
    def record_sales_cycle_duration(self, category: str, deal_size_range: str, duration_days: float):
        """Record sales cycle duration metrics"""
        b2b_sales_cycle_duration_days.labels(category=category, deal_size_range=deal_size_range).observe(duration_days)
    
    def record_quote_acceptance_rate(self, category: str, period: str, acceptance_rate: float):
        """Record quote acceptance rate metrics"""
        b2b_quote_acceptance_rate.labels(category=category, period=period).set(acceptance_rate)
    
    def record_product_bundle_recommendation(self, bundle_type: str, category_combination: str):
        """Record product bundle recommendation metrics"""
        b2b_product_bundle_recommendations.labels(bundle_type=bundle_type, category_combination=category_combination).inc()
    
    def record_customer_feedback_sentiment(self, lead_id: str, feedback_type: str, sentiment_score: float):
        """Record customer feedback sentiment metrics"""
        b2b_customer_feedback_sentiment.labels(lead_id=lead_id, feedback_type=feedback_type).set(sentiment_score)
    
    def record_sales_rep_performance(self, rep_id: str, metric_type: str, performance_score: float):
        """Record sales representative performance metrics"""
        b2b_sales_rep_performance.labels(rep_id=rep_id, metric_type=metric_type).set(performance_score)
    
    def record_lead_source_effectiveness(self, source: str, conversion_stage: str):
        """Record lead source effectiveness metrics"""
        b2b_lead_source_effectiveness.labels(source=source, conversion_stage=conversion_stage).inc()
    
    def record_cross_sell_opportunity(self, primary_category: str, cross_sell_category: str):
        """Record cross-sell opportunity metrics"""
        b2b_product_cross_sell_opportunities.labels(primary_category=primary_category, cross_sell_category=cross_sell_category).inc()
    
    def record_upsell_opportunity(self, category: str, upsell_type: str):
        """Record upsell opportunity metrics"""
        b2b_upsell_opportunities.labels(category=category, upsell_type=upsell_type).inc()
    
    def record_customer_churn_risk(self, lead_id: str, risk_factors: str, risk_score: float):
        """Record customer churn risk metrics"""
        b2b_customer_churn_risk.labels(lead_id=lead_id, risk_factors=risk_factors).set(risk_score)

    # Organization Metrics Methods
    def update_organization_metrics(self, db: Session):
        """Update organization-related metrics from database"""
        try:
            from db.models import Organization as DBOrganization, User as DBUser, OrganizationType
            
            # Get organization counts by type and status
            org_counts = db.query(
                DBOrganization.org_type,
                DBOrganization.is_active,
                func.count(DBOrganization.id).label('count')
            ).group_by(DBOrganization.org_type, DBOrganization.is_active).all()
            
            # Reset organization total metrics
            for org_type in OrganizationType:
                for is_active in [True, False]:
                    b2b_organizations_total.labels(org_type=org_type.value, is_active=str(is_active).lower()).set(0)
            
            # Set current values
            for org_type, is_active, count in org_counts:
                b2b_organizations_total.labels(org_type=org_type.value, is_active=str(is_active).lower()).set(count)
            
            # Get detailed organization metrics
            organizations = db.query(DBOrganization).filter(DBOrganization.is_active == True).all()
            
            for org in organizations:
                # Count users per organization
                user_count = db.query(DBUser).filter(
                    DBUser.organization_id == org.id,
                    DBUser.is_active == True
                ).count()
                
                b2b_organization_users_count.labels(
                    organization_id=org.id,
                    organization_name=org.name,
                    org_type=org.org_type.value
                ).set(user_count)
                
                # Calculate quota utilization
                user_utilization = (user_count / max(org.max_users, 1)) * 100
                b2b_organization_quota_utilization.labels(
                    organization_id=org.id,
                    organization_name=org.name,
                    quota_type="users"
                ).set(user_utilization)
                
                # Count leads per organization by status
                from db.models import LeadStatus
                for status in LeadStatus:
                    lead_count = db.query(DBLead).filter(
                        DBLead.organization_id == org.id,
                        DBLead.status == status
                    ).count()
                    
                    b2b_organization_leads_count.labels(
                        organization_id=org.id,
                        organization_name=org.name,
                        org_type=org.org_type.value,
                        lead_status=status.value
                    ).set(lead_count)
                
                # Calculate leads quota utilization
                total_leads = db.query(DBLead).filter(DBLead.organization_id == org.id).count()
                leads_utilization = (total_leads / max(org.max_leads, 1)) * 100
                b2b_organization_quota_utilization.labels(
                    organization_id=org.id,
                    organization_name=org.name,
                    quota_type="leads"
                ).set(leads_utilization)
                
                # Calculate activity score (based on recent activity)
                from datetime import datetime, timedelta
                recent_cutoff = datetime.now() - timedelta(days=7)
                
                recent_activity = db.query(func.count(DBChatMessage.id)).filter(
                    DBChatMessage.created_at >= recent_cutoff,
                    DBLead.organization_id == org.id
                ).join(DBLead).scalar() or 0
                
                # Simple activity score: normalize by organization size
                activity_score = min(recent_activity / max(user_count, 1), 100)
                b2b_organization_activity_score.labels(
                    organization_id=org.id,
                    organization_name=org.name,
                    org_type=org.org_type.value
                ).set(activity_score)
                
        except Exception as e:
            print(f"Error updating organization metrics: {e}")
            self.record_error("organization_metrics_update", "metrics_service")

    def update_user_metrics(self, db: Session):
        """Update user-related metrics from database"""
        try:
            from db.models import User as DBUser, UserRole
            
            # Get user counts by role and status
            user_counts = db.query(
                DBUser.role,
                DBUser.is_active,
                DBUser.is_verified,
                func.count(DBUser.id).label('count')
            ).group_by(DBUser.role, DBUser.is_active, DBUser.is_verified).all()
            
            # Reset user total metrics
            for role in UserRole:
                for is_active in [True, False]:
                    for is_verified in [True, False]:
                        b2b_users_total.labels(
                            role=role.value,
                            is_active=str(is_active).lower(),
                            is_verified=str(is_verified).lower()
                        ).set(0)
            
            # Set current values
            for role, is_active, is_verified, count in user_counts:
                b2b_users_total.labels(
                    role=role.value,
                    is_active=str(is_active).lower(),
                    is_verified=str(is_verified).lower()
                ).set(count)
            
            # Get detailed user metrics
            users = db.query(DBUser).filter(DBUser.is_active == True).all()
            
            for user in users:
                # Update last login timestamp
                if user.last_login:
                    last_login_timestamp = user.last_login.timestamp()
                    b2b_user_last_login.labels(
                        user_id=user.id,
                        user_email=user.email,
                        user_role=user.role.value,
                        organization_id=user.organization_id
                    ).set(last_login_timestamp)
                
                # Count leads managed by user
                for status in ["NEW", "QUALIFIED", "PROPOSAL", "CLOSED_WON", "CLOSED_LOST"]:
                    lead_count = db.query(DBLead).filter(
                        DBLead.assigned_user_id == user.id,
                        DBLead.status == status
                    ).count()
                    
                    b2b_user_leads_managed.labels(
                        user_id=user.id,
                        user_email=user.email,
                        user_role=user.role.value,
                        organization_id=user.organization_id,
                        lead_status=status
                    ).set(lead_count)
                
                # Calculate user activity score
                from datetime import datetime, timedelta
                recent_cutoff = datetime.now() - timedelta(days=7)
                
                recent_messages = db.query(func.count(DBChatMessage.id)).filter(
                    DBChatMessage.user_id == user.id,
                    DBChatMessage.created_at >= recent_cutoff
                ).scalar() or 0
                
                # Simple activity score: messages per day over last 7 days
                activity_score = min(recent_messages / 7, 50)  # Max 50 points for 50+ messages/day
                b2b_user_activity_score.labels(
                    user_id=user.id,
                    user_email=user.email,
                    user_role=user.role.value,
                    organization_id=user.organization_id
                ).set(activity_score)
                
        except Exception as e:
            print(f"Error updating user metrics: {e}")
            self.record_error("user_metrics_update", "metrics_service")

    def record_user_api_usage(self, user_id: str, user_email: str, organization_id: str, endpoint: str, method: str):
        """Record API usage per user"""
        b2b_user_api_usage.labels(
            user_id=user_id,
            user_email=user_email,
            organization_id=organization_id,
            endpoint=endpoint,
            method=method
        ).inc()

    def record_user_feature_usage(self, user_id: str, organization_id: str, feature: str, action: str):
        """Record feature usage per user"""
        b2b_user_feature_usage.labels(
            user_id=user_id,
            organization_id=organization_id,
            feature=feature,
            action=action
        ).inc()

    def record_user_chat_interaction(self, user_id: str, organization_id: str, interaction_type: str):
        """Record chat interactions per user"""
        b2b_user_chat_interactions.labels(
            user_id=user_id,
            organization_id=organization_id,
            interaction_type=interaction_type
        ).inc()

    def record_user_session_duration(self, user_id: str, user_role: str, organization_id: str, duration_minutes: float):
        """Record user session duration"""
        b2b_user_session_duration.labels(
            user_id=user_id,
            user_role=user_role,
            organization_id=organization_id
        ).observe(duration_minutes)

    def record_user_quote_generation(self, user_id: str, user_email: str, organization_id: str, quote_status: str):
        """Record quote generation per user"""
        b2b_user_quotes_generated.labels(
            user_id=user_id,
            user_email=user_email,
            organization_id=organization_id,
            quote_status=quote_status
        ).inc()

    def update_organization_revenue_metrics(self, organization_id: str, organization_name: str, metric_type: str, value: float, currency: str = "USD"):
        """Update organization revenue metrics"""
        b2b_organization_revenue_metrics.labels(
            organization_id=organization_id,
            organization_name=organization_name,
            metric_type=metric_type,
            currency=currency
        ).set(value)

    def update_user_token_consumption(self, user_id: str, user_email: str, organization_id: str, provider: str, model: str, tokens: int):
        """Update user token consumption"""
        b2b_user_token_consumption.labels(
            user_id=user_id,
            user_email=user_email,
            organization_id=organization_id,
            provider=provider,
            model=model
        ).set(tokens)

    def update_user_performance_metrics(self, user_id: str, user_email: str, organization_id: str, metric_type: str, value: float):
        """Update user performance metrics"""
        b2b_user_performance_metrics.labels(
            user_id=user_id,
            user_email=user_email,
            organization_id=organization_id,
            metric_type=metric_type
        ).set(value)

    def update_tenant_isolation_health(self, organization_id: str, check_type: str, status: int):
        """Update tenant isolation health check"""
        b2b_tenant_isolation_health.labels(
            organization_id=organization_id,
            check_type=check_type
        ).set(status)

    def record_cross_tenant_activity(self, source_org_id: str, target_org_id: str, activity_type: str):
        """Record cross-tenant activity for security monitoring"""
        b2b_cross_tenant_activity.labels(
            source_org_id=source_org_id,
            target_org_id=target_org_id,
            activity_type=activity_type
        ).inc()

    def update_organization_subscription_health(self, organization_id: str, organization_name: str, limit_type: str, health_score: float):
        """Update organization subscription health metrics"""
        b2b_organization_subscription_health.labels(
            organization_id=organization_id,
            organization_name=organization_name,
            limit_type=limit_type
        ).set(health_score)

    def update_organization_feature_adoption(self, organization_id: str, organization_name: str, feature: str, adoption_rate: float):
        """Update organization feature adoption metrics"""
        b2b_organization_feature_adoption.labels(
            organization_id=organization_id,
            organization_name=organization_name,
            feature=feature,
            adoption_rate=adoption_rate
        ).set(adoption_rate)
    
    def record_recommendation_set_metrics(self, recommendation_set: Dict[str, Any], lead_id: str = None):
        """Record comprehensive recommendation set metrics"""
        try:
            recommendations = recommendation_set.get('recommendations', [])
            selected_recommendations = recommendation_set.get('selected_recommendations', [])
            
            # Record all recommendations
            for rec in recommendations:
                category = rec.get('category', 'unknown')
                product_id = rec.get('product_id', 'unknown')
                product_name = rec.get('name', 'Unknown Product')
                suitability_score = rec.get('suitability_score', 0.0)
                
                self.record_product_recommendation(
                    category=category,
                    product_id=product_id,
                    product_name=product_name,
                    status="generated"
                )
                
                # Record quality score
                recommendation_set_id = recommendation_set.get('id', 'unknown')
                self.record_recommendation_quality(
                    category=category,
                    recommendation_set_id=recommendation_set_id,
                    quality_score=suitability_score
                )
            
            # Record selections
            for selected_id in selected_recommendations:
                # Find the selected recommendation
                selected_rec = next((r for r in recommendations if r.get('product_id') == selected_id), None)
                if selected_rec:
                    category = selected_rec.get('category', 'unknown')
                    product_id = selected_rec.get('product_id', 'unknown')
                    product_name = selected_rec.get('name', 'Unknown Product')
                    
                    self.record_product_selection(
                        category=category,
                        product_id=product_id,
                        product_name=product_name
                    )
            
            print(f"📊 Recorded recommendation set metrics: {len(recommendations)} recommendations, {len(selected_recommendations)} selections")
            
        except Exception as e:
            print(f"❌ Error recording recommendation set metrics: {e}")
            self.record_error("recommendation_set_recording", "metrics_service")
    
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
            result = db.execute(text("SELECT 1"))
            result.fetchone()
            
            # If we get here, database is healthy
            b2b_db_health.set(1)
            self.update_system_health("database", 1)
            
            # Get active connections count
            try:
                result = db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"))
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
    
    # Record basic HTTP metrics
    metrics_service.record_http_request(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code,
        duration=duration
    )
    
    # Try to extract user information for API usage tracking
    try:
        # Check if there's an Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # Try to decode the token to get user info
            from jose import jwt
            from config import settings
            token = auth_header.split(" ")[1]
            
            try:
                payload = jwt.decode(token, getattr(settings, 'secret_key', 'your-secret-key-change-in-production'), algorithms=["HS256"])
                user_id = payload.get("sub")
                user_email = payload.get("email")
                organization_id = payload.get("organization_id")
                
                if user_id and user_email and organization_id:
                    # Record user API usage
                    metrics_service.record_user_api_usage(
                        user_id=user_id,
                        user_email=user_email,
                        organization_id=organization_id,
                        endpoint=endpoint,
                        method=request.method
                    )
                    
                    # Record feature usage based on endpoint
                    feature = _extract_feature_from_endpoint(endpoint)
                    if feature:
                        metrics_service.record_user_feature_usage(
                            user_id=user_id,
                            organization_id=organization_id,
                            feature=feature,
                            action=request.method.lower()
                        )
                        
            except jwt.JWTError:
                # Invalid token, skip user tracking
                pass
                
    except Exception as e:
        # Don't fail the request if user tracking fails
        pass
    
    return response

def _extract_feature_from_endpoint(endpoint: str) -> str:
    """Extract feature name from endpoint for usage tracking"""
    if "/api/chat" in endpoint:
        return "chat"
    elif "/api/leads" in endpoint:
        return "leads"
    elif "/api/quotes" in endpoint:
        return "quotes"
    elif "/api/recommendations" in endpoint:
        return "recommendations"
    elif "/api/admin" in endpoint:
        return "admin"
    elif "/api/auth" in endpoint:
        return "auth"
    else:
        return "other"

def metrics_endpoint():
    """FastAPI endpoint to expose Prometheus metrics"""
    return Response(
        content=metrics_service.get_metrics(),
        media_type=CONTENT_TYPE_LATEST
    ) 