#!/usr/bin/env python3
"""
Fix data population issues and create sample solutions
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_sample_solutions():
    """Create sample solutions data"""
    
    sample_solutions = [
        {
            "id": "video-backup-solution-1",
            "name": "Enterprise Video Backup Solution",
            "description": "Complete video backup solution for media companies with 16TB storage capacity and RAID 6 protection",
            "use_case": "Video backup storage for media production companies",
            "industry": ["media", "entertainment", "production"],
            "company_size": "enterprise",
            "budget_range": "high",
            "components": [
                {
                    "product_id": "nas-server-16tb",
                    "name": "16TB NAS Server",
                    "quantity": 1,
                    "price": 2499.99
                },
                {
                    "product_id": "raid-controller",
                    "name": "RAID 6 Controller",
                    "quantity": 1,
                    "price": 299.99
                },
                {
                    "product_id": "network-switch",
                    "name": "2.5GbE Network Switch",
                    "quantity": 1,
                    "price": 199.99
                }
            ],
            "total_price": 2999.97,
            "implementation_time": "2-3 weeks",
            "benefits": [
                "16TB storage capacity for large video files",
                "RAID 6 protection against drive failures",
                "2.5GbE transfer speeds for fast backup",
                "Enterprise-grade reliability"
            ],
            "requirements": [
                "Network infrastructure with 2.5GbE support",
                "IT staff for initial setup",
                "Backup software configuration"
            ]
        },
        {
            "id": "small-business-storage-1",
            "name": "Small Business Storage Solution",
            "description": "Affordable storage solution for small businesses with 4TB capacity and basic RAID protection",
            "use_case": "File storage and backup for small businesses",
            "industry": ["small_business", "general"],
            "company_size": "small",
            "budget_range": "medium",
            "components": [
                {
                    "product_id": "nas-4tb",
                    "name": "4TB NAS Device",
                    "quantity": 1,
                    "price": 899.99
                },
                {
                    "product_id": "network-cable",
                    "name": "Cat6 Network Cables",
                    "quantity": 2,
                    "price": 29.99
                }
            ],
            "total_price": 929.98,
            "implementation_time": "1 week",
            "benefits": [
                "4TB storage for business files",
                "Easy setup and management",
                "Remote access capabilities",
                "Automatic backup features"
            ],
            "requirements": [
                "Basic network infrastructure",
                "Internet connection for remote access"
            ]
        },
        {
            "id": "workstation-solution-1",
            "name": "Professional Workstation Solution",
            "description": "High-performance workstation for professional applications like CAD, 3D modeling, and video editing",
            "use_case": "Professional workstation for design and engineering",
            "industry": ["engineering", "architecture", "media"],
            "company_size": "medium",
            "budget_range": "high",
            "components": [
                {
                    "product_id": "workstation-cpu",
                    "name": "Intel Xeon W-2295 Processor",
                    "quantity": 1,
                    "price": 1499.99
                },
                {
                    "product_id": "workstation-gpu",
                    "name": "NVIDIA Quadro RTX 4000",
                    "quantity": 1,
                    "price": 899.99
                },
                {
                    "product_id": "workstation-ram",
                    "name": "32GB DDR4 ECC Memory",
                    "quantity": 2,
                    "price": 299.99
                },
                {
                    "product_id": "workstation-storage",
                    "name": "1TB NVMe SSD",
                    "quantity": 1,
                    "price": 169.99
                }
            ],
            "total_price": 3169.96,
            "implementation_time": "1-2 weeks",
            "benefits": [
                "Professional-grade performance",
                "Optimized for CAD and 3D applications",
                "Reliable ECC memory",
                "Fast NVMe storage"
            ],
            "requirements": [
                "Professional software licenses",
                "Adequate power supply",
                "Proper cooling system"
            ]
        }
    ]
    
    # Create solutions directory if it doesn't exist
    solutions_dir = Path("Data/json")
    solutions_dir.mkdir(parents=True, exist_ok=True)
    
    # Save sample solutions
    solutions_file = solutions_dir / "sample_solutions.json"
    with open(solutions_file, 'w', encoding='utf-8') as f:
        json.dump(sample_solutions, f, indent=2)
    
    logger.info(f"✅ Created sample solutions file: {solutions_file}")
    logger.info(f"   Solutions created: {len(sample_solutions)}")
    
    return sample_solutions

async def fix_elasticsearch_data():
    """Fix Elasticsearch data issues"""
    
    try:
        from services.elasticsearch_service import get_elasticsearch_service
        from services.elasticsearch_vector_service import get_elasticsearch_vector_service
        from config import settings
        
        logger.info("🔧 Fixing Elasticsearch data issues...")
        
        # Get services
        es_service = get_elasticsearch_service()
        vector_service = get_elasticsearch_vector_service(
            settings.azure_embedding_endpoint,
            settings.azure_embedding_key
        )
        
        # Initialize vector service
        await vector_service.initialize()
        
        # Clear existing data to start fresh
        logger.info("🧹 Clearing existing data...")
        try:
            await es_service.client.indices.delete(index=es_service.products_index, ignore=[404])
            await es_service.client.indices.delete(index=es_service.solutions_index, ignore=[404])
            await vector_service.client.indices.delete(index=vector_service.products_index, ignore=[404])
            await vector_service.client.indices.delete(index=vector_service.solutions_index, ignore=[404])
        except Exception as e:
            logger.warning(f"Warning clearing indices: {e}")
        
        # Recreate indices
        logger.info("🏗️ Recreating indices...")
        await es_service.create_indices()
        await vector_service.create_vector_indices()
        
        # Load data with improved processing
        logger.info("📦 Loading data with improved processing...")
        
        # Load main elasticsearch data
        await es_service.load_initial_data()
        
        # Load vector data
        vector_results = await vector_service.load_data_from_json(max_per_file=100)
        
        logger.info("✅ Data loading complete!")
        logger.info(f"   Vector results: {vector_results}")
        
        # Verify data
        await verify_data_quality(es_service, vector_service)
        
    except Exception as e:
        logger.error(f"❌ Error fixing Elasticsearch data: {e}")
        raise

async def verify_data_quality(es_service, vector_service):
    """Verify the quality of loaded data"""
    
    logger.info("🔍 Verifying data quality...")
    
    # Check main elasticsearch
    try:
        products_count = await es_service.client.count(index=es_service.products_index)
        solutions_count = await es_service.client.count(index=es_service.solutions_index)
        
        logger.info(f"📊 Main Elasticsearch:")
        logger.info(f"   Products: {products_count['count']}")
        logger.info(f"   Solutions: {solutions_count['count']}")
        
        # Sample a few products to check quality
        if products_count['count'] > 0:
            response = await es_service.client.search(
                index=es_service.products_index,
                body={"query": {"match_all": {}}, "size": 3}
            )
            
            for hit in response['hits']['hits']:
                product = hit['_source']
                logger.info(f"   Sample product: {product.get('name', 'N/A')} (Category: {product.get('category', 'N/A')})")
        
    except Exception as e:
        logger.warning(f"Warning checking main elasticsearch: {e}")
    
    # Check vector elasticsearch
    try:
        vector_products_count = await vector_service.client.count(index=vector_service.products_index)
        vector_solutions_count = await vector_service.client.count(index=vector_service.solutions_index)
        
        logger.info(f"📊 Vector Elasticsearch:")
        logger.info(f"   Products: {vector_products_count['count']}")
        logger.info(f"   Solutions: {vector_solutions_count['count']}")
        
    except Exception as e:
        logger.warning(f"Warning checking vector elasticsearch: {e}")

async def main():
    """Main function"""
    
    logger.info("🚀 Starting data population fix...")
    
    # Create sample solutions
    await create_sample_solutions()
    
    # Fix elasticsearch data
    await fix_elasticsearch_data()
    
    logger.info("✅ Data population fix complete!")

if __name__ == "__main__":
    asyncio.run(main())