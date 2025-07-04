#!/usr/bin/env python3
"""
Quick test script to verify the fixes for similar products and language consistency
"""

import asyncio
import sys
import os

# Add the project path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_similar_products_fix():
    """Test that similar products are always available for comparison table"""
    
    try:
        print("🔧 Testing similar products fix...")
        
        from ai_services.simple_conversational_agent import SimpleConversationalAgent
        from ai_services.base import AIMessage
        
        # Mock base provider
        class MockProvider:
            def is_configured(self):
                return True
                
            async def generate_response(self, messages, **kwargs):
                from ai_services.base import AIResponse
                return AIResponse(
                    content="RTX 4070のGPUについて見積もりを作成いたします。",
                    model="mock",
                    provider="mock",
                    usage={}
                )
            
            async def generate_structured_response(self, messages, model_class):
                # Mock quote data
                return model_class(
                    quote_number="Q-20240627-001",
                    title="RTX 4070 GPU Quote",
                    company_tagline="High-Performance Graphics Solutions",
                    customer_info={
                        "company_name": "テスト株式会社",
                        "contact_name": "田中太郎", 
                        "email": "tanaka@test.co.jp"
                    },
                    business_context="High-performance GPUs for gaming and AI workloads",
                    line_items=[
                        {
                            "name": "NVIDIA RTX 4070",
                            "description": "High-performance graphics card for gaming and AI",
                            "quantity": 100,
                            "unit_price": 599.0,
                            "total_price": 59900.0,
                            "category": "Graphics Cards"
                        }
                    ],
                    financials={
                        "subtotal": 59900.0,
                        "tax_rate": 0.08,
                        "tax_amount": 4792.0,
                        "total": 64692.0,
                        "currency": "USD"
                    },
                    terms_and_conditions=["Standard warranty applies"],
                    implementation_notes=["Installation support available"],
                    next_steps=["Review quote and confirm order"],
                    valid_until="2024-07-27",
                    created_at="2024-06-27",
                    language="ja"
                )
        
        # Create agent with Japanese language
        agent = SimpleConversationalAgent(MockProvider(), language="ja")
        
        # Test quote generation (which triggers pitch deck generation)
        print("📝 Testing quote generation with fallback similar products...")
        
        quote_request = {
            'conversation_messages': [
                AIMessage(role="user", content="RTX 4070のGPUの見積もりをお願いします。")
            ],
            'customer_context': {
                'company_name': 'テスト株式会社'
            },
            'product_data': None  # Force fallback logic
        }
        
        quote = await agent.generate_quote(quote_request)
        
        if quote:
            similar_products_count = quote.get('similar_products_count', 0)
            print(f"✅ Quote generated!")
            print(f"   Similar products count: {similar_products_count}")
            print(f"   Pitch deck generated: {quote.get('pitch_deck_generated', False)}")
            
            if similar_products_count > 0:
                print("✅ Similar products fix working - fallback products created!")
                return True
            else:
                print("❌ Similar products still 0 - fix not working properly")
                return False
        else:
            print("❌ Quote generation failed")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_language_consistency():
    """Test that Japanese responses are properly generated"""
    
    try:
        print("🔧 Testing language consistency...")
        
        from ai_services.simple_conversational_agent import SimpleConversationalAgent
        from ai_services.base import AIMessage, AIResponse
        
        # Mock provider that responds in Japanese when properly instructed
        class MockJapaneseProvider:
            def is_configured(self):
                return True
                
            async def generate_response(self, messages, **kwargs):
                # Check if Japanese instruction is in system prompt
                system_message = next((msg for msg in messages if msg.role == "system"), None)
                if system_message and "日本語で回答してください" in system_message.content:
                    content = "RTX 4070のGPUについて詳細な見積もりを作成いたします。お客様のご要望に最適なソリューションをご提案いたします。"
                else:
                    content = "I'd be happy to help you with a quote for RTX 4070 GPUs."
                
                return AIResponse(
                    content=content,
                    model="mock",
                    provider="mock",
                    usage={}
                )
        
        # Create agent with Japanese language
        agent = SimpleConversationalAgent(MockJapaneseProvider(), language="ja")
        
        # Test response generation
        print("📝 Testing Japanese response generation...")
        
        test_messages = [
            AIMessage(role="user", content="RTX 4070のGPUについて教えてください。")
        ]
        
        response = await agent.generate_response(test_messages)
        
        print(f"Response content: {response.content}")
        
        # Check if response contains Japanese characters
        has_japanese = any(ord(char) >= 0x3000 for char in response.content)
        
        if has_japanese:
            print("✅ Language consistency fix working - response in Japanese!")
            return True
        else:
            print("❌ Language consistency fix not working - response still in English")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def main():
    print("🔧 Testing fixes for similar products and language consistency...")
    print("="*60)
    
    # Test 1: Similar products fix
    print("\nTEST 1: SIMILAR PRODUCTS FIX")
    print("-" * 40)
    similar_products_ok = await test_similar_products_fix()
    
    # Test 2: Language consistency fix  
    print("\nTEST 2: LANGUAGE CONSISTENCY FIX")
    print("-" * 40)
    language_ok = await test_language_consistency()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY:")
    print(f"✅ Similar products fix: {'PASS' if similar_products_ok else 'FAIL'}")
    print(f"✅ Language consistency fix: {'PASS' if language_ok else 'FAIL'}")
    
    if similar_products_ok and language_ok:
        print("\n🎉 All fixes are working correctly!")
        return True
    else:
        print("\n❌ Some fixes still need work")
        return False

if __name__ == "__main__":
    asyncio.run(main())
