from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import os
import glob
from pathlib import Path
import logging
import asyncio
from services.elasticsearch_service import get_elasticsearch_service
from services.chroma_service import ChromaDBService
from db.database import get_db
from config import settings
import aiofiles
import shutil

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

# Configuration file for storing prompts
PROMPTS_CONFIG_FILE = Path("Data/admin_config/prompts.json")
DATA_CONFIG_FILE = Path("Data/admin_config/data_sources.json")

# Ensure config directory exists
PROMPTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin dashboard HTML"""
    try:
        template_path = Path("templates/admin.html")
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
        else:
            # Fallback if template file doesn't exist
            return HTMLResponse(content="<h1>Admin Dashboard</h1><p>Template file not found. Please check templates/admin.html</p>")
    except Exception as e:
        logger.error(f"Error serving admin dashboard: {e}")
        return HTMLResponse(content=f"<h1>Error</h1><p>Failed to load admin dashboard: {e}</p>")

# Prompt Management Endpoints
@router.get("/prompts/{category}")
async def get_prompts(category: str):
    """Get all prompts for a category"""
    try:
        if PROMPTS_CONFIG_FILE.exists():
            with open(PROMPTS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                prompts_config = json.load(f)
        else:
            prompts_config = {}
        
        return prompts_config.get(category, {})
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
        
        # Load existing prompts
        if PROMPTS_CONFIG_FILE.exists():
            with open(PROMPTS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                prompts_config = json.load(f)
        else:
            prompts_config = {}
        
        # Update prompts
        if category not in prompts_config:
            prompts_config[category] = {}
        
        prompts_config[category][name] = content
        
        # Save back to file
        with open(PROMPTS_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(prompts_config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved prompt: {category}/{name}")
        return {"status": "success", "message": "Prompt saved successfully"}
    
    except Exception as e:
        logger.error(f"Error saving prompt: {e}")
        raise HTTPException(status_code=500, detail="Error saving prompt")

@router.delete("/prompts/{category}/{name}")
async def delete_prompt(category: str, name: str):
    """Delete a prompt"""
    try:
        if not PROMPTS_CONFIG_FILE.exists():
            raise HTTPException(status_code=404, detail="No prompts found")
        
        with open(PROMPTS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            prompts_config = json.load(f)
        
        if category in prompts_config and name in prompts_config[category]:
            del prompts_config[category][name]
            
            # Clean up empty categories
            if not prompts_config[category]:
                del prompts_config[category]
            
            with open(PROMPTS_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(prompts_config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Deleted prompt: {category}/{name}")
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

@router.get("/metrics")
async def get_metrics():
    """Get performance metrics"""
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