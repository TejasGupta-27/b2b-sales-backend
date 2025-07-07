#!/usr/bin/env python3
"""
Performance Monitoring Script for B2B Sales Backend
Monitors key metrics to ensure the application can handle multiple users
"""

import asyncio
import aiohttp
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self, base_url: str = "http://localhost:3001"):
        self.base_url = base_url
        self.session = None
        self.metrics = {
            "response_times": [],
            "concurrent_users": 0,
            "errors": [],
            "start_time": time.time()
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check application health"""
        try:
            start_time = time.time()
            async with self.session.get(f"{self.base_url}/health") as response:
                duration = time.time() - start_time
                return {
                    "status": response.status,
                    "duration": duration,
                    "healthy": response.status == 200
                }
        except Exception as e:
            return {
                "status": 0,
                "duration": 0,
                "healthy": False,
                "error": str(e)
            }
    
    async def performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        try:
            async with self.session.get(f"{self.base_url}/api/admin/performance") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def database_stats(self) -> Dict[str, Any]:
        """Get database connection statistics"""
        try:
            async with self.session.get(f"{self.base_url}/api/debug/database") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def elasticsearch_stats(self) -> Dict[str, Any]:
        """Get Elasticsearch statistics"""
        try:
            async with self.session.get(f"{self.base_url}/api/debug/elasticsearch") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def simulate_user_request(self, user_id: int) -> Dict[str, Any]:
        """Simulate a user making a chat request"""
        try:
            payload = {
                "message": f"Hello from user {user_id}",
                "lead_id": f"test_lead_{user_id}",
                "conversation_stage": "discovery"
            }
            
            start_time = time.time()
            async with self.session.post(
                f"{self.base_url}/api/chat",
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
    
    async def load_test(self, num_users: int, duration: int = 60) -> Dict[str, Any]:
        """Run a load test with multiple concurrent users"""
        logger.info(f"Starting load test with {num_users} users for {duration} seconds")
        
        start_time = time.time()
        results = []
        
        # Create tasks for concurrent users
        tasks = []
        for i in range(num_users):
            task = asyncio.create_task(self.simulate_user_request(i + 1))
            tasks.append(task)
        
        # Wait for all requests to complete
        user_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_requests = 0
        total_duration = 0
        errors = []
        
        for result in user_results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif result.get("success"):
                successful_requests += 1
                total_duration += result.get("duration", 0)
            else:
                errors.append(result.get("error", "Unknown error"))
        
        avg_response_time = total_duration / successful_requests if successful_requests > 0 else 0
        
        return {
            "total_users": num_users,
            "successful_requests": successful_requests,
            "failed_requests": len(errors),
            "success_rate": successful_requests / num_users * 100,
            "avg_response_time": avg_response_time,
            "errors": errors[:5],  # Show first 5 errors
            "test_duration": time.time() - start_time
        }
    
    def print_summary(self, stats: Dict[str, Any]):
        """Print a formatted summary of performance statistics"""
        print("\n" + "="*60)
        print("PERFORMANCE MONITORING SUMMARY")
        print("="*60)
        
        # Health Status
        health = stats.get("health", {})
        print(f"Health Status: {'✅ Healthy' if health.get('healthy') else '❌ Unhealthy'}")
        print(f"Response Time: {health.get('duration', 0):.3f}s")
        
        # Performance Stats
        perf = stats.get("performance", {})
        if "error" not in perf:
            print(f"\nPerformance Metrics:")
            print(f"  Active Requests: {perf.get('active_requests', 0)}")
            print(f"  Cache Hit Rate: {perf.get('cache_hit_rate', 0):.1f}%")
            print(f"  Avg Response Time: {perf.get('avg_response_time', 0):.3f}s")
        
        # Database Stats
        db = stats.get("database", {})
        if "error" not in db:
            print(f"\nDatabase Connection Pool:")
            print(f"  Pool Size: {db.get('pool_size', 0)}")
            print(f"  Checked Out: {db.get('checked_out', 0)}")
            print(f"  Checked In: {db.get('checked_in', 0)}")
            print(f"  Overflow: {db.get('overflow', 0)}")
        
        # Load Test Results
        load = stats.get("load_test", {})
        if load:
            print(f"\nLoad Test Results:")
            print(f"  Total Users: {load.get('total_users', 0)}")
            print(f"  Success Rate: {load.get('success_rate', 0):.1f}%")
            print(f"  Avg Response Time: {load.get('avg_response_time', 0):.3f}s")
            print(f"  Failed Requests: {load.get('failed_requests', 0)}")
        
        print("="*60)
    
    async def run_monitoring(self, interval: int = 30, load_test_users: int = 0):
        """Run continuous monitoring"""
        logger.info(f"Starting performance monitoring (interval: {interval}s)")
        
        while True:
            try:
                # Collect all metrics
                health = await self.health_check()
                performance = await self.performance_stats()
                database = await self.database_stats()
                elasticsearch = await self.elasticsearch_stats()
                
                stats = {
                    "timestamp": datetime.now().isoformat(),
                    "health": health,
                    "performance": performance,
                    "database": database,
                    "elasticsearch": elasticsearch
                }
                
                # Run load test if requested
                if load_test_users > 0:
                    load_test = await self.load_test(load_test_users)
                    stats["load_test"] = load_test
                
                # Print summary
                self.print_summary(stats)
                
                # Wait for next interval
                await asyncio.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(interval)

async def main():
    parser = argparse.ArgumentParser(description="Performance Monitor for B2B Sales Backend")
    parser.add_argument("--url", default="http://localhost:3001", help="Base URL of the application")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in seconds")
    parser.add_argument("--load-test", type=int, default=0, help="Number of users for load test")
    parser.add_argument("--single-check", action="store_true", help="Run single check instead of continuous monitoring")
    
    args = parser.parse_args()
    
    async with PerformanceMonitor(args.url) as monitor:
        if args.single_check:
            # Single check
            health = await monitor.health_check()
            performance = await monitor.performance_stats()
            database = await monitor.database_stats()
            
            stats = {
                "health": health,
                "performance": performance,
                "database": database
            }
            
            if args.load_test > 0:
                load_test = await monitor.load_test(args.load_test)
                stats["load_test"] = load_test
            
            monitor.print_summary(stats)
        else:
            # Continuous monitoring
            await monitor.run_monitoring(args.interval, args.load_test)

if __name__ == "__main__":
    asyncio.run(main()) 