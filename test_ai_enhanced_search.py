#!/usr/bin/env python3
"""
Interactive test script for AI-enhanced search functionality
"""

import asyncio
import sys
import os
import json

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_services.factory import AIServiceFactory
from ai_services.hybrid_product_retriever_agent import HybridProductRetrieverAgent
from config import settings

async def interactive_test():
    """Interactive test for AI-enhanced search"""
    
    print("🧪 Interactive AI-Enhanced Search Test")
    print("=" * 50)
    print("Enter your queries to test the AI-enhanced search functionality.")
    print("Type 'quit' or 'exit' to end the test.")
    print("Type 'help' for available commands.")
    print()
    
    # Initialize AI provider using factory
    print("🔧 Initializing AI Provider...")
    ai_provider = AIServiceFactory.create_provider("azure_openai")
    
    # Initialize hybrid retriever
    print("🔧 Initializing Hybrid Product Retriever...")
    hybrid_retriever = HybridProductRetrieverAgent(
        base_provider=ai_provider,
        azure_embedding_endpoint=settings.azure_embedding_endpoint,
        azure_embedding_key=settings.azure_embedding_api_key
    )
    await hybrid_retriever.initialize()
    
    print("✅ Ready for interactive testing!")
    print()
    
    while True:
        try:
            # Get user input
            user_input = input("🔍 Enter your query (or 'help' for commands): ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
                
            if user_input.lower() == 'help':
                print_help()
                continue
                
            if user_input.lower() == 'demo':
                await run_demo_queries(hybrid_retriever)
                continue
                
            if user_input.lower() == 'config':
                print_config()
                continue
                
            if user_input.lower() == 'debug':
                await run_debug_tests(hybrid_retriever)
                continue
                
            # Test the user's query
            await test_custom_query(hybrid_retriever, user_input)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

def print_help():
    """Print available commands"""
    print("\n📋 Available Commands:")
    print("  help     - Show this help message")
    print("  demo     - Run predefined demo queries")
    print("  debug    - Run debug tests for AI-enhanced search")
    print("  config   - Show current configuration")
    print("  quit/exit/q - Exit the test")
    print("\n📝 Query Examples:")
    print("  - 'I need a gaming PC for competitive esports'")
    print("  - 'Looking for a workstation for video editing'")
    print("  - 'Need storage solution for small business'")
    print("  - 'High-performance CPU for AI development'")
    print("  - 'Monitor for professional color work'")
    print("  - 'i9 CPU for high-performance computing'")
    print("  - 'RTX 4080 graphics card for gaming'")
    print()

def print_config():
    """Print current configuration"""
    print("\n⚙️ Current Configuration:")
    print(f"  AI Enhanced Search: {settings.enable_ai_enhanced_search}")
    print(f"  RRF Merging: {settings.use_rrf_merging}")
    print(f"  RRF K: {settings.rrf_k}")
    print(f"  Final Result Limit: {settings.final_result_limit}")
    print(f"  Elasticsearch Weight: {settings.rrf_elasticsearch_weight}")
    print(f"  Semantic Weight: {settings.rrf_semantic_weight}")
    print()

async def test_custom_query(hybrid_retriever, query: str):
    """Test a custom query"""
    
    print(f"\n🔍 Testing Query: '{query}'")
    print("-" * 40)
    
    # Create test requirements from the query
    test_requirements = {
        "use_case": query,
        "technical_requirements": [],
        "business_requirements": [],
        "search_terms": query.split(),
        "semantic_query": query
    }
    
    try:
        # Test AI-enhanced search
        test_result = await hybrid_retriever.test_ai_enhanced_search(test_requirements)
        
        if test_result['success']:
            print(f"✅ AI-Enhanced Search Test Passed!")
            print(f"   Vector Results: {test_result['vector_results_count']}")
            print(f"   Elasticsearch Results: {test_result['elasticsearch_results_count']}")
            
            # Show dynamic query details
            dynamic_query = test_result['dynamic_query']
            print(f"   AI-Generated Semantic Query: {dynamic_query['semantic_query']}")
            print(f"   Search Strategy: {dynamic_query['search_strategy']}")
            print(f"   Selected Categories: {dynamic_query['category_filters']}")
            print(f"   AI Confidence: {dynamic_query['confidence']:.1%}")
            print(f"   Reasoning: {dynamic_query['reasoning']}")
            
            # Test full conversation analysis
            print(f"\n💬 Testing Full Conversation Analysis...")
            from ai_services.base import AIMessage
            
            conversation = [
                AIMessage(role="user", content=query)
            ]
            
            customer_context = {
                "company_name": "Test Company",
                "industry": "Technology",
                "budget_range": "$1000-$5000",
                "timeline": "Immediate"
            }
            
            result = await hybrid_retriever.analyze_conversation_and_retrieve(conversation, customer_context)
            
            print(f"✅ Conversation Analysis Complete:")
            print(f"   Products Found: {len(result.get('products', []))}")
            print(f"   Solutions Found: {len(result.get('solutions', []))}")
            print(f"   AI Enhanced: {result.get('ai_enhanced', False)}")
            print(f"   Retrieval Confidence: {result.get('retrieval_confidence', 0):.1%}")
            
            # Show top products with enhanced details
            products = result.get('products', [])
            if products:
                print(f"\n🏆 Top Products Found:")
                for i, product in enumerate(products[:5]):
                    print(f"   {i+1}. {product.get('name', 'Unknown')}")
                    print(f"      Category: {product.get('category', 'Unknown')}")
                    print(f"      Score: {product.get('_similarity_score', product.get('_score', 0)):.3f}")
                    print(f"      Source: {product.get('search_source', 'Unknown')}")
                    if product.get('ai_query_generated'):
                        print(f"      AI Generated: Yes (Confidence: {product.get('ai_confidence', 0):.1%})")
                    if product.get('rrf_score'):
                        print(f"      RRF Score: {product.get('rrf_score', 0):.4f}")
                    print()
            
            # Show search methods used
            search_methods = result.get('search_methods', {})
            if search_methods:
                print(f"🔍 Search Methods Used:")
                for method in search_methods.get('methods', []):
                    print(f"   - {method}")
                if search_methods.get('fusion_method'):
                    print(f"   - Fusion: {search_methods['fusion_method']}")
            
        else:
            print(f"❌ AI-Enhanced Search Test Failed")
            print(f"   Error: {test_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(traceback.format_exc())

async def run_debug_tests(hybrid_retriever):
    """Run specific debug tests for AI-enhanced search improvements"""
    
    print("\n🔧 Running Debug Tests for AI-Enhanced Search...")
    print("=" * 60)
    
    debug_queries = [
        "i9 CPU for high-performance computing",
        "RTX 4080 graphics card for gaming",
        "32GB DDR5 memory for workstation",
        "1TB NVMe SSD for fast storage",
        "850W power supply for gaming PC"
    ]
    
    for i, query in enumerate(debug_queries, 1):
        print(f"\n🔧 Debug Test {i}: '{query}'")
        print("-" * 50)
        
        # Create specific test requirements
        test_requirements = {
            "technical_requirements": [query],
            "search_keywords": query.split(),
            "semantic_queries": [query],
            "semantic_query": query,
            "use_case": query
        }
        
        try:
            # Test AI-enhanced search with detailed output
            test_result = await hybrid_retriever.test_ai_enhanced_search(test_requirements)
            
            if test_result['success']:
                dynamic_query = test_result['dynamic_query']
                print(f"✅ AI Query Generation:")
                print(f"   Semantic Query: {dynamic_query['semantic_query']}")
                print(f"   Search Strategy: {dynamic_query['search_strategy']}")
                print(f"   Categories: {dynamic_query['category_filters']}")
                print(f"   Confidence: {dynamic_query['confidence']:.1%}")
                print(f"   Reasoning: {dynamic_query['reasoning']}")
                
                # Test individual search methods
                print(f"\n🔍 Testing Individual Search Methods...")
                
                # Test vector search
                if hybrid_retriever.vector_service:
                    vector_results = await hybrid_retriever.vector_service.vector_search_products_with_ai_query(
                        test_requirements, size=5
                    )
                    print(f"   Vector Search Results: {len(vector_results)} products")
                    for j, product in enumerate(vector_results[:3]):
                        print(f"     {j+1}. {product.get('name', 'Unknown')} (Score: {product.get('_similarity_score', 0):.3f})")
                
                # Test Elasticsearch search
                if hybrid_retriever.vector_service:
                    es_results = await hybrid_retriever.vector_service.elasticsearch_search_with_ai_query(
                        test_requirements, size=5
                    )
                    print(f"   Elasticsearch Results: {len(es_results)} products")
                    for j, product in enumerate(es_results[:3]):
                        print(f"     {j+1}. {product.get('name', 'Unknown')} (Score: {product.get('_score', 0):.3f})")
                
            else:
                print(f"❌ Debug test failed: {test_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Debug test error: {e}")

async def run_demo_queries(hybrid_retriever):
    """Run predefined demo queries"""
    
    print("\n🎯 Running Demo Queries...")
    print("=" * 40)
    
    demo_queries = [
        "I need a high-performance gaming PC for competitive esports. I want to run games at 1440p with high frame rates.",
        "Looking for a professional workstation for video editing and 3D rendering. Need something that can handle 4K video.",
        "Need a storage solution for our small business. We need to backup important files and share them across the network.",
        "Looking for a high-end CPU for AI and machine learning development. Need something with lots of cores.",
        "Need a professional monitor for color-accurate work. Something suitable for photo and video editing.",
        "i9 CPU for high-performance computing tasks",
        "RTX 4080 graphics card for gaming and content creation"
    ]
    
    for i, query in enumerate(demo_queries, 1):
        print(f"\n🎯 Demo Query {i}: {query}")
        print("-" * 60)
        await test_custom_query(hybrid_retriever, query)
        print()

async def test_custom_query_standalone(query: str):
    """Standalone function to test a single query (for command line usage)"""
    
    # Initialize components
    ai_provider = AIServiceFactory.create_provider("azure_openai")
    
    hybrid_retriever = HybridProductRetrieverAgent(
        base_provider=ai_provider,
        azure_embedding_endpoint=settings.azure_embedding_endpoint,
        azure_embedding_key=settings.azure_embedding_api_key
    )
    await hybrid_retriever.initialize()
    
    # Test the query
    await test_custom_query(hybrid_retriever, query)

if __name__ == "__main__":
    # Check if command line arguments are provided
    if len(sys.argv) > 1:
        # Non-interactive mode with command line arguments
        query = " ".join(sys.argv[1:])
        print(f"🔍 Testing query: '{query}'")
        asyncio.run(test_custom_query_standalone(query))
    else:
        # Interactive mode
        asyncio.run(interactive_test()) 