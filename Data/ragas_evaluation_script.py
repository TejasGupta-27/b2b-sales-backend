#!/usr/bin/env python3
"""
RAGAS Evaluation Script for Hybrid Product Retriever Agent

This script evaluates the hybrid product retriever agent using the RAGAS framework
with a comprehensive test dataset covering various B2B scenarios.
"""

import json
import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import pandas as pd
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_relevancy,
    context_recall,
    answer_correctness
)

@dataclass
class EvaluationResult:
    """Container for evaluation results"""
    scenario_id: str
    conversation: List[Dict[str, str]]
    customer_context: Dict[str, Any]
    expected_requirements: Dict[str, Any]
    ground_truth_products: List[Dict[str, str]]
    retrieved_products: List[Dict[str, Any]]
    extracted_requirements: Dict[str, Any]
    retrieval_accuracy: float
    requirement_extraction_accuracy: float
    semantic_relevance_score: float
    hybrid_confidence: float
    response_time: float
    search_methods_used: Dict[str, int]

class HybridRetrieverEvaluator:
    """Evaluator for hybrid product retriever agent using RAGAS"""
    
    def __init__(self, test_dataset_path: str, agent_instance):
        """
        Initialize the evaluator
        
        Args:
            test_dataset_path: Path to the test dataset JSON file
            agent_instance: Instance of HybridProductRetrieverAgent
        """
        self.test_dataset_path = test_dataset_path
        self.agent = agent_instance
        self.test_data = self._load_test_dataset()
        
    def _load_test_dataset(self) -> Dict[str, Any]:
        """Load the test dataset from JSON file"""
        try:
            with open(self.test_dataset_path, 'r') as f:
                data = json.load(f)
            print(f"✅ Loaded test dataset with {len(data['dataset']['scenarios'])} scenarios")
            return data['dataset']
        except Exception as e:
            print(f"❌ Failed to load test dataset: {e}")
            raise
    
    async def evaluate_single_scenario(self, scenario: Dict[str, Any]) -> EvaluationResult:
        """
        Evaluate a single scenario
        
        Args:
            scenario: Scenario data from test dataset
            
        Returns:
            EvaluationResult with metrics
        """
        scenario_id = scenario['id']
        print(f"\n🔍 Evaluating scenario: {scenario_id}")
        
        # Convert conversation to AIMessage format
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in scenario['conversation']
        ]
        
        # Measure response time
        start_time = time.time()
        
        try:
            # Run the hybrid retriever
            result = await self.agent.retrieve_products(
                messages=messages,
                customer_context=scenario.get('customer_context')
            )
            
            response_time = time.time() - start_time
            
            # Extract metrics
            retrieval_accuracy = self._calculate_retrieval_accuracy(
                result['products'], 
                scenario['ground_truth_products']
            )
            
            requirement_extraction_accuracy = self._calculate_requirement_accuracy(
                result.get('requirements', {}),
                scenario['expected_requirements']
            )
            
            semantic_relevance = self._calculate_semantic_relevance(
                result['products'],
                scenario['expected_requirements']
            )
            
            return EvaluationResult(
                scenario_id=scenario_id,
                conversation=scenario['conversation'],
                customer_context=scenario.get('customer_context', {}),
                expected_requirements=scenario['expected_requirements'],
                ground_truth_products=scenario['ground_truth_products'],
                retrieved_products=result['products'],
                extracted_requirements=result.get('requirements', {}),
                retrieval_accuracy=retrieval_accuracy,
                requirement_extraction_accuracy=requirement_extraction_accuracy,
                semantic_relevance_score=semantic_relevance,
                hybrid_confidence=result.get('retrieval_confidence', 0.0),
                response_time=response_time,
                search_methods_used=result.get('search_methods', {})
            )
            
        except Exception as e:
            print(f"❌ Error evaluating scenario {scenario_id}: {e}")
            return EvaluationResult(
                scenario_id=scenario_id,
                conversation=scenario['conversation'],
                customer_context=scenario.get('customer_context', {}),
                expected_requirements=scenario['expected_requirements'],
                ground_truth_products=scenario['ground_truth_products'],
                retrieved_products=[],
                extracted_requirements={},
                retrieval_accuracy=0.0,
                requirement_extraction_accuracy=0.0,
                semantic_relevance_score=0.0,
                hybrid_confidence=0.0,
                response_time=time.time() - start_time,
                search_methods_used={}
            )
    
    def _calculate_retrieval_accuracy(
        self, 
        retrieved_products: List[Dict], 
        ground_truth: List[Dict]
    ) -> float:
        """Calculate retrieval accuracy based on ground truth products"""
        if not ground_truth:
            return 0.0
        
        # Extract product names from ground truth
        gt_names = {product['name'].lower() for product in ground_truth}
        
        # Check how many ground truth products were found
        found_count = 0
        for product in retrieved_products:
            product_name = product.get('name', '').lower()
            if product_name in gt_names:
                found_count += 1
        
        return found_count / len(ground_truth)
    
    def _calculate_requirement_accuracy(
        self, 
        extracted: Dict[str, Any], 
        expected: Dict[str, Any]
    ) -> float:
        """Calculate requirement extraction accuracy"""
        if not expected:
            return 0.0
        
        total_requirements = 0
        matched_requirements = 0
        
        # Check technical requirements
        expected_tech = set(expected.get('technical_requirements', []))
        extracted_tech = set(extracted.get('technical_requirements', []))
        
        total_requirements += len(expected_tech)
        matched_requirements += len(expected_tech.intersection(extracted_tech))
        
        # Check business requirements
        expected_business = set(expected.get('business_requirements', []))
        extracted_business = set(extracted.get('business_requirements', []))
        
        total_requirements += len(expected_business)
        matched_requirements += len(expected_business.intersection(extracted_business))
        
        # Check product categories
        expected_categories = set(expected.get('product_categories', []))
        extracted_categories = set(extracted.get('product_categories', []))
        
        total_requirements += len(expected_categories)
        matched_requirements += len(expected_categories.intersection(extracted_categories))
        
        return matched_requirements / total_requirements if total_requirements > 0 else 0.0
    
    def _calculate_semantic_relevance(
        self, 
        products: List[Dict], 
        requirements: Dict[str, Any]
    ) -> float:
        """Calculate semantic relevance score"""
        if not products:
            return 0.0
        
        # Simple semantic relevance based on hybrid scores
        total_score = 0.0
        for product in products:
            # Use hybrid score if available, otherwise use semantic score
            score = product.get('hybrid_score', product.get('semantic_score', 0.0))
            total_score += score
        
        return total_score / len(products)
    
    async def run_full_evaluation(self) -> Dict[str, Any]:
        """Run evaluation on all scenarios"""
        print(f"🚀 Starting full evaluation with {len(self.test_data['scenarios'])} scenarios")
        
        results = []
        for scenario in self.test_data['scenarios']:
            result = await self.evaluate_single_scenario(scenario)
            results.append(result)
        
        # Calculate aggregate metrics
        aggregate_metrics = self._calculate_aggregate_metrics(results)
        
        # Generate detailed report
        report = self._generate_evaluation_report(results, aggregate_metrics)
        
        return report
    
    def _calculate_aggregate_metrics(self, results: List[EvaluationResult]) -> Dict[str, float]:
        """Calculate aggregate metrics across all scenarios"""
        if not results:
            return {}
        
        metrics = {
            'avg_retrieval_accuracy': sum(r.retrieval_accuracy for r in results) / len(results),
            'avg_requirement_extraction_accuracy': sum(r.requirement_extraction_accuracy for r in results) / len(results),
            'avg_semantic_relevance': sum(r.semantic_relevance_score for r in results) / len(results),
            'avg_hybrid_confidence': sum(r.hybrid_confidence for r in results) / len(results),
            'avg_response_time': sum(r.response_time for r in results) / len(results),
            'total_scenarios': len(results),
            'successful_scenarios': len([r for r in results if r.retrieval_accuracy > 0])
        }
        
        return metrics
    
    def _generate_evaluation_report(
        self, 
        results: List[EvaluationResult], 
        aggregate_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Generate comprehensive evaluation report"""
        
        # Convert results to DataFrame for analysis
        df = pd.DataFrame([
            {
                'scenario_id': r.scenario_id,
                'retrieval_accuracy': r.retrieval_accuracy,
                'requirement_extraction_accuracy': r.requirement_extraction_accuracy,
                'semantic_relevance': r.semantic_relevance_score,
                'hybrid_confidence': r.hybrid_confidence,
                'response_time': r.response_time,
                'products_found': len(r.retrieved_products),
                'ground_truth_count': len(r.ground_truth_products)
            }
            for r in results
        ])
        
        # Scenario-wise analysis
        scenario_analysis = []
        for result in results:
            scenario_analysis.append({
                'scenario_id': result.scenario_id,
                'metrics': {
                    'retrieval_accuracy': result.retrieval_accuracy,
                    'requirement_extraction_accuracy': result.requirement_extraction_accuracy,
                    'semantic_relevance': result.semantic_relevance_score,
                    'hybrid_confidence': result.hybrid_confidence,
                    'response_time': result.response_time
                },
                'search_methods': result.search_methods_used,
                'products_retrieved': len(result.retrieved_products),
                'ground_truth_products': [p['name'] for p in result.ground_truth_products],
                'retrieved_product_names': [p.get('name', 'Unknown') for p in result.retrieved_products[:5]]  # Top 5
            })
        
        report = {
            'evaluation_summary': {
                'total_scenarios': aggregate_metrics['total_scenarios'],
                'successful_scenarios': aggregate_metrics['successful_scenarios'],
                'success_rate': aggregate_metrics['successful_scenarios'] / aggregate_metrics['total_scenarios'],
                'aggregate_metrics': aggregate_metrics
            },
            'detailed_metrics': {
                'retrieval_accuracy_stats': {
                    'mean': df['retrieval_accuracy'].mean(),
                    'std': df['retrieval_accuracy'].std(),
                    'min': df['retrieval_accuracy'].min(),
                    'max': df['retrieval_accuracy'].max()
                },
                'requirement_extraction_stats': {
                    'mean': df['requirement_extraction_accuracy'].mean(),
                    'std': df['requirement_extraction_accuracy'].std(),
                    'min': df['requirement_extraction_accuracy'].min(),
                    'max': df['requirement_extraction_accuracy'].max()
                },
                'response_time_stats': {
                    'mean': df['response_time'].mean(),
                    'std': df['response_time'].std(),
                    'min': df['response_time'].min(),
                    'max': df['response_time'].max()
                }
            },
            'scenario_analysis': scenario_analysis,
            'recommendations': self._generate_recommendations(aggregate_metrics, df)
        }
        
        return report
    
    def _generate_recommendations(
        self, 
        aggregate_metrics: Dict[str, float], 
        df: pd.DataFrame
    ) -> List[str]:
        """Generate improvement recommendations based on evaluation results"""
        recommendations = []
        
        # Retrieval accuracy recommendations
        if aggregate_metrics['avg_retrieval_accuracy'] < 0.7:
            recommendations.append(
                "Improve retrieval accuracy by enhancing semantic search embeddings "
                "and keyword matching algorithms"
            )
        
        # Requirement extraction recommendations
        if aggregate_metrics['avg_requirement_extraction_accuracy'] < 0.6:
            recommendations.append(
                "Enhance requirement extraction by improving the structured "
                "extraction prompts and fallback mechanisms"
            )
        
        # Response time recommendations
        if aggregate_metrics['avg_response_time'] > 5.0:
            recommendations.append(
                "Optimize response time by implementing caching and "
                "parallelizing search operations"
            )
        
        # Hybrid confidence recommendations
        if aggregate_metrics['avg_hybrid_confidence'] < 0.5:
            recommendations.append(
                "Improve hybrid confidence scoring by better combining "
                "keyword and semantic search results"
            )
        
        # General recommendations
        recommendations.extend([
            "Consider adding more domain-specific training data for better understanding of B2B contexts",
            "Implement A/B testing for different hybrid search weight configurations",
            "Add more comprehensive error handling and fallback mechanisms"
        ])
        
        return recommendations
    
    def save_evaluation_report(self, report: Dict[str, Any], output_path: str):
        """Save evaluation report to JSON file"""
        try:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Evaluation report saved to: {output_path}")
        except Exception as e:
            print(f"❌ Failed to save evaluation report: {e}")
    
    def print_summary(self, report: Dict[str, Any]):
        """Print evaluation summary to console"""
        summary = report['evaluation_summary']
        metrics = summary['aggregate_metrics']
        
        print("\n" + "="*60)
        print("🔍 HYBRID PRODUCT RETRIEVER EVALUATION SUMMARY")
        print("="*60)
        print(f"📊 Total Scenarios: {summary['total_scenarios']}")
        print(f"✅ Successful Scenarios: {summary['successful_scenarios']}")
        print(f"📈 Success Rate: {summary['success_rate']:.2%}")
        print("\n📋 AGGREGATE METRICS:")
        print(f"   • Retrieval Accuracy: {metrics['avg_retrieval_accuracy']:.3f}")
        print(f"   • Requirement Extraction: {metrics['avg_requirement_extraction_accuracy']:.3f}")
        print(f"   • Semantic Relevance: {metrics['avg_semantic_relevance']:.3f}")
        print(f"   • Hybrid Confidence: {metrics['avg_hybrid_confidence']:.3f}")
        print(f"   • Avg Response Time: {metrics['avg_response_time']:.2f}s")
        print("\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"   {i}. {rec}")
        print("="*60)

# Example usage function
async def run_ragas_evaluation(
    agent_instance,
    test_dataset_path: str = "Data/ragas_test_dataset.json",
    output_path: str = "Data/evaluation_report.json"
):
    """
    Run RAGAS evaluation on the hybrid product retriever agent
    
    Args:
        agent_instance: Instance of HybridProductRetrieverAgent
        test_dataset_path: Path to test dataset JSON file
        output_path: Path to save evaluation report
    """
    print("🚀 Starting RAGAS Evaluation for Hybrid Product Retriever Agent")
    
    # Initialize evaluator
    evaluator = HybridRetrieverEvaluator(test_dataset_path, agent_instance)
    
    # Run evaluation
    report = await evaluator.run_full_evaluation()
    
    # Save report
    evaluator.save_evaluation_report(report, output_path)
    
    # Print summary
    evaluator.print_summary(report)
    
    return report

if __name__ == "__main__":
    # Example usage - you would need to import and initialize your agent
    print("📝 RAGAS Evaluation Script for Hybrid Product Retriever Agent")
    print("To use this script:")
    print("1. Import your HybridProductRetrieverAgent")
    print("2. Initialize the agent with proper configuration")
    print("3. Call run_ragas_evaluation(agent_instance)")
    print("\nExample:")
    print("from ai_services.hybrid_product_retriever_agent import HybridProductRetrieverAgent")
    print("agent = HybridProductRetrieverAgent(...)")
    print("report = await run_ragas_evaluation(agent)") 