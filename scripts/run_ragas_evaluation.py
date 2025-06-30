#!/usr/bin/env python3
"""
Simple script to run RAGAS evaluation in Docker container with actual hybrid product retriever
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.append('/app')

async def main():
    """Main function to run RAGAS evaluation with actual agent"""
    try:
        # Import the evaluation script
        from Data.ragas_evaluation_script import run_ragas_evaluation, print_evaluation_report
        
        print("🚀 Starting RAGAS Evaluation for Hybrid Product Retriever Agent")
        print("=" * 60)
        
        # Run the evaluation with actual agent
        report = await run_ragas_evaluation()
        
        # Print the report
        print_evaluation_report(report)
        
        # Save results to file
        import json
        with open('/app/Data/evaluation_results.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✅ Evaluation completed! Results saved to /app/Data/evaluation_results.json")
        
        # Print summary
        metrics = report["evaluation_summary"]["overall_metrics"]
        print(f"\n📊 Summary:")
        print(f"   - Retrieval Accuracy: {metrics['average_retrieval_accuracy']:.1%}")
        print(f"   - Requirement Extraction: {metrics['average_requirement_extraction']:.1%}")
        print(f"   - Semantic Relevance: {metrics['average_semantic_relevance']:.1%}")
        print(f"   - Response Time: {metrics['average_response_time']:.2f}s")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed and the agent module is available")
    except Exception as e:
        print(f"❌ Error running evaluation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 