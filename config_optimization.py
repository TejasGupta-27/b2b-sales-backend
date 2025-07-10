"""
Performance Optimization Configuration
This file contains optimized settings for better performance and conversational experience
"""

import os
from typing import Dict, Any

# Performance Optimization Settings
PERFORMANCE_CONFIG = {
    # Response Time Optimization
    "response_time_target_ms": 500,  # Target response time
    "max_response_time_ms": 2000,    # Maximum acceptable response time
    
    # Caching Configuration
    "cache_enabled": True,
    "cache_ttl_seconds": 120,        # 2 minutes for chat responses
    "cache_max_entries": 1000,       # Maximum cache entries
    "cache_cleanup_interval": 60,    # Cleanup every minute
    
    # Database Optimization
    "db_pool_size": 20,
    "db_max_overflow": 30,
    "db_pool_timeout": 30,
    "db_connect_timeout": 10,
    "db_pool_recycle": 300,
    
    # Conversation Optimization
    "max_conversation_history": 10,  # Reduced from 20
    "enable_conversational_agent": True,
    "disable_complex_flow_analysis": True,
    "parallel_speech_generation": True,
    
    # Elasticsearch Optimization
    "es_search_timeout": 5000,       # 5 seconds timeout
    "es_max_results": 20,            # Limit search results
    "es_enable_caching": True,
    "es_cache_ttl": 300,             # 5 minutes
    
    # AI Service Optimization
    "ai_request_timeout": 10000,     # 10 seconds timeout
    "ai_max_tokens": 500,            # Limit response length
    "ai_temperature": 0.7,           # Balanced creativity
    "ai_enable_streaming": False,    # Disable for faster responses
    
    # Speech Service Optimization
    "speech_timeout": 5000,          # 5 seconds timeout
    "speech_quality": "medium",      # Balance quality vs speed
    "speech_parallel_processing": True,
    "disable_speech_on_high_cpu": True,  # Disable speech when CPU > 80%
    "cpu_threshold_for_speech_disable": 80.0,  # CPU threshold percentage
    
    # Service Caching
    "enable_service_caching": True,  # Cache AI providers and agents
    "pre_initialize_agents": True,   # Pre-initialize agents on startup
    
    # Monitoring Configuration
    "enable_performance_monitoring": True,
    "performance_logging": True,
    "response_time_tracking": True,
    "cache_hit_rate_tracking": True,
    "cpu_monitoring": True,
}

# Conversational Agent Settings
CONVERSATIONAL_CONFIG = {
    "agent_personality": "friendly_expert",
    "conversation_style": "natural",
    "response_tone": "casual_professional",
    "enable_empathy": True,
    "enable_follow_up_questions": True,
    "max_response_length": 200,      # Keep responses concise
    "enable_context_awareness": True,
    "disable_rigid_stages": True,
    "enable_natural_flow": True,
}

# Environment Variables for Performance
PERFORMANCE_ENV_VARS = {
    "ENABLE_RESPONSE_CACHING": "True",
    "CACHE_TTL": "120",
    "MAX_CONCURRENT_REQUESTS": "100",
    "REQUEST_TIMEOUT": "10",
    "DATABASE_POOL_SIZE": "20",
    "DATABASE_MAX_OVERFLOW": "30",
    "DATABASE_POOL_TIMEOUT": "30",
    "ELASTICSEARCH_TIMEOUT": "5000",
    "AI_REQUEST_TIMEOUT": "10000",
    "SPEECH_TIMEOUT": "5000",
    "USE_HYBRID_RETRIEVER": "False",  # Disable for better performance
    "CONVERSATION_HISTORY_LIMIT": "10",
    "ENABLE_COMPLEX_FLOW_ANALYSIS": "False",
    "ENABLE_PARALLEL_PROCESSING": "True",
}

def get_optimized_settings() -> Dict[str, Any]:
    """Get optimized settings for performance"""
    return {
        "performance": PERFORMANCE_CONFIG,
        "conversational": CONVERSATIONAL_CONFIG,
        "env_vars": PERFORMANCE_ENV_VARS
    }

def apply_performance_optimizations():
    """Apply performance optimizations to environment"""
    for key, value in PERFORMANCE_ENV_VARS.items():
        if key not in os.environ:
            os.environ[key] = value

def get_performance_recommendations() -> list:
    """Get performance optimization recommendations"""
    return [
        "✅ Use SimpleConversationalAgent instead of EnhancedB2BSalesAgent",
        "✅ Enable response caching with 2-minute TTL",
        "✅ Reduce conversation history to last 10 messages",
        "✅ Use parallel speech generation",
        "✅ Optimize database connection pool (20 connections)",
        "✅ Disable hybrid retriever for faster responses",
        "✅ Set reasonable timeouts for all services",
        "✅ Monitor performance with /api/admin/performance endpoint",
        "✅ Use natural conversation flow instead of rigid stages",
        "✅ Implement proper error handling and fallbacks"
    ]

def get_latency_optimizations() -> list:
    """Get specific latency optimization strategies"""
    return [
        "Cache similar chat responses for 2 minutes",
        "Use parallel processing for speech generation",
        "Reduce AI service calls from 4-6 to 1-2 per request",
        "Limit conversation history to essential messages",
        "Use connection pooling for database and external services",
        "Implement request deduplication",
        "Use lightweight conversational agent",
        "Disable complex flow analysis",
        "Optimize Elasticsearch queries",
        "Use async/await properly throughout the stack"
    ] 