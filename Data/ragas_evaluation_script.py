#!/usr/bin/env python3
"""
RAGAS Evaluation Script for Hybrid Product Retriever Agent

This script evaluates the hybrid product retriever agent using RAGAS principles
with a comprehensive test dataset covering various B2B scenarios.
"""

import json
import asyncio
import time
import re
import sys
import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Add the app directory to Python path for imports
sys.path.append('/app')

# Configure comprehensive logging for evaluation
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Console output
        logging.FileHandler('/app/logs/ragas_evaluation.log')  # File output
    ]
)

# Set specific loggers to DEBUG level to see category debug messages
logging.getLogger('ai_services.hybrid_product_retriever_agent').setLevel(logging.DEBUG)
logging.getLogger('services.elasticsearch_vector_service').setLevel(logging.DEBUG)
logging.getLogger('__main__').setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.info("🔍 RAGAS Evaluation: DEBUG logging enabled for category debugging")

@dataclass
class EvaluationResult:
    """Container for evaluation results"""
    scenario_id: str
    conversation: List[Dict[str, str]]
    customer_context: Dict[str, Any]
    expected_requirements: Dict[str, Any]
    ground_truth_products: List[Dict[str, Any]]
    retrieved_products: List[Dict[str, Any]]
    retrieval_accuracy: float
    requirement_extraction_accuracy: float
    semantic_relevance_score: float
    response_time: float
    hybrid_performance: Dict[str, float]

class RAGASEvaluator:
    """RAGAS-style evaluator for hybrid product retriever agent"""
    
    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the evaluator with embedding model"""
        try:
            self.embedding_model = SentenceTransformer(embedding_model_name)
            self.use_embeddings = True
            print(f"✅ Using sentence-transformers with model: {embedding_model_name}")
        except Exception as e:
            print(f"⚠️  Failed to load sentence-transformers: {e}")
            print("   Falling back to text similarity method")
            self.embedding_model = None
            self.use_embeddings = False
        
    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        if self.use_embeddings and self.embedding_model:
            try:
                embeddings = self.embedding_model.encode([text1, text2])
                similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
                return float(similarity)
            except Exception as e:
                print(f"⚠️  Embedding similarity failed: {e}")
                # Fall back to text similarity
                pass
        
        # Fallback to text similarity
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def extract_requirements_from_conversation(self, conversation: List[Dict[str, str]]) -> Dict[str, Any]:
        """Extract requirements from conversation"""
        # Combine all user messages
        user_messages = " ".join([
            msg["content"] for msg in conversation if msg["role"] == "user"
        ])
        
        # Simple keyword-based requirement extraction
        requirements = {
            "technical_requirements": [],
            "business_requirements": [],
            "product_categories": [],
            "search_terms": []
        }
        
        # Extract technical requirements
        tech_keywords = ["RAM", "GPU", "CPU", "storage", "memory", "monitor", "network", "TB", "GB"]
        for keyword in tech_keywords:
            if keyword.lower() in user_messages.lower():
                requirements["technical_requirements"].append(keyword)
        
        # Extract business requirements
        business_keywords = ["budget", "office", "gaming", "workstation", "server", "employees", "team"]
        for keyword in business_keywords:
            if keyword.lower() in user_messages.lower():
                requirements["business_requirements"].append(keyword)
        
        # Extract product categories
        category_keywords = ["cpu", "gpu", "memory", "storage", "monitor", "workstation", "server", "nas"]
        for keyword in category_keywords:
            if keyword.lower() in user_messages.lower():
                requirements["product_categories"].append(keyword)
        
        # Extract search terms (simplified)
        words = re.findall(r'\b\w+\b', user_messages.lower())
        requirements["search_terms"] = [word for word in words if len(word) > 3][:10]
        
        return requirements
    
    def calculate_retrieval_accuracy(self, ground_truth: List[Dict], retrieved: List[Dict]) -> float:
        """Calculate retrieval accuracy based on ground truth products"""
        if not ground_truth or not retrieved:
            return 0.0
        
        # Simple matching based on product names and categories
        ground_truth_info = set()
        for product in ground_truth:
            ground_truth_info.add(product["name"].lower())
            ground_truth_info.add(product["category"].lower())
        
        retrieved_info = set()
        for product in retrieved:
            retrieved_info.add(product.get("name", "").lower())
            retrieved_info.add(product.get("category", "").lower())
        
        matches = len(ground_truth_info.intersection(retrieved_info))
        return matches / len(ground_truth_info) if ground_truth_info else 0.0
    
    def calculate_requirement_extraction_accuracy(self, expected: Dict, extracted: Dict) -> float:
        """Calculate requirement extraction accuracy"""
        if not expected or not extracted:
            return 0.0
        
        total_requirements = 0
        matched_requirements = 0
        
        # Compare technical requirements
        expected_tech = set(expected.get("technical_requirements", []))
        extracted_tech = set(extracted.get("technical_requirements", []))
        total_requirements += len(expected_tech)
        matched_requirements += len(expected_tech.intersection(extracted_tech))
        
        # Compare business requirements
        expected_business = set(expected.get("business_requirements", []))
        extracted_business = set(extracted.get("business_requirements", []))
        total_requirements += len(expected_business)
        matched_requirements += len(expected_business.intersection(extracted_business))
        
        return matched_requirements / total_requirements if total_requirements > 0 else 0.0
    
    def calculate_semantic_relevance(self, query: str, products: List[Dict]) -> float:
        """Calculate semantic relevance between query and retrieved products"""
        if not products:
            return 0.0
        
        # Combine product information for similarity calculation
        product_texts = []
        for product in products:
            product_text = f"{product.get('name', '')} {product.get('category', '')}"
            product_texts.append(product_text)
        
        # Calculate average similarity
        similarities = []
        for product_text in product_texts:
            similarity = self.calculate_semantic_similarity(query, product_text)
            similarities.append(similarity)
        
        return np.mean(similarities) if similarities else 0.0

async def initialize_hybrid_retriever():
    """Initialize the hybrid product retriever agent"""
    try:
        from ai_services.hybrid_product_retriever_agent import HybridProductRetrieverAgent
        from ai_services.azure_openai import AzureOpenAIProvider
        from config import settings
        
        # Initialize base provider (Azure OpenAI)
        base_provider = AzureOpenAIProvider(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            deployment_name=settings.azure_openai_deployment_name,
            api_version=settings.azure_openai_api_version
        )
        
        # Initialize hybrid retriever
        hybrid_retriever = HybridProductRetrieverAgent(
            base_provider=base_provider,
            azure_embedding_endpoint=settings.azure_embedding_endpoint,
            azure_embedding_key=settings.azure_embedding_api_key
        )
        
        # Initialize the retriever
        await hybrid_retriever.initialize()
        
        print("✅ Hybrid Product Retriever initialized successfully")
        return hybrid_retriever
        
    except Exception as e:
        print(f"❌ Failed to initialize hybrid retriever: {e}")
        print("   Will use simulation mode instead")
        return None

async def run_ragas_evaluation(agent=None, dataset_path: str = "/app/Data/ragas_test_dataset.json") -> Dict[str, Any]:
    """
    Run RAGAS evaluation on the hybrid product retriever agent
    
    Args:
        agent: Initialized HybridProductRetrieverAgent instance (optional)
        dataset_path: Path to the test dataset JSON file
    
    Returns:
        Dictionary containing evaluation results and metrics
    """
    
    # Load test dataset
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)
    
    evaluator = RAGASEvaluator()
    results = []
    
    # Initialize agent if not provided
    if agent is None:
        print("🔧 Initializing Hybrid Product Retriever Agent...")
        agent = await initialize_hybrid_retriever()
    
    print(f"Starting RAGAS evaluation with {len(dataset['dataset']['scenarios'])} scenarios...")
    print(f"Agent type: {'Hybrid Product Retriever' if agent else 'Simulation Mode'}")
    
    for scenario in dataset['dataset']['scenarios']:
        print(f"\nEvaluating scenario: {scenario['id']}")
        
        # Convert conversation to AIMessage format
        from ai_services.base import AIMessage
        conversation_messages = [
            AIMessage(role=msg["role"], content=msg["content"])
            for msg in scenario['conversation']
        ]
        
        # Extract requirements using our evaluator
        extracted_requirements = evaluator.extract_requirements_from_conversation(
            scenario['conversation']
        )
        
        # Use actual agent or simulation
        start_time = time.time()
        
        try:
            if agent:
                # Use actual hybrid retriever
                retrieval_result = await agent.retrieve_products(
                    conversation_messages, 
                    scenario['customer_context']
                )
                
                retrieved_products = retrieval_result.get('products', [])
                print(f"  - Agent found {len(retrieved_products)} products")
                print(f"  - Retrieval confidence: {retrieval_result.get('retrieval_confidence', 0.0):.2f}")
                print(f"  - Search methods: {retrieval_result.get('search_methods', {}).get('methods', [])}")
                
            else:
                # Fallback to simulation
                conversation_text = " ".join([
                    msg["content"] for msg in scenario['conversation']
                ])
                
                if "video editing" in conversation_text.lower():
                    retrieved_products = [
                        {"name": "AMD Ryzen 9 7950X", "category": "cpu"},
                        {"name": "32GB DDR5 RAM", "category": "memory"},
                        {"name": "NVIDIA RTX 4080", "category": "video_card"}
                    ]
                elif "nas" in conversation_text.lower() or "storage" in conversation_text.lower():
                    retrieved_products = [
                        {"name": "Synology DS920+", "category": "storage"},
                        {"name": "WD Red 4TB HDD", "category": "storage"}
                    ]
                elif "gaming" in conversation_text.lower():
                    retrieved_products = [
                        {"name": "NVIDIA RTX 4070 Ti", "category": "video_card"},
                        {"name": "AMD Ryzen 7 7700X", "category": "cpu"}
                    ]
                elif "ai" in conversation_text.lower() or "training" in conversation_text.lower():
                    retrieved_products = [
                        {"name": "NVIDIA RTX 4090", "category": "video_card"},
                        {"name": "Samsung 990 Pro 2TB NVMe", "category": "storage"}
                    ]
                else:
                    retrieved_products = [
                        {"name": "Sample Product 1", "category": "cpu"},
                        {"name": "Sample Product 2", "category": "memory"}
                    ]
            
            response_time = time.time() - start_time
            
            # Calculate metrics
            # Use llm_generated_product_names as ground truth, fallback to empty list if not found
            ground_truth_products = scenario.get('llm_generated_product_names', [])
            if ground_truth_products:
                # Convert the structure to match expected format
                ground_truth_products = [
                    {"name": item.get("product_name", ""), "category": item.get("category", "")}
                    for item in ground_truth_products
                ]
            
            retrieval_accuracy = evaluator.calculate_retrieval_accuracy(
                ground_truth_products, 
                retrieved_products
            )
            
            requirement_extraction_accuracy = evaluator.calculate_requirement_extraction_accuracy(
                scenario['expected_requirements'],
                extracted_requirements
            )
            
            semantic_relevance = evaluator.calculate_semantic_relevance(
                " ".join([msg["content"] for msg in scenario['conversation']]),
                retrieved_products
            )
            
            # Create result
            result = EvaluationResult(
                scenario_id=scenario['id'],
                conversation=scenario['conversation'],
                customer_context=scenario['customer_context'],
                expected_requirements=scenario['expected_requirements'],
                ground_truth_products=ground_truth_products,
                retrieved_products=retrieved_products,
                retrieval_accuracy=retrieval_accuracy,
                requirement_extraction_accuracy=requirement_extraction_accuracy,
                semantic_relevance_score=semantic_relevance,
                response_time=response_time,
                hybrid_performance={
                    "keyword_search_score": 0.8,  # Placeholder
                    "semantic_search_score": 0.7,  # Placeholder
                    "hybrid_merge_score": 0.75     # Placeholder
                }
            )
            
            results.append(result)
            
            print(f"  - Retrieval Accuracy: {retrieval_accuracy:.2f}")
            print(f"  - Requirement Extraction: {requirement_extraction_accuracy:.2f}")
            print(f"  - Semantic Relevance: {semantic_relevance:.2f}")
            print(f"  - Response Time: {response_time:.2f}s")
            
        except Exception as e:
            print(f"  - Error evaluating scenario: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Calculate overall metrics
    if results:
        overall_metrics = {
            "average_retrieval_accuracy": np.mean([r.retrieval_accuracy for r in results]),
            "average_requirement_extraction": np.mean([r.requirement_extraction_accuracy for r in results]),
            "average_semantic_relevance": np.mean([r.semantic_relevance_score for r in results]),
            "average_response_time": np.mean([r.response_time for r in results]),
            "total_scenarios_evaluated": len(results)
        }
    else:
        overall_metrics = {
            "average_retrieval_accuracy": 0.0,
            "average_requirement_extraction": 0.0,
            "average_semantic_relevance": 0.0,
            "average_response_time": 0.0,
            "total_scenarios_evaluated": 0
        }
    
    # Create evaluation report
    evaluation_report = {
        "evaluation_summary": {
            "dataset_name": dataset['dataset']['name'],
            "total_scenarios": len(dataset['dataset']['scenarios']),
            "evaluated_scenarios": len(results),
            "overall_metrics": overall_metrics,
            "agent_used": "Hybrid Product Retriever" if agent else "Simulation Mode"
        },
        "detailed_results": [
            {
                "scenario_id": r.scenario_id,
                "retrieval_accuracy": r.retrieval_accuracy,
                "requirement_extraction_accuracy": r.requirement_extraction_accuracy,
                "semantic_relevance_score": r.semantic_relevance_score,
                "response_time": r.response_time,
                "hybrid_performance": r.hybrid_performance
            }
            for r in results
        ],
        "recommendations": generate_recommendations(overall_metrics)
    }
    
    return evaluation_report

def generate_recommendations(metrics: Dict[str, float]) -> List[str]:
    """Generate recommendations based on evaluation metrics"""
    recommendations = []
    
    if metrics["average_retrieval_accuracy"] < 0.7:
        recommendations.append("Improve product retrieval accuracy by enhancing search algorithms")
    
    if metrics["average_requirement_extraction"] < 0.6:
        recommendations.append("Enhance requirement extraction by improving NLP processing")
    
    if metrics["average_semantic_relevance"] < 0.6:
        recommendations.append("Improve semantic understanding by fine-tuning embedding models")
    
    if metrics["average_response_time"] > 2.0:
        recommendations.append("Optimize response time by improving search efficiency")
    
    if not recommendations:
        recommendations.append("Overall performance is good. Consider fine-tuning for specific use cases.")
    
    return recommendations

def print_evaluation_report(report: Dict[str, Any]):
    """Print a formatted evaluation report"""
    print("\n" + "="*60)
    print("RAGAS EVALUATION REPORT")
    print("="*60)
    
    summary = report["evaluation_summary"]
    metrics = summary["overall_metrics"]
    
    print(f"\nDataset: {summary['dataset_name']}")
    print(f"Agent Used: {summary['agent_used']}")
    print(f"Scenarios Evaluated: {metrics['total_scenarios_evaluated']}/{summary['total_scenarios']}")
    
    print(f"\nOverall Metrics:")
    print(f"  - Average Retrieval Accuracy: {metrics['average_retrieval_accuracy']:.3f}")
    print(f"  - Average Requirement Extraction: {metrics['average_requirement_extraction']:.3f}")
    print(f"  - Average Semantic Relevance: {metrics['average_semantic_relevance']:.3f}")
    print(f"  - Average Response Time: {metrics['average_response_time']:.3f}s")
    
    print(f"\nRecommendations:")
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"  {i}. {rec}")
    
    print("\n" + "="*60)

# Example usage
if __name__ == "__main__":
    async def main():
        # Run evaluation with actual agent
        report = await run_ragas_evaluation()
        print_evaluation_report(report)
    
    asyncio.run(main()) 