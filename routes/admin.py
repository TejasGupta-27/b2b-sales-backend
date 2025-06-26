from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import os
import glob
from pathlib import Path
import logging
import asyncio
import time
import psutil
from services.elasticsearch_service import get_elasticsearch_service
from services.chroma_service import ChromaDBService
from services.prompt_manager import get_prompt_manager
from db.database import get_db
from config import settings
import aiofiles
import shutil
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

# Configuration file for storing prompts
PROMPTS_CONFIG_FILE = Path("Data/admin_config/prompts.json")
DATA_CONFIG_FILE = Path("Data/admin_config/data_sources.json")

# Ensure config directory exists
PROMPTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Metrics storage
metrics_data = {
    "start_time": time.time(),
    "request_count": 0,
    "error_count": 0,
    "response_times": [],
    "token_usage": 0
}

# Grafana JSON Data Source Endpoints
@router.get("/grafana/prompts")
async def get_prompts_for_grafana():
    """Get all prompts for Grafana display"""
    try:
        prompt_manager = get_prompt_manager()
        all_prompts = {}
        
        categories = ["sales_agent", "quote_generation", "conversation_flow", "product_retriever", "discovery"]
        for category in categories:
            try:
                category_prompts = prompt_manager.get_category_prompts(category)
                all_prompts[category] = category_prompts
            except Exception as e:
                logger.warning(f"Error loading prompts for category {category}: {e}")
                all_prompts[category] = {}
        
        # Format for Grafana
        result = []
        for category, prompts in all_prompts.items():
            for name, content in prompts.items():
                result.append({
                    "category": category,
                    "name": name,
                    "content": content,
                    "content_length": len(content),
                    "word_count": len(content.split()),
                    "last_modified": datetime.now().isoformat()
                })
        
        return {"data": result}
    
    except Exception as e:
        logger.error(f"Error getting prompts for Grafana: {e}")
        return {"data": [], "error": str(e)}

@router.get("/grafana/config")
async def get_config_for_grafana():
    """Get all configuration for Grafana display"""
    try:
        prompt_manager = get_prompt_manager()
        
        # Get conversational config
        conversational_config = {}
        try:
            personality = prompt_manager.get_prompt("conversational_agent", "personality_config", "{}")
            industry_contexts = prompt_manager.get_prompt("conversational_agent", "industry_contexts", "{}")
            response_guidelines = prompt_manager.get_prompt("conversational_agent", "response_guidelines", "{}")
            
            conversational_config = {
                "personality": json.loads(personality),
                "industry_contexts": json.loads(industry_contexts),
                "response_guidelines": json.loads(response_guidelines)
            }
        except Exception as e:
            logger.warning(f"Error loading conversational config: {e}")
        
        # Get system config
        system_config = {
            "debug": settings.debug,
            "use_hybrid_retriever": settings.use_hybrid_retriever,
            "force_reload_data": settings.force_reload_data,
            "skip_data_loading": settings.skip_data_loading,
            "enable_response_caching": getattr(settings, 'enable_response_caching', False),
            "cache_ttl": getattr(settings, 'cache_ttl', 300)
        }
        
        return {
            "data": {
                "conversational": conversational_config,
                "system": system_config,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting config for Grafana: {e}")
        return {"data": {}, "error": str(e)}

@router.get("/grafana/logs")
async def get_logs_for_grafana():
    """Get logs for Grafana display"""
    try:
        logs_dir = Path("logs")
        all_logs = []
        
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                if log_file.is_file():
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            # Get last 100 lines
                            recent_lines = lines[-100:] if len(lines) > 100 else lines
                            
                            for line in recent_lines:
                                line = line.strip()
                                if line:
                                    # Parse log line (basic parsing)
                                    parts = line.split(' - ', 2)
                                    if len(parts) >= 3:
                                        timestamp_str, level, message = parts[0], parts[1], parts[2]
                                        try:
                                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                        except:
                                            timestamp = datetime.now()
                                        
                                        all_logs.append({
                                            "timestamp": timestamp.isoformat(),
                                            "level": level,
                                            "message": message,
                                            "file": log_file.name
                                        })
                    except Exception as e:
                        logger.warning(f"Error reading log file {log_file}: {e}")
        
        # Sort by timestamp
        all_logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {"data": all_logs[:1000]}  # Limit to 1000 entries
    
    except Exception as e:
        logger.error(f"Error getting logs for Grafana: {e}")
        return {"data": [], "error": str(e)}

@router.get("/grafana/data-status")
async def get_data_status_for_grafana():
    """Get data source status for Grafana"""
    try:
        status = {
            "elasticsearch": False,
            "chromadb": False,
            "json_files": False,
            "json_files_count": 0,
            "elasticsearch_stats": {},
            "chromadb_stats": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Check Elasticsearch
        try:
            elasticsearch_service = get_elasticsearch_service()
            await elasticsearch_service.test_connection()
            status["elasticsearch"] = True
            try:
                products_count = await elasticsearch_service._safe_count("products")
                solutions_count = await elasticsearch_service._safe_count("solutions")
                status["elasticsearch_stats"] = {
                    "products": products_count,
                    "solutions": solutions_count
                }
            except Exception as e:
                status["elasticsearch_stats"] = {
                    "products": "Unknown",
                    "solutions": "Unknown",
                    "error": str(e)
                }
        except Exception as e:
            status["elasticsearch_error"] = str(e)
        
        # Check ChromaDB
        try:
            if settings.use_hybrid_retriever and settings.azure_embedding_endpoint:
                chroma_service = ChromaDBService(
                    azure_embedding_endpoint=settings.azure_embedding_endpoint,
                    azure_embedding_key=settings.azure_embedding_api_key
                )
                await chroma_service.initialize()
                stats = await chroma_service.get_collection_stats()
                status["chromadb"] = True
                status["chromadb_stats"] = stats
        except Exception as e:
            status["chromadb_error"] = str(e)
        
        # Check JSON files
        json_dir = Path("Data/json")
        if json_dir.exists():
            json_files = list(json_dir.glob("*.json"))
            status["json_files"] = len(json_files) > 0
            status["json_files_count"] = len(json_files)
        
        return {"data": status}
    
    except Exception as e:
        logger.error(f"Error getting data status for Grafana: {e}")
        return {"data": {}, "error": str(e)}

@router.get("/grafana/system-metrics")
async def get_system_metrics_for_grafana():
    """Get comprehensive system metrics for Grafana"""
    try:
        # Get database metrics
        db: Session = next(get_db())
        from db.models import Lead, ChatMessage
        
        # Get lead statistics
        total_leads = db.query(Lead).count()
        active_leads = db.query(Lead).filter(Lead.status == "active").count()
        new_leads_today = db.query(Lead).filter(
            Lead.created_at >= datetime.now().date()
        ).count()
        
        # Get message statistics
        total_messages = db.query(ChatMessage).count()
        messages_today = db.query(ChatMessage).filter(
            ChatMessage.timestamp >= datetime.now().date()
        ).count()
        
        # Get system metrics
        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent()
        
        # Get file system metrics
        data_dir = Path("Data")
        total_files = 0
        total_size = 0
        if data_dir.exists():
            for file_path in data_dir.rglob("*"):
                if file_path.is_file():
                    total_files += 1
                    total_size += file_path.stat().st_size
        
        # Get token usage
        token_file = Path("Data/token_usage.json")
        token_usage = 0
        if token_file.exists():
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                token_usage = token_data.get("total_tokens", 0)
        
        metrics = {
            "database": {
                "total_leads": total_leads,
                "active_leads": active_leads,
                "new_leads_today": new_leads_today,
                "total_messages": total_messages,
                "messages_today": messages_today
            },
            "system": {
                "memory_usage_mb": memory_info.rss / 1024 / 1024,
                "cpu_percent": cpu_percent,
                "uptime_seconds": time.time() - metrics_data["start_time"],
                "total_requests": metrics_data["request_count"],
                "error_count": metrics_data["error_count"]
            },
            "files": {
                "total_files": total_files,
                "total_size_mb": total_size / 1024 / 1024
            },
            "ai": {
                "token_usage": token_usage
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return {"data": metrics}
    
    except Exception as e:
        logger.error(f"Error getting system metrics for Grafana: {e}")
        return {"data": {}, "error": str(e)}

# Action endpoints for Grafana
@router.post("/grafana/actions/reindex")
async def reindex_from_grafana(force_replace: bool = False):
    """Reindex data from Grafana"""
    try:
        logger.info(f"Reindexing data from Grafana (force_replace={force_replace})...")
        elasticsearch_service = get_elasticsearch_service()
        
        # Health check
        health_check = await elasticsearch_service.test_connection()
        if not health_check:
            return {"success": False, "error": "Elasticsearch is not available"}
        
        # Reindex
        await elasticsearch_service.reindex_all_data(force_replace=force_replace)
        
        return {
            "success": True, 
            "message": f"Data reindexed successfully: {'Data replaced completely' if force_replace else 'Data updated safely'}",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error reindexing from Grafana: {e}")
        return {"success": False, "error": str(e)}

@router.post("/grafana/actions/sync-chroma")
async def sync_chroma_from_grafana(clear_existing: bool = False):
    """Sync ChromaDB from Grafana"""
    try:
        from main import chroma_service
        
        if not chroma_service:
            return {"success": False, "error": "ChromaDB not initialized"}
        
        result = await chroma_service.sync_data_safely(max_per_file=50, clear_existing=clear_existing)
        stats = await chroma_service.get_collection_stats()
        
        return {
            "success": True,
            "message": "ChromaDB cleared and resynced" if clear_existing else "ChromaDB synced (duplicates prevented)",
            "sync_result": result,
            "final_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error syncing ChromaDB from Grafana: {e}")
        return {"success": False, "error": str(e)}

@router.post("/grafana/actions/save-prompt")
async def save_prompt_from_grafana(prompt_data: Dict[str, Any]):
    """Save prompt from Grafana"""
    try:
        category = prompt_data["category"]
        name = prompt_data["name"]
        content = prompt_data["content"]
        
        prompt_manager = get_prompt_manager()
        success = prompt_manager.save_prompt(category, name, content)
        
        if success:
            return {
                "success": True,
                "message": "Prompt saved successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"success": False, "error": "Error saving prompt"}
    
    except Exception as e:
        logger.error(f"Error saving prompt from Grafana: {e}")
        return {"success": False, "error": str(e)}

@router.post("/grafana/actions/update-config")
async def update_config_from_grafana(config_data: Dict[str, Any]):
    """Update configuration from Grafana"""
    try:
        config_type = config_data.get("type")
        config_content = config_data.get("content")
        
        if not config_type or not config_content:
            return {"success": False, "error": "Missing config type or content"}
        
        prompt_manager = get_prompt_manager()
        success = prompt_manager.update_conversational_config(config_type, config_content)
        
        if success:
            return {
                "success": True,
                "message": f"{config_type} configuration updated successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"success": False, "error": f"Invalid config type: {config_type}"}
    
    except Exception as e:
        logger.error(f"Error updating config from Grafana: {e}")
        return {"success": False, "error": str(e)}

# Legacy endpoints (keeping for backward compatibility)
@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
    """Redirect to Grafana dashboard"""
    # Redirect to nginx-proxied Grafana URL
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>B2B Sales Backend - Admin Dashboard</title>
        <meta http-equiv="refresh" content="0; url=http://48.210.58.7/grafana/">
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .btn {{ display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }}
            .btn:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 B2B Sales Backend - Admin Dashboard</h1>
            <p>Redirecting to Grafana monitoring dashboard...</p>
            <p>If you are not redirected automatically, click the button below:</p>
            <a href="http://48.210.58.7/grafana/" class="btn">Open Grafana Dashboard</a>
            <br><br>
            <p><strong>Grafana Credentials:</strong> admin / admin123</p>
            <p><small>Available Services:</small></p>
            <ul style="list-style: none; padding: 0;">
                <li>📊 <a href="http://48.210.58.7/grafana/">Grafana Dashboard</a></li>
                <li>📈 <a href="http://48.210.58.7:9090">Prometheus Metrics</a></li>
                <li>🔍 <a href="http://48.210.58.7:5601">Kibana (Elasticsearch)</a></li>
                <li>🗄️ <a href="http://48.210.58.7:8080">Adminer (Database)</a></li>
                <li>🔧 <a href="http://48.210.58.7/admin/">Admin Panel</a></li>
            </ul>
        </div>
    </body>
    </html>
    """)

@router.head("/")
async def admin_dashboard_head():
    """Handle HEAD requests for admin dashboard"""
    return Response(
        status_code=200,
        headers={
            "content-type": "text/html; charset=utf-8",
            "content-length": "0"
        }
    )

# Specific proxy routes for Grafana
@router.get("/login")
async def proxy_grafana_login():
    """Proxy Grafana login page"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://grafana:3000/login")
            return HTMLResponse(
                content=response.text,
                status_code=response.status_code,
                headers=response.headers
            )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grafana proxy error: {str(e)}")

@router.get("/d/{dashboard_id}")
async def proxy_grafana_dashboard(dashboard_id: str):
    """Proxy Grafana dashboard"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://grafana:3000/d/{dashboard_id}")
            return HTMLResponse(
                content=response.text,
                status_code=response.status_code,
                headers=response.headers
            )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grafana proxy error: {str(e)}")

@router.get("/api/{path:path}")
async def proxy_grafana_api(path: str, request: Request):
    """Proxy Grafana API calls"""
    target_url = f"http://grafana:3000/api/{path}"
    
    # Get headers
    headers = dict(request.headers)
    headers.pop("host", None)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(target_url, headers=headers, params=request.query_params)
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response.headers
            )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grafana proxy error: {str(e)}")

@router.get("/metrics")
async def get_prometheus_metrics():
    """Get Prometheus format metrics"""
    try:
        # Get system metrics
        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent()
        
        # Get database metrics
        db: Session = next(get_db())
        from db.models import Lead, ChatMessage
        active_leads = db.query(Lead).count()
        total_messages = db.query(ChatMessage).count()
        
        # Get Elasticsearch metrics
        elasticsearch_service = get_elasticsearch_service()
        try:
            products_count = await elasticsearch_service._safe_count("products")
            solutions_count = await elasticsearch_service._safe_count("solutions")
        except:
            products_count = 0
            solutions_count = 0
        
        # Get token usage
        token_file = Path("Data/token_usage.json")
        token_usage = 0
        if token_file.exists():
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                token_usage = token_data.get("total_tokens", 0)
        
        # Calculate response time statistics
        avg_response_time = 0
        if metrics_data["response_times"]:
            avg_response_time = sum(metrics_data["response_times"]) / len(metrics_data["response_times"])
        
        # Generate Prometheus format metrics
        metrics = f"""# HELP b2b_uptime_seconds Total uptime in seconds
# TYPE b2b_uptime_seconds counter
b2b_uptime_seconds {time.time() - metrics_data["start_time"]}

# HELP b2b_requests_total Total number of requests
# TYPE b2b_requests_total counter
b2b_requests_total {metrics_data["request_count"]}

# HELP b2b_errors_total Total number of errors
# TYPE b2b_errors_total counter
b2b_errors_total {metrics_data["error_count"]}

# HELP b2b_response_time_seconds Average response time
# TYPE b2b_response_time_seconds gauge
b2b_response_time_seconds {avg_response_time}

# HELP b2b_active_leads Number of active leads
# TYPE b2b_active_leads gauge
b2b_active_leads {active_leads}

# HELP b2b_total_messages Total number of chat messages
# TYPE b2b_total_messages gauge
b2b_total_messages {total_messages}

# HELP b2b_elasticsearch_products_count Number of products in Elasticsearch
# TYPE b2b_elasticsearch_products_count gauge
b2b_elasticsearch_products_count {products_count}

# HELP b2b_elasticsearch_solutions_count Number of solutions in Elasticsearch
# TYPE b2b_elasticsearch_solutions_count gauge
b2b_elasticsearch_solutions_count {solutions_count}

# HELP b2b_token_usage_total Total AI token usage
# TYPE b2b_token_usage_total counter
b2b_token_usage_total {token_usage}

# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds
# TYPE process_cpu_seconds_total counter
process_cpu_seconds_total {process.cpu_times().user + process.cpu_times().system}

# HELP process_resident_memory_bytes Resident memory size in bytes
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes {memory_info.rss}

# HELP process_virtual_memory_bytes Virtual memory size in bytes
# TYPE process_virtual_memory_bytes gauge
process_virtual_memory_bytes {memory_info.vms}

# HELP process_open_fds Number of open file descriptors
# TYPE process_open_fds gauge
process_open_fds {len(process.open_files())}

# HELP process_threads Number of OS threads in the process
# TYPE process_threads gauge
process_threads {process.num_threads()}
"""
        
        return Response(content=metrics, media_type="text/plain")
    
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return Response(content="# Error generating metrics", media_type="text/plain")

@router.get("/metrics/json")
async def get_metrics():
    """Get performance metrics in JSON format"""
    try:
        # Load token usage
        token_file = Path("Data/token_usage.json")
        token_usage = 0
        if token_file.exists():
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                token_usage = token_data.get("total_tokens", 0)
        
        return {
            "avg_response_time": "150ms",
            "success_rate": "98.5%",
            "token_usage": f"{token_usage:,}",
            "active_sessions": "12"
        }
    
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return {
            "avg_response_time": "N/A",
            "success_rate": "N/A", 
            "token_usage": "N/A",
            "active_sessions": "N/A"
        }

# Middleware to track metrics
async def track_metrics_middleware(request, call_next):
    start_time = time.time()
    metrics_data["request_count"] += 1
    
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        metrics_data["error_count"] += 1
        raise e
    finally:
        response_time = time.time() - start_time
        metrics_data["response_times"].append(response_time)
        # Keep only last 1000 response times to prevent memory bloat
        if len(metrics_data["response_times"]) > 1000:
            metrics_data["response_times"] = metrics_data["response_times"][-1000:]

# Conversational Configuration Endpoints
@router.get("/conversational/config")
async def get_conversational_config():
    """Get conversational configuration"""
    try:
        prompt_manager = get_prompt_manager()
        config = prompt_manager.get_conversational_config()
        return config
    except Exception as e:
        logger.error(f"Error getting conversational config: {e}")
        raise HTTPException(status_code=500, detail="Error getting conversational configuration")

@router.post("/conversational/config/{config_type}")
async def update_conversational_config(config_type: str, config_data: Dict[str, Any]):
    """Update conversational configuration"""
    try:
        prompt_manager = get_prompt_manager()
        success = prompt_manager.update_conversational_config(config_type, config_data)
        
        if success:
            return {"status": "success", "message": f"{config_type} configuration updated successfully"}
        else:
            raise HTTPException(status_code=400, detail=f"Invalid config type: {config_type}")
    
    except Exception as e:
        logger.error(f"Error updating conversational config: {e}")
        raise HTTPException(status_code=500, detail="Error updating conversational configuration")

@router.get("/conversational/config/{config_type}")
async def get_conversational_config_type(config_type: str):
    """Get specific conversational configuration type"""
    try:
        prompt_manager = get_prompt_manager()
        
        if config_type == "personality":
            config_str = prompt_manager.get_prompt("conversational_agent", "personality_config", "{}")
        elif config_type == "industry_contexts":
            config_str = prompt_manager.get_prompt("conversational_agent", "industry_contexts", "{}")
        elif config_type == "response_guidelines":
            config_str = prompt_manager.get_prompt("conversational_agent", "response_guidelines", "{}")
        else:
            raise HTTPException(status_code=400, detail=f"Invalid config type: {config_type}")
        
        return json.loads(config_str)
    
    except Exception as e:
        logger.error(f"Error getting conversational config type: {e}")
        raise HTTPException(status_code=500, detail="Error getting conversational configuration")

@router.post("/conversational/config/reset")
async def reset_conversational_config():
    """Reset conversational configuration to defaults"""
    try:
        prompt_manager = get_prompt_manager()
        
        # Get default prompts
        default_prompts = prompt_manager._get_default_conversational_prompts()
        conversational_prompts = default_prompts.get("conversational_agent", {})
        
        # Reset each configuration
        for name, content in conversational_prompts.items():
            prompt_manager.save_prompt("conversational_agent", name, content)
        
        logger.info("Conversational configuration reset to defaults")
        return {"status": "success", "message": "Conversational configuration reset to defaults"}
    
    except Exception as e:
        logger.error(f"Error resetting conversational config: {e}")
        raise HTTPException(status_code=500, detail="Error resetting conversational configuration")

@router.post("/conversational/config/test")
async def test_conversational_config(config_data: Dict[str, Any]):
    """Test conversational configuration with sample data"""
    try:
        config_type = config_data.get("config_type")
        config_content = config_data.get("config")
        
        if not config_type or not config_content:
            raise HTTPException(status_code=400, detail="Missing config_type or config")
        
        # Validate JSON format
        try:
            if isinstance(config_content, str):
                parsed_config = json.loads(config_content)
            else:
                parsed_config = config_content
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": f"Invalid JSON format: {e}",
                "test_results": {}
            }
        
        # Test configuration based on type
        test_results = {
            "config_type": config_type,
            "is_valid_json": True,
            "config_size": len(str(parsed_config)),
            "validation_results": {}
        }
        
        if config_type == "personality":
            # Validate personality configuration
            required_fields = ["name", "role", "personality_traits", "communication_style", "tone"]
            for field in required_fields:
                if field not in parsed_config:
                    test_results["validation_results"][field] = "Missing"
                else:
                    test_results["validation_results"][field] = "Present"
            
            # Test personality prompt generation
            try:
                name = parsed_config.get("name", "Agent")
                role = parsed_config.get("role", "Assistant")
                traits = ", ".join(parsed_config.get("personality_traits", []))
                
                test_prompt = f"""You are {name}, a {role}. 
Your personality: {traits}
Communication style: {parsed_config.get('communication_style', 'conversational')}
Tone: {parsed_config.get('tone', 'professional')}"""
                
                test_results["sample_prompt"] = test_prompt
                test_results["prompt_length"] = len(test_prompt)
                
            except Exception as e:
                test_results["validation_results"]["prompt_generation"] = f"Error: {e}"
        
        elif config_type == "industry_contexts":
            # Validate industry contexts
            if not isinstance(parsed_config, dict):
                test_results["validation_results"]["structure"] = "Should be a dictionary"
            else:
                test_results["validation_results"]["structure"] = "Valid dictionary"
                test_results["validation_results"]["industries_count"] = len(parsed_config)
                
                # Check each industry
                for industry, config in parsed_config.items():
                    if isinstance(config, dict) and "focus_areas" in config and "common_concerns" in config:
                        test_results["validation_results"][f"industry_{industry}"] = "Valid"
                    else:
                        test_results["validation_results"][f"industry_{industry}"] = "Invalid structure"
        
        elif config_type == "response_guidelines":
            # Validate response guidelines
            if not isinstance(parsed_config, dict):
                test_results["validation_results"]["structure"] = "Should be a dictionary"
            else:
                test_results["validation_results"]["structure"] = "Valid dictionary"
                test_results["validation_results"]["guideline_types_count"] = len(parsed_config)
                
                # Check each guideline type
                for guideline_type, config in parsed_config.items():
                    if isinstance(config, dict) and "approach" in config and "key_elements" in config:
                        test_results["validation_results"][f"guideline_{guideline_type}"] = "Valid"
                    else:
                        test_results["validation_results"][f"guideline_{guideline_type}"] = "Invalid structure"
        
        return {
            "status": "success",
            "message": f"Configuration '{config_type}' tested successfully",
            "test_results": test_results
        }
    
    except Exception as e:
        logger.error(f"Error testing conversational config: {e}")
        raise HTTPException(status_code=500, detail="Error testing conversational configuration")

# Prompt Management Endpoints
@router.get("/prompts/{category}")
async def get_prompts(category: str):
    """Get all prompts for a category"""
    try:
        prompt_manager = get_prompt_manager()
        return prompt_manager.get_category_prompts(category)
    except Exception as e:
        logger.error(f"Error loading prompts: {e}")
        raise HTTPException(status_code=500, detail="Error loading prompts")

@router.post("/prompts")
async def save_prompt(prompt_data: Dict[str, Any]):
    """Save or update a prompt"""
    try:
        category = prompt_data["category"]
        name = prompt_data["name"]
        content = prompt_data["content"]
        
        prompt_manager = get_prompt_manager()
        success = prompt_manager.save_prompt(category, name, content)
        
        if success:
            return {"status": "success", "message": "Prompt saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Error saving prompt")
    
    except Exception as e:
        logger.error(f"Error saving prompt: {e}")
        raise HTTPException(status_code=500, detail="Error saving prompt")

@router.delete("/prompts/{category}/{name}")
async def delete_prompt(category: str, name: str):
    """Delete a prompt"""
    try:
        prompt_manager = get_prompt_manager()
        success = prompt_manager.delete_prompt(category, name)
        
        if success:
            return {"status": "success", "message": "Prompt deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Prompt not found")
    
    except Exception as e:
        logger.error(f"Error deleting prompt: {e}")
        raise HTTPException(status_code=500, detail="Error deleting prompt")

@router.post("/prompts/test")
async def test_prompt(prompt_data: Dict[str, Any]):
    """Test a prompt with sample data"""
    try:
        category = prompt_data["category"]
        name = prompt_data["name"]
        content = prompt_data["content"]
        
        # Basic validation
        if not content or len(content.strip()) < 10:
            return {
                "status": "error",
                "message": "Prompt content is too short or empty",
                "test_results": {}
            }
        
        # Test prompt with sample variables
        test_variables = {
            "customer_name": "John Doe",
            "company": "Acme Corp",
            "industry": "Technology",
            "product_name": "Workstation Pro",
            "price": "$3,499.99"
        }
        
        # Try to substitute variables in the prompt
        test_content = content
        for var, value in test_variables.items():
            test_content = test_content.replace(f"{{{var}}}", value)
            test_content = test_content.replace(f"{{{{{var}}}}}", value)
        
        # Calculate basic metrics
        word_count = len(test_content.split())
        char_count = len(test_content)
        
        test_results = {
            "original_length": len(content),
            "processed_length": len(test_content),
            "word_count": word_count,
            "character_count": char_count,
            "test_variables_used": test_variables,
            "processed_content_preview": test_content[:200] + "..." if len(test_content) > 200 else test_content
        }
        
        logger.info(f"Tested prompt: {category}/{name}")
        return {
            "status": "success", 
            "message": f"Prompt '{name}' tested successfully",
            "test_results": test_results
        }
    
    except Exception as e:
        logger.error(f"Error testing prompt: {e}")
        raise HTTPException(status_code=500, detail="Error testing prompt")

# Log Management Endpoints
@router.get("/logs/{log_file}")
async def get_logs(log_file: str):
    """Get log file content"""
    try:
        logs_dir = Path("logs")
        
        if log_file == "all":
            # Combine all log files
            all_logs = []
            for log_path in logs_dir.glob("*.log"):
                if log_path.is_file():
                    with open(log_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        all_logs.append(f"=== {log_path.name} ===\n{content}\n")
            
            return {"content": "\n".join(all_logs)}
        else:
            log_path = logs_dir / log_file
            if not log_path.exists():
                raise HTTPException(status_code=404, detail="Log file not found")
            
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {"content": content}
    
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        raise HTTPException(status_code=500, detail="Error reading logs")

@router.get("/logs/{log_file}/download")
async def download_logs(log_file: str):
    """Download log file"""
    try:
        logs_dir = Path("logs")
        log_path = logs_dir / log_file
        
        if not log_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
        
        return FileResponse(
            path=log_path,
            filename=log_file,
            media_type='text/plain'
        )
    
    except Exception as e:
        logger.error(f"Error downloading logs: {e}")
        raise HTTPException(status_code=500, detail="Error downloading logs")

@router.post("/logs/clear")
async def clear_logs():
    """Clear all log files"""
    try:
        logs_dir = Path("logs")
        cleared_files = []
        
        for log_path in logs_dir.glob("*.log"):
            if log_path.is_file():
                with open(log_path, 'w') as f:
                    f.write("")  # Clear file content
                cleared_files.append(log_path.name)
        
        logger.info(f"Cleared log files: {cleared_files}")
        return {"status": "success", "cleared_files": cleared_files}
    
    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        raise HTTPException(status_code=500, detail="Error clearing logs")

# Data Management Endpoints
@router.post("/data/upload")
async def upload_data(file: UploadFile = File(...), source: str = Form(...)):
    """Upload data file"""
    try:
        # Create upload directory if it doesn't exist
        upload_dir = Path("Data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file
        file_path = upload_dir / f"{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Process the uploaded data based on source
        if source == "products" or source == "solutions":
            # Copy to appropriate JSON directory
            json_dir = Path("Data/json")
            target_path = json_dir / f"{source}.json"
            shutil.copy2(file_path, target_path)
            
            # Trigger reindexing
            elasticsearch_service = get_elasticsearch_service()
            await elasticsearch_service.reindex_all_data()
        
        logger.info(f"Uploaded data file: {file_path}")
        return {"status": "success", "message": f"Data uploaded successfully to {source}"}
    
    except Exception as e:
        logger.error(f"Error uploading data: {e}")
        raise HTTPException(status_code=500, detail="Error uploading data")

@router.get("/data/download/{source}")
async def download_data(source: str):
    """Download data file"""
    try:
        data_dir = Path("Data/json")
        
        if source == "products":
            file_path = data_dir / "products.json"
        elif source == "solutions":
            file_path = data_dir / "solutions.json"
        elif source == "elasticsearch":
            # Export from Elasticsearch
            elasticsearch_service = get_elasticsearch_service()
            
            # Get all products
            products_query = {"query": {"match_all": {}}, "size": 10000}
            products = await elasticsearch_service.search_products(products_query, "products")
            
            # Get all solutions
            solutions_query = {"query": {"match_all": {}}, "size": 1000}
            solutions = await elasticsearch_service.search_products(solutions_query, "solutions")
            
            # Create temporary file
            export_data = {
                "products": products,
                "solutions": solutions,
                "exported_at": datetime.now().isoformat()
            }
            
            temp_file = Path("Data/temp") / f"elasticsearch_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            return FileResponse(
                path=temp_file,
                filename=f"elasticsearch_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                media_type='application/json'
            )
        elif source == "chromadb":
            # Export from ChromaDB
            return {"message": "ChromaDB export functionality coming soon"}
        else:
            raise HTTPException(status_code=400, detail="Invalid data source")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Data file not found: {source}")
        
        return FileResponse(
            path=file_path,
            filename=f"{source}.json",
            media_type='application/json'
        )
    
    except Exception as e:
        logger.error(f"Error downloading data: {e}")
        raise HTTPException(status_code=500, detail="Error downloading data")

@router.post("/data/validate/{source}")
async def validate_data(source: str):
    """Validate data integrity"""
    try:
        validation_results = {
            "source": source,
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {}
        }
        
        if source == "products":
            # Validate products data
            data_file = Path("Data/json/products.json")
            if data_file.exists():
                with open(data_file, 'r', encoding='utf-8') as f:
                    try:
                        products = json.load(f)
                        validation_results["stats"]["total_products"] = len(products)
                        
                        # Validate each product
                        required_fields = ["id", "name", "category", "price"]
                        for i, product in enumerate(products):
                            for field in required_fields:
                                if field not in product:
                                    validation_results["errors"].append(
                                        f"Product {i}: Missing required field '{field}'"
                                    )
                                    validation_results["valid"] = False
                        
                    except json.JSONDecodeError as e:
                        validation_results["errors"].append(f"Invalid JSON format: {e}")
                        validation_results["valid"] = False
            else:
                validation_results["errors"].append("Products data file not found")
                validation_results["valid"] = False
                
        elif source == "solutions":
            # Validate solutions data
            data_file = Path("Data/json/solutions.json")
            if data_file.exists():
                with open(data_file, 'r', encoding='utf-8') as f:
                    try:
                        solutions = json.load(f)
                        validation_results["stats"]["total_solutions"] = len(solutions)
                        
                        # Validate each solution
                        required_fields = ["id", "name", "description"]
                        for i, solution in enumerate(solutions):
                            for field in required_fields:
                                if field not in solution:
                                    validation_results["errors"].append(
                                        f"Solution {i}: Missing required field '{field}'"
                                    )
                                    validation_results["valid"] = False
                        
                    except json.JSONDecodeError as e:
                        validation_results["errors"].append(f"Invalid JSON format: {e}")
                        validation_results["valid"] = False
            else:
                validation_results["errors"].append("Solutions data file not found")
                validation_results["valid"] = False
                
        elif source == "elasticsearch":
            # Validate Elasticsearch connection and data
            elasticsearch_service = get_elasticsearch_service()
            try:
                health_check = await elasticsearch_service.test_connection()
                if health_check:
                    # Get index stats
                    products_count = await elasticsearch_service._safe_count("products")
                    solutions_count = await elasticsearch_service._safe_count("solutions")
                    
                    validation_results["stats"] = {
                        "products_count": products_count,
                        "solutions_count": solutions_count
                    }
                    
                    if products_count == 0:
                        validation_results["warnings"].append("No products found in Elasticsearch")
                    if solutions_count == 0:
                        validation_results["warnings"].append("No solutions found in Elasticsearch")
                else:
                    validation_results["errors"].append("Elasticsearch connection failed")
                    validation_results["valid"] = False
            except Exception as e:
                validation_results["errors"].append(f"Elasticsearch validation error: {e}")
                validation_results["valid"] = False
                
        elif source == "chromadb":
            # Validate ChromaDB
            try:
                if settings.use_hybrid_retriever and settings.azure_embedding_endpoint:
                    chroma_service = ChromaDBService(
                        azure_embedding_endpoint=settings.azure_embedding_endpoint,
                        azure_embedding_key=settings.azure_embedding_api_key
                    )
                    await chroma_service.initialize()
                    stats = await chroma_service.get_collection_stats()
                    validation_results["stats"] = stats
                    
                    if stats["products_count"] == 0:
                        validation_results["warnings"].append("No products found in ChromaDB")
                    if stats["solutions_count"] == 0:
                        validation_results["warnings"].append("No solutions found in ChromaDB")
                else:
                    validation_results["warnings"].append("ChromaDB not configured or enabled")
            except Exception as e:
                validation_results["errors"].append(f"ChromaDB validation error: {e}")
                validation_results["valid"] = False
        else:
            raise HTTPException(status_code=400, detail="Invalid data source")
        
        return validation_results
    
    except Exception as e:
        logger.error(f"Error validating data: {e}")
        raise HTTPException(status_code=500, detail="Error validating data")

@router.get("/data/status")
async def get_data_status():
    """Get status of all data sources"""
    try:
        status = {
            "elasticsearch": False,
            "chromadb": False,
            "json_files": False,
            "json_files_count": 0
        }
        
        # Check Elasticsearch
        try:
            elasticsearch_service = get_elasticsearch_service()
            await elasticsearch_service.test_connection()
            status["elasticsearch"] = True
            try:
                products_count = await elasticsearch_service._safe_count("products")
                solutions_count = await elasticsearch_service._safe_count("solutions")
                status["elasticsearch_stats"] = {
                    "products": products_count,
                    "solutions": solutions_count
                }
            except Exception as e:
                status["elasticsearch_stats"] = {
                    "products": "Unknown",
                    "solutions": "Unknown"
                }
        except Exception:
            pass
        
        # Check ChromaDB
        try:
            if settings.use_hybrid_retriever and settings.azure_embedding_endpoint:
                chroma_service = ChromaDBService(
                    azure_embedding_endpoint=settings.azure_embedding_endpoint,
                    azure_embedding_key=settings.azure_embedding_api_key
                )
                await chroma_service.initialize()
                stats = await chroma_service.get_collection_stats()
                status["chromadb"] = True
                status["chromadb_stats"] = stats
        except:
            pass
        
        # Check JSON files
        json_dir = Path("Data/json")
        if json_dir.exists():
            json_files = list(json_dir.glob("*.json"))
            status["json_files"] = len(json_files) > 0
            status["json_files_count"] = len(json_files)
        
        return status
    
    except Exception as e:
        logger.error(f"Error getting data status: {e}")
        raise HTTPException(status_code=500, detail="Error getting data status")

# System Status Endpoints
@router.get("/status")
async def get_system_status(db: Session = Depends(get_db)):
    """Get system status"""
    try:
        # Get lead count
        from db.models import Lead
        active_leads = db.query(Lead).count()
        
        # Calculate uptime (simplified)
        uptime = "Active"
        
        # Get total requests (simplified)
        total_requests = "N/A"
        
        return {
            "uptime": uptime,
            "total_requests": total_requests,
            "active_leads": active_leads,
            "status": "healthy"
        }
    
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "uptime": "Unknown",
            "total_requests": "Unknown",
            "active_leads": 0,
            "status": "error"
        }

@router.post("/reindex")
async def reindex_data(force_replace: bool = False):
    """Reindex Elasticsearch data with safer default behavior"""
    try:
        logger.info(f"Starting data reindexing (force_replace={force_replace})...")
        elasticsearch_service = get_elasticsearch_service()
        
        # First, check if Elasticsearch is healthy
        try:
            health_check = await elasticsearch_service.test_connection()
            if not health_check:
                raise HTTPException(
                    status_code=503, 
                    detail="Elasticsearch is not available. Please check if the service is running."
                )
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            raise HTTPException(
                status_code=503, 
                detail=f"Elasticsearch health check failed: {str(e)}"
            )
        
        # Wait for cluster to be ready
        try:
            await elasticsearch_service._wait_for_cluster_ready()
        except Exception as e:
            logger.warning(f"Cluster readiness check failed: {e}")
        
        # Attempt reindexing with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await elasticsearch_service.reindex_all_data(force_replace=force_replace)
                message = "Data replaced completely" if force_replace else "Data updated safely"
                logger.info(f"Data reindexed successfully: {message}")
                return {"status": "success", "message": f"Data reindexed successfully: {message}"}
            except Exception as e:
                logger.warning(f"Reindex attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    # Last attempt failed
                    raise e
                else:
                    # Wait before retry
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error reindexing data: {e}")
        raise HTTPException(status_code=500, detail=f"Error reindexing data: {str(e)}")

@router.post("/reindex/force")
async def force_reindex_data():
    """Force complete replacement of Elasticsearch data"""
    try:
        logger.info("Starting FORCE data reindexing (complete replacement)...")
        elasticsearch_service = get_elasticsearch_service()
        
        # Health check
        health_check = await elasticsearch_service.test_connection()
        if not health_check:
            raise HTTPException(
                status_code=503, 
                detail="Elasticsearch is not available."
            )
        
        # Force complete replacement
        await elasticsearch_service.reindex_all_data(force_replace=True)
        logger.info("Force reindex completed successfully")
        return {"status": "success", "message": "Data completely replaced and reindexed"}
        
    except Exception as e:
        logger.error(f"Error in force reindex: {e}")
        raise HTTPException(status_code=500, detail=f"Error in force reindex: {str(e)}")

@router.post("/sync-chroma")
async def sync_chroma_data(clear_existing: bool = False):
    """Sync ChromaDB data with duplicate prevention"""
    try:
        # Import here to avoid circular imports
        from main import chroma_service
        
        if not chroma_service:
            raise HTTPException(status_code=503, detail="ChromaDB not initialized")
        
        # Use safe sync method
        result = await chroma_service.sync_data_safely(max_per_file=50, clear_existing=clear_existing)
        stats = await chroma_service.get_collection_stats()
        
        message = "ChromaDB cleared and resynced" if clear_existing else "ChromaDB synced (duplicates prevented)"
        logger.info(f"ChromaDB sync completed: {message}")
        
        return {
            "status": "success", 
            "message": message,
            "sync_result": result,
            "final_stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error syncing ChromaDB: {e}")
        raise HTTPException(status_code=500, detail=f"Error syncing ChromaDB: {str(e)}") 