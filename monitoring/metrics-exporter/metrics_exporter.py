#!/usr/bin/env python3
"""
Custom Metrics Exporter for B2B Sales Backend
Monitors multi-user performance, gunicorn workers, database connections, and application metrics
"""

import os
import time
import asyncio
import aiohttp
import logging
from prometheus_client import start_http_server, Gauge, Counter, Histogram, Summary
from typing import Dict, Any, Optional
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
# Application metrics
b2b_health_status = Gauge('b2b_health_status', 'Application health status (1=healthy, 0=unhealthy)')
b2b_response_time = Histogram('b2b_response_time_seconds', 'Response time in seconds', ['endpoint'])
b2b_active_requests = Gauge('b2b_active_requests', 'Number of active requests')
b2b_cache_hit_rate = Gauge('b2b_cache_hit_rate', 'Cache hit rate percentage')
b2b_total_requests = Counter('b2b_total_requests', 'Total number of requests', ['method', 'endpoint'])
b2b_error_requests = Counter('b2b_error_requests', 'Total number of error requests', ['method', 'endpoint'])

# Database metrics
b2b_db_connections_total = Gauge('b2b_db_connections_total', 'Total database connections')
b2b_db_connections_active = Gauge('b2b_db_connections_active', 'Active database connections')
b2b_db_connections_idle = Gauge('b2b_db_connections_idle', 'Idle database connections')
b2b_db_connections_overflow = Gauge('b2b_db_connections_overflow', 'Overflow database connections')

# Multi-user metrics
b2b_concurrent_users = Gauge('b2b_concurrent_users', 'Number of concurrent users')
b2b_chat_messages_total = Counter('b2b_chat_messages_total', 'Total chat messages', ['type'])
b2b_leads_total = Counter('b2b_leads_total', 'Total leads')
b2b_quotes_generated = Counter('b2b_quotes_generated', 'Total quotes generated')

# Performance metrics
b2b_avg_response_time = Gauge('b2b_avg_response_time_seconds', 'Average response time in seconds')
b2b_success_rate = Gauge('b2b_success_rate', 'Request success rate percentage')
b2b_memory_usage_mb = Gauge('b2b_memory_usage_mb', 'Memory usage in MB')
b2b_cpu_usage_percent = Gauge('b2b_cpu_usage_percent', 'CPU usage percentage')

# Worker metrics (for gunicorn)
b2b_workers_total = Gauge('b2b_workers_total', 'Total number of workers')
b2b_workers_active = Gauge('b2b_workers_active', 'Active workers')
b2b_worker_requests = Counter('b2b_worker_requests', 'Requests per worker', ['worker_id'])

class B2BMetricsExporter:
    def __init__(self, app_url: str, metrics_port: int = 9188):
        self.app_url = app_url
        self.metrics_port = metrics_port
        self.session = None
        self.last_check = 0
        self.check_interval = 30  # seconds
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_health(self) -> Dict[str, Any]:
        """Check application health"""
        try:
            start_time = time.time()
            async with self.session.get(f"{self.app_url}/health") as response:
                duration = time.time() - start_time
                return {
                    "healthy": response.status == 200,
                    "status_code": response.status,
                    "response_time": duration
                }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "status_code": 0,
                "response_time": 0
            }
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        try:
            async with self.session.get(f"{self.app_url}/api/admin/performance") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status {response.status}"}
        except Exception as e:
            logger.error(f"Performance stats failed: {e}")
            return {"error": str(e)}
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database connection statistics"""
        try:
            async with self.session.get(f"{self.app_url}/api/debug/database") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status {response.status}"}
        except Exception as e:
            logger.error(f"Database stats failed: {e}")
            return {"error": str(e)}
    
    async def get_elasticsearch_stats(self) -> Dict[str, Any]:
        """Get Elasticsearch statistics"""
        try:
            async with self.session.get(f"{self.app_url}/api/debug/elasticsearch") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status {response.status}"}
        except Exception as e:
            logger.error(f"Elasticsearch stats failed: {e}")
            return {"error": str(e)}
    
    async def simulate_load_test(self, num_users: int = 5) -> Dict[str, Any]:
        """Simulate load test to measure concurrent user performance"""
        try:
            tasks = []
            for i in range(num_users):
                task = self.simulate_user_request(i + 1)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_requests = 0
            total_duration = 0
            errors = 0
            
            for result in results:
                if isinstance(result, Exception):
                    errors += 1
                elif result.get("success"):
                    successful_requests += 1
                    total_duration += result.get("duration", 0)
                else:
                    errors += 1
            
            avg_response_time = total_duration / successful_requests if successful_requests > 0 else 0
            success_rate = (successful_requests / num_users) * 100 if num_users > 0 else 0
            
            return {
                "total_users": num_users,
                "successful_requests": successful_requests,
                "failed_requests": errors,
                "success_rate": success_rate,
                "avg_response_time": avg_response_time
            }
        except Exception as e:
            logger.error(f"Load test failed: {e}")
            return {"error": str(e)}
    
    async def simulate_user_request(self, user_id: int) -> Dict[str, Any]:
        """Simulate a user making a chat request"""
        try:
            payload = {
                "message": f"Test message from user {user_id}",
                "lead_id": f"test_lead_{user_id}",
                "conversation_stage": "discovery"
            }
            
            start_time = time.time()
            async with self.session.post(
                f"{self.app_url}/api/chat",
                json=payload
            ) as response:
                duration = time.time() - start_time
                
                return {
                    "user_id": user_id,
                    "status": response.status,
                    "duration": duration,
                    "success": response.status == 200
                }
        except Exception as e:
            return {
                "user_id": user_id,
                "status": 0,
                "duration": 0,
                "success": False,
                "error": str(e)
            }
    
    def update_metrics(self, health_data: Dict[str, Any], perf_data: Dict[str, Any], 
                      db_data: Dict[str, Any], load_data: Dict[str, Any]):
        """Update Prometheus metrics with collected data"""
        
        # Health metrics
        b2b_health_status.set(1 if health_data.get("healthy", False) else 0)
        b2b_response_time.labels(endpoint="/health").observe(health_data.get("response_time", 0))
        
        # Performance metrics
        if "error" not in perf_data:
            b2b_active_requests.set(perf_data.get("active_requests", 0))
            b2b_cache_hit_rate.set(perf_data.get("cache_hit_rate", 0))
            b2b_avg_response_time.set(perf_data.get("avg_response_time", 0))
            b2b_success_rate.set(perf_data.get("success_rate", 0))
        
        # Database metrics
        if "error" not in db_data:
            b2b_db_connections_total.set(db_data.get("pool_size", 0))
            b2b_db_connections_active.set(db_data.get("checked_out", 0))
            b2b_db_connections_idle.set(db_data.get("checked_in", 0))
            b2b_db_connections_overflow.set(db_data.get("overflow", 0))
        
        # Load test metrics
        if "error" not in load_data:
            b2b_concurrent_users.set(load_data.get("total_users", 0))
            b2b_success_rate.set(load_data.get("success_rate", 0))
            b2b_avg_response_time.set(load_data.get("avg_response_time", 0))
        
        # Increment request counters
        b2b_total_requests.labels(method="GET", endpoint="/health").inc()
        if health_data.get("status_code", 0) >= 400:
            b2b_error_requests.labels(method="GET", endpoint="/health").inc()
    
    async def collect_metrics(self):
        """Collect all metrics periodically"""
        logger.info("Starting metrics collection...")
        
        while True:
            try:
                current_time = time.time()
                
                # Collect all metrics
                health_data = await self.check_health()
                perf_data = await self.get_performance_stats()
                db_data = await self.get_database_stats()
                load_data = await self.simulate_load_test(5)  # Test with 5 users
                
                # Update Prometheus metrics
                self.update_metrics(health_data, perf_data, db_data, load_data)
                
                # Log summary
                logger.info(f"Metrics updated - Health: {health_data.get('healthy', False)}, "
                          f"Active Requests: {perf_data.get('active_requests', 0)}, "
                          f"DB Connections: {db_data.get('checked_out', 0)}/{db_data.get('pool_size', 0)}, "
                          f"Load Test Success: {load_data.get('success_rate', 0):.1f}%")
                
                # Wait for next collection
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(self.check_interval)

async def main():
    """Main function to run the metrics exporter"""
    app_url = os.getenv("B2B_APP_URL", "http://localhost:3001")
    metrics_port = int(os.getenv("METRICS_PORT", "9188"))
    
    logger.info(f"Starting B2B Metrics Exporter for {app_url} on port {metrics_port}")
    
    # Start Prometheus HTTP server
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started on port {metrics_port}")
    
    # Start metrics collection
    async with B2BMetricsExporter(app_url, metrics_port) as exporter:
        await exporter.collect_metrics()

if __name__ == "__main__":
    asyncio.run(main()) 