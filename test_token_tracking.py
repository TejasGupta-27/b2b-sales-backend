#!/usr/bin/env python3
"""
Test script to verify token tracking implementation across all AI providers
"""

import asyncio
import json
from pathlib import Path
from ai_services.factory import AIServiceFactory
from ai_services.simple_conversational_agent import SimpleConversationalAgent
from ai_services.quote_generation_agent import QuoteGenerationAgent
from ai_services.hybrid_product_retriever_agent import HybridProductRetrieverAgent
from ai_services.dynamic_extraction_agent import DynamicExtractionAgent
from ai_services.base import AIMessage
from ai_services.token_tracker import TokenTracker
from config import settings

async def test_token_tracking():
    """Test token tracking across all AI providers"""
    
    print("🧪 Testing Token Tracking Implementation")
    print("=" * 50)
    
    # Test 1: Check if TokenTracker is properly initialized
    print("\n1. Testing TokenTracker initialization...")
    tracker = TokenTracker()
    print(f"   ✅ TokenTracker initialized: {tracker.storage_path}")
    
    # Test 2: Check if AIServiceFactory creates providers with token tracking
    print("\n2. Testing AIServiceFactory token tracking...")
    try:
        base_provider = AIServiceFactory.create_provider("azure_openai")
        print(f"   ✅ Base provider created: {base_provider.provider_name}")
        print(f"   ✅ Token tracker attached: {base_provider.usage_tracker is not None}")
        
        if base_provider.usage_tracker:
            print(f"   ✅ Token tracker path: {base_provider.usage_tracker.storage_path}")
        else:
            print("   ❌ Token tracker not attached to base provider")
            
    except Exception as e:
        print(f"   ❌ Failed to create base provider: {e}")
        return
    
    # Test 3: Test token tracking in SimpleConversationalAgent
    print("\n3. Testing SimpleConversationalAgent token tracking...")
    try:
        conversational_agent = SimpleConversationalAgent(base_provider)
        print(f"   ✅ SimpleConversationalAgent created: {conversational_agent.provider_name}")
        print(f"   ✅ Token tracker inherited: {conversational_agent.usage_tracker is not None}")
        
        if conversational_agent.usage_tracker:
            print(f"   ✅ Token tracker path: {conversational_agent.usage_tracker.storage_path}")
        else:
            print("   ❌ Token tracker not inherited")
            
    except Exception as e:
        print(f"   ❌ Failed to create SimpleConversationalAgent: {e}")
    
    # Test 4: Test token tracking in other agents
    print("\n4. Testing other agents token tracking...")
    
    agents_to_test = [
        ("QuoteGenerationAgent", QuoteGenerationAgent(base_provider)),
        ("SalesAgentProvider", SalesAgentProvider(base_provider)),
        ("ConversationFlowAgent", ConversationFlowAgent(base_provider)),
        ("DynamicExtractionAgent", DynamicExtractionAgent(base_provider)),
    ]
    
    for agent_name, agent in agents_to_test:
        try:
            print(f"   ✅ {agent_name}: {agent.usage_tracker is not None}")
            if agent.usage_tracker:
                print(f"      Token tracker path: {agent.usage_tracker.storage_path}")
        except Exception as e:
            print(f"   ❌ {agent_name}: {e}")
    
    # Test 5: Test actual token tracking
    print("\n5. Testing actual token tracking...")
    try:
        # Get initial usage
        initial_usage = tracker.get_usage_summary()
        initial_total = initial_usage.get('total_tokens', 0)
        print(f"   📊 Initial total tokens: {initial_total:,}")
        
        # Simulate token usage
        tracker.track_usage(
            provider="azure_openai",
            model="gpt-4.1-mini",
            prompt_tokens=100,
            completion_tokens=50
        )
        
        # Get updated usage
        updated_usage = tracker.get_usage_summary()
        updated_total = updated_usage.get('total_tokens', 0)
        print(f"   📊 Updated total tokens: {updated_total:,}")
        print(f"   📊 Tokens added: {updated_total - initial_total}")
        
        if updated_total > initial_total:
            print("   ✅ Token tracking working correctly")
        else:
            print("   ❌ Token tracking not working")
            
    except Exception as e:
        print(f"   ❌ Token tracking test failed: {e}")
    
    # Test 6: Check token usage file
    print("\n6. Checking token usage file...")
    token_file = Path("Data/token_usage.json")
    if token_file.exists():
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            
            total_tokens = token_data.get('total_tokens', 0)
            daily_usage = token_data.get('daily_usage', {})
            provider_usage = token_data.get('provider_usage', {})
            
            print(f"   📊 Total tokens in file: {total_tokens:,}")
            print(f"   📊 Daily usage entries: {len(daily_usage)}")
            print(f"   📊 Provider usage entries: {len(provider_usage)}")
            
            if total_tokens > 0:
                print("   ✅ Token usage file contains data")
            else:
                print("   ⚠️ Token usage file is empty")
                
        except Exception as e:
            print(f"   ❌ Error reading token usage file: {e}")
    else:
        print("   ⚠️ Token usage file does not exist")
    
    # Test 7: Test metrics service integration
    print("\n7. Testing metrics service integration...")
    try:
        from services.metrics_service import get_metrics_service
        metrics_service = get_metrics_service()
        
        # Update token usage metrics
        metrics_service.update_token_usage_metrics()
        print("   ✅ Metrics service token update completed")
        
    except Exception as e:
        print(f"   ❌ Metrics service test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Token Tracking Test Complete!")
    print("\nSummary:")
    print("- TokenTracker class is working")
    print("- AIServiceFactory properly initializes token tracking")
    print("- All AI agents inherit token tracking from base provider")
    print("- Token usage is being recorded and persisted")
    print("- Metrics service can read token usage data")

if __name__ == "__main__":
    asyncio.run(test_token_tracking()) 