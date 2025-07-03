#!/usr/bin/env python3
"""
Debug script to identify token tracking issues
"""

import asyncio
import json
import requests
from pathlib import Path
from ai_services.factory import AIServiceFactory
from ai_services.simple_conversational_agent import SimpleConversationalAgent
from ai_services.base import AIMessage
from ai_services.token_tracker import TokenTracker
from services.metrics_service import get_metrics_service
from config import settings

async def debug_token_tracking():
    """Debug token tracking issues step by step"""
    
    print("🔍 Token Tracking Diagnostic")
    print("=" * 50)
    
    # Step 1: Check token usage file
    print("\n1. Checking token usage file...")
    token_file = Path("Data/token_usage.json")
    if token_file.exists():
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            
            total_tokens = token_data.get('total_tokens', 0)
            daily_usage = token_data.get('daily_usage', {})
            provider_usage = token_data.get('provider_usage', {})
            
            print(f"   📊 Total tokens: {total_tokens:,}")
            print(f"   📊 Daily usage entries: {len(daily_usage)}")
            print(f"   📊 Provider usage entries: {len(provider_usage)}")
            
            if total_tokens > 0:
                print("   ✅ Token usage file contains data")
                print(f"   📊 Recent daily usage:")
                for date, usage in list(daily_usage.items())[-3:]:
                    print(f"      {date}: {usage.get('tokens', 0):,} tokens")
            else:
                print("   ⚠️ Token usage file is empty")
                
        except Exception as e:
            print(f"   ❌ Error reading token usage file: {e}")
    else:
        print("   ❌ Token usage file does not exist")
    
    # Step 2: Test TokenTracker directly
    print("\n2. Testing TokenTracker directly...")
    try:
        tracker = TokenTracker()
        initial_total = tracker.get_usage_summary().get('total_tokens', 0)
        print(f"   📊 Initial total: {initial_total:,}")
        
        # Track some test usage
        tracker.track_usage(
            provider="azure_openai",
            model="gpt-4.1-mini",
            prompt_tokens=50,
            completion_tokens=25
        )
        
        updated_total = tracker.get_usage_summary().get('total_tokens', 0)
        print(f"   📊 After test tracking: {updated_total:,}")
        print(f"   📊 Difference: {updated_total - initial_total}")
        
        if updated_total > initial_total:
            print("   ✅ TokenTracker working correctly")
        else:
            print("   ❌ TokenTracker not working")
            
    except Exception as e:
        print(f"   ❌ TokenTracker test failed: {e}")
    
    # Step 3: Test AI Provider creation
    print("\n3. Testing AI Provider creation...")
    try:
        base_provider = AIServiceFactory.create_provider("azure_openai")
        print(f"   ✅ Base provider created: {base_provider.provider_name}")
        print(f"   ✅ Is configured: {base_provider.is_configured()}")
        print(f"   ✅ Token tracker attached: {base_provider.usage_tracker is not None}")
        
        if base_provider.usage_tracker:
            print(f"   📊 Token tracker path: {base_provider.usage_tracker.storage_path}")
        else:
            print("   ❌ Token tracker not attached to base provider")
            
    except Exception as e:
        print(f"   ❌ Failed to create base provider: {e}")
        return None
    
    # Step 4: Test actual AI call with token tracking
    print("\n4. Testing actual AI call with token tracking...")
    if base_provider and base_provider.is_configured():
        try:
            # Get initial usage from provider's tracker
            if base_provider.usage_tracker:
                initial_usage = base_provider.usage_tracker.get_usage_summary()
                initial_total = initial_usage.get('total_tokens', 0)
                print(f"   📊 Initial tokens from provider tracker: {initial_total:,}")
            
            # Make a simple AI call
            test_messages = [AIMessage(role="user", content="Hello, this is a test message.")]
            response = await base_provider.generate_response(test_messages, max_tokens=50)
            
            print(f"   ✅ AI response generated")
            print(f"   📊 Response content length: {len(response.content)}")
            print(f"   📊 Usage reported: {response.usage}")
            
            # Check if tokens were tracked
            if base_provider.usage_tracker:
                updated_usage = base_provider.usage_tracker.get_usage_summary()
                updated_total = updated_usage.get('total_tokens', 0)
                print(f"   📊 Updated tokens from provider tracker: {updated_total:,}")
                print(f"   📊 Tokens added: {updated_total - initial_total}")
                
                if updated_total > initial_total:
                    print("   ✅ Token tracking working in AI provider")
                else:
                    print("   ❌ Token tracking NOT working in AI provider")
            
        except Exception as e:
            print(f"   ❌ AI call test failed: {e}")
    else:
        print("   ⚠️ Skipping AI call test - provider not configured")
    
    # Step 5: Test SimpleConversationalAgent
    print("\n5. Testing SimpleConversationalAgent token tracking...")
    if base_provider:
        try:
            conversational_agent = SimpleConversationalAgent(base_provider)
            print(f"   ✅ SimpleConversationalAgent created")
            print(f"   ✅ Token tracker inherited: {conversational_agent.usage_tracker is not None}")
            
            if conversational_agent.usage_tracker:
                # Test response generation
                test_messages = [AIMessage(role="user", content="What products do you recommend?")]
                
                initial_usage = conversational_agent.usage_tracker.get_usage_summary()
                initial_total = initial_usage.get('total_tokens', 0)
                print(f"   📊 Initial tokens: {initial_total:,}")
                
                await conversational_agent.initialize()
                response = await conversational_agent.generate_response(
                    test_messages, 
                    customer_context={"company_name": "Test Company"}
                )
                
                updated_usage = conversational_agent.usage_tracker.get_usage_summary()
                updated_total = updated_usage.get('total_tokens', 0)
                print(f"   📊 Updated tokens: {updated_total:,}")
                print(f"   📊 Tokens added: {updated_total - initial_total}")
                
                if updated_total > initial_total:
                    print("   ✅ Token tracking working in SimpleConversationalAgent")
                else:
                    print("   ❌ Token tracking NOT working in SimpleConversationalAgent")
                    
        except Exception as e:
            print(f"   ❌ SimpleConversationalAgent test failed: {e}")
    
    # Step 6: Test metrics service integration
    print("\n6. Testing metrics service integration...")
    try:
        metrics_service = get_metrics_service()
        
        # Update token usage metrics
        metrics_service.update_token_usage_metrics()
        print("   ✅ Metrics service token update completed")
        
        # Try to get metrics
        metrics_data = metrics_service.get_metrics()
        if "b2b_token_usage" in metrics_data:
            print("   ✅ Token usage metrics found in Prometheus output")
            # Count lines containing token metrics
            token_lines = [line for line in metrics_data.split('\n') if 'b2b_token_usage' in line and not line.startswith('#')]
            print(f"   📊 Token metric lines: {len(token_lines)}")
        else:
            print("   ❌ Token usage metrics NOT found in Prometheus output")
            
    except Exception as e:
        print(f"   ❌ Metrics service test failed: {e}")
    
    # Step 7: Test metrics endpoint
    print("\n7. Testing metrics endpoint...")
    try:
        # Try to hit the metrics endpoint locally
        response = requests.get("http://localhost:3001/metrics", timeout=5)
        if response.status_code == 200:
            metrics_text = response.text
            if "b2b_token_usage" in metrics_text:
                print("   ✅ Metrics endpoint accessible and contains token metrics")
                # Count token metrics
                token_lines = [line for line in metrics_text.split('\n') if 'b2b_token_usage' in line and not line.startswith('#')]
                print(f"   📊 Token metric lines in endpoint: {len(token_lines)}")
                
                # Show some sample metrics
                print("   📊 Sample token metrics:")
                for line in token_lines[:3]:
                    print(f"      {line}")
            else:
                print("   ⚠️ Metrics endpoint accessible but no token metrics found")
        else:
            print(f"   ⚠️ Metrics endpoint returned status {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Could not reach metrics endpoint: {e}")
        print("   ℹ️ This is normal if the server is not running")
    
    print("\n" + "=" * 50)
    print("🎯 Diagnostic Summary:")
    print("   - Check if token data is being written to the JSON file")
    print("   - Verify AI providers are calling _track_usage()")
    print("   - Ensure metrics service reads the JSON file correctly") 
    print("   - Confirm metrics endpoint exposes the data")
    print("   - Check if Grafana can scrape the metrics endpoint")

if __name__ == "__main__":
    asyncio.run(debug_token_tracking()) 