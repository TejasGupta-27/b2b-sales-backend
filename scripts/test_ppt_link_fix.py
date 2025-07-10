#!/usr/bin/env python3
"""
Test script to verify that PPT download links are properly included in Japanese responses
{
b2b-sales-backend-1  |   "quote_number": "Q-20240627-001",
b2b-sales-backend-1  |   "title": "Intel Core i7 Processor and Complementary Technology Solutions Quote",
b2b-sales-backend-1  |   "company_tagline": "Innovative Technology Solutions for Your Business",
b2b-sales-backend-1  |   "customer_info": {
b2b-sales-backend-1  |     "company_name": "Unknown",
b2b-sales-backend-1  |     "contact_name": "Unknown",
b2b-sales-backend-1  |     "email": "unknown@example.com",
b2b-sales-backend-1  |     "phone": null,
b2b-sales-backend-1  |     "address": null
b2b-sales-backend-1  |   },
b2b-sales-backend-1  |   "business_context": "The customer requested a quote for the latest Intel Core i7 processor. To provide a comprehensive technology solution, this quote includes the Intel Core i7 processor along with complementary products such as compatible motherboards, memory modules, and SSD storage to ensure optimal performance and compatibility for computing needs.",
b2b-sales-backend-1  |   "line_items": [
b2b-sales-backend-1  |     {
b2b-sales-backend-1  |       "name": "Intel Core i7-13700K Processor",
b2b-sales-backend-1  |       "description": "Latest generation Intel Core i7 processor with 16 cores and 24 threads, suitable for high-performance computing and multitasking.",
b2b-sales-backend-1  |       "quantity": 1,
b2b-sales-backend-1  |       "unit_price": 420.0,
b2b-sales-backend-1  |       "total_price": 420.0,
b2b-sales-backend-1  |       "category": "Hardware"
b2b-sales-backend-1  |     },
b2b-sales-backend-1  |     {
b2b-sales-backend-1  |       "name": "ASUS ROG Strix Z790-E Gaming Motherboard",
b2b-sales-backend-1  |       "description": "High-end motherboard compatible with Intel 13th Gen processors, featuring DDR5 support, PCIe 5.0, and advanced cooling solutions.",
b2b-sales-backend-1  |       "quantity": 1,
b2b-sales-backend-1  |       "unit_price": 400.0,
b2b-sales-backend-1  |       "total_price": 400.0,
b2b-sales-backend-1  |       "category": "Hardware"
b2b-sales-backend-1  |     },
b2b-sales-backend-1  |     {
b2b-sales-backend-1  |       "name": "Corsair Vengeance DDR5 32GB (2x16GB) 5600MHz RAM",
b2b-sales-backend-1  |       "description": "High-speed DDR5 memory kit optimized for Intel 13th Gen processors, ensuring smooth multitasking and gaming performance.",
b2b-sales-backend-1  |       "quantity": 1,
b2b-sales-backend-1  |       "unit_price": 180.0,
b2b-sales-backend-1  |       "total_price": 180.0,
b2b-sales-backend-1  |       "category": "Hardware"
b2b-sales-backend-1  |     },
b2b-sales-backend-1  |     {
b2b-sales-backend-1  |       "name": "Samsung 980 Pro 1TB NVMe SSD",
b2b-sales-backend-1  |       "description": "High-performance NVMe SSD for fast boot times and quick data access, enhancing overall system responsiveness.",
b2b-sales-backend-1  |       "quantity": 1,
b2b-sales-backend-1  |       "unit_price": 150.0,
b2b-sales-backend-1  |       "total_price": 150.0,
b2b-sales-backend-1  |       "category": "Hardware"
b2b-sales-backend-1  |     }
b2b-sales-backend-1  |   ],
b2b-sales-backend-1  |   "financials": {
b2b-sales-backend-1  |     "subtotal": 1150.0,
b2b-sales-backend-1  |     "tax_rate": 0.08,
b2b-sales-backend-1  |     "tax_amount": 92.0,
b2b-sales-backend-1  |     "total": 1242.0,
b2b-sales-backend-1  |     "currency": "USD"
b2b-sales-backend-1  |   },
b2b-sales-backend-1  |   "terms_and_conditions": [
b2b-sales-backend-1  |     "Prices are valid for 30 days from the quote date.",
b2b-sales-backend-1  |     "Payment terms: 50% deposit upon order confirmation, balance due upon delivery.",
b2b-sales-backend-1  |     "Warranty: All hardware products come with a manufacturer warranty of at least 1 year.",
b2b-sales-backend-1  |     "Delivery lead time is approximately 7-10 business days after order confirmation.",
b2b-sales-backend-1  |     "Returns accepted within 14 days of delivery if products are unopened and in original packaging."
b2b-sales-backend-1  |   ],
b2b-sales-backend-1  |   "implementation_notes": [
b2b-sales-backend-1  |     "Ensure compatibility of all components before installation.",
b2b-sales-backend-1  |     "Installation services can be provided upon request at an additional cost.",
b2b-sales-backend-1  |     "System testing and benchmarking recommended after assembly to verify performance."
b2b-sales-backend-1  |   ],
b2b-sales-backend-1  |   "next_steps": [
b2b-sales-backend-1  |     "Review the quote and confirm acceptance via email.",
b2b-sales-backend-1  |     "Provide any additional requirements or customization requests.",
b2b-sales-backend-1  |     "Schedule delivery and installation dates upon order confirmation."
b2b-sales-backend-1  |   ],
b2b-sales-backend-1  |   "valid_until": "2024-07-27",
b2b-sales-backend-1  |   "created_at": "2024-06-27",
b2b-sales-backend-1  |   "language": "en",
b2b-sales-backend-1  |   "language_detection": {
b2b-sales-backend-1  |     "language": "en",
b2b-sales-backend-1  |     "method": "explicit",
b2b-sales-backend-1  |     "confidence": 1.0,
b2b-sales-backend-1  |     "detected_languages": [],
b2b-sales-backend-1  |     "fallback_used": false
b2b-sales-backend-1  |   },
b2b-sales-backend-1  |   "quote_id": "001",
b2b-sales-backend-1  |   "generation_method": "pydantic_structured_internationalized",
b2b-sales-backend-1  |   "data_source": "conversation_only"
b2b-sales-backend-1  | }
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_services.quote_generation_agent import QuoteGenerationAgent
from services.localisation import get_translation

async def test_ppt_link_in_japanese_response():
    """Test that PPT download link is included in Japanese quote responses"""
    
    try:
        print("🔧 Testing PPT download link in Japanese response...")
        
        # Create a mock quote with both PDF and PPT available
        test_quote = {
            'quote_number': 'TEST-001',
            'financials': {
                'subtotal': 599.0,
                'tax_amount': 47.92,
                'total': 646.92,
                'currency': 'USD'
            },
            'valid_until': '2024-07-27',
            'pdf_generated': True,
            'pdf_url': '/api/quotes/download-pdf/TEST-001',
            'pitch_deck_generated': True,
            'pitch_deck_url': '/api/quotes/download-pitch-deck/TEST-001'
        }
        
        # Create mock provider
        class MockProvider:
            def is_configured(self):
                return True
                
            async def generate_response(self, messages, **kwargs):
                return None
        
        # Create quote agent
        quote_agent = QuoteGenerationAgent(MockProvider(), language="ja")
        
        print("📝 Testing quote response formatting...")
        
        # Format the quote response
        formatted_response = quote_agent.format_quote_response(test_quote, language="ja")
        
        print("Response content:")
        print("-" * 50)
        print(formatted_response)
        print("-" * 50)
        
        # Check if both PDF and PPT links are present
        has_pdf_link = "見積PDFをダウンロード" in formatted_response
        has_ppt_link = "提案スライドをダウンロード" in formatted_response
        has_pdf_url = "/api/quotes/download-pdf/TEST-001" in formatted_response
        has_ppt_url = "/api/quotes/download-pitch-deck/TEST-001" in formatted_response
        
        print(f"\n✅ Analysis:")
        print(f"   PDF link text present: {has_pdf_link}")
        print(f"   PPT link text present: {has_ppt_link}")
        print(f"   PDF URL present: {has_pdf_url}")
        print(f"   PPT URL present: {has_ppt_url}")
        
        # Check next steps - should include PPT-related step
        ppt_step_present = "提案資料をご覧ください" in formatted_response
        print(f"   PPT step in next steps: {ppt_step_present}")
        
        # Test success if both links are present
        if has_pdf_link and has_ppt_link and has_pdf_url and has_ppt_url and ppt_step_present:
            print("\n✅ PPT link fix working - both PDF and PPT links present in Japanese response!")
            return True
        else:
            print("\n❌ PPT link fix not working - missing links in Japanese response")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_ppt_link_in_english_response():
    """Test that PPT download link is included in English quote responses (for comparison)"""
    
    try:
        print("\n🔧 Testing PPT download link in English response (for comparison)...")
        
        # Create a mock quote with both PDF and PPT available
        test_quote = {
            'quote_number': 'TEST-001',
            'financials': {
                'subtotal': 599.0,
                'tax_amount': 47.92,
                'total': 646.92,
                'currency': 'USD'
            },
            'valid_until': '2024-07-27',
            'pdf_generated': True,
            'pdf_url': '/api/quotes/download-pdf/TEST-001',
            'pitch_deck_generated': True,
            'pitch_deck_url': '/api/quotes/download-pitch-deck/TEST-001'
        }
        
        # Create mock provider
        class MockProvider:
            def is_configured(self):
                return True
                
            async def generate_response(self, messages, **kwargs):
                return None
        
        # Create quote agent
        quote_agent = QuoteGenerationAgent(MockProvider(), language="en")
        
        print("📝 Testing quote response formatting...")
        
        # Format the quote response
        formatted_response = quote_agent.format_quote_response(test_quote, language="en")
        
        print("Response content:")
        print("-" * 50)
        print(formatted_response)
        print("-" * 50)
        
        # Check if both PDF and PPT links are present
        has_pdf_link = "Download Complete Quote PDF" in formatted_response
        has_ppt_link = "Download Pitch Deck" in formatted_response
        has_pdf_url = "/api/quotes/download-pdf/TEST-001" in formatted_response
        has_ppt_url = "/api/quotes/download-pitch-deck/TEST-001" in formatted_response
        
        print(f"\n✅ Analysis:")
        print(f"   PDF link text present: {has_pdf_link}")
        print(f"   PPT link text present: {has_ppt_link}")
        print(f"   PDF URL present: {has_pdf_url}")
        print(f"   PPT URL present: {has_ppt_url}")
        
        # Check next steps - should include PPT-related step
        ppt_step_present = "Check out the pitch deck" in formatted_response
        print(f"   PPT step in next steps: {ppt_step_present}")
        
        # Test success if both links are present
        if has_pdf_link and has_ppt_link and has_pdf_url and has_ppt_url and ppt_step_present:
            print("\n✅ English response includes both PDF and PPT links!")
            return True
        else:
            print("\n❌ English response missing links")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_translations():
    """Test that translations are properly loaded."""
    print("\n🔧 Testing translation loading...")

    # Test Japanese translations
    ja_translations = get_translation("quote_prompt", "ja")
    print(f"Japanese PPT ready text: {ja_translations.get('ppt_ready', 'MISSING')}")

    # Test English translations
    en_translations = get_translation("quote_prompt", "en")
    print(f"English PPT ready text: {en_translations.get('ppt_ready', 'MISSING')}")

    return 'ppt_ready' in ja_translations and 'ppt_ready' in en_translations

async def main():
    print("🔧 Testing PPT download link fix...")
    print("="*60)
    
    # Test 1: Translation loading
    print("\nTEST 1: TRANSLATION LOADING")
    print("-" * 40)
    translations_ok = await test_translations()
    
    # Test 2: English response (reference)
    print("\nTEST 2: ENGLISH RESPONSE (REFERENCE)")
    print("-" * 40)
    english_ok = await test_ppt_link_in_english_response()
    
    # Test 3: Japanese response
    print("\nTEST 3: JAPANESE RESPONSE")
    print("-" * 40)
    japanese_ok = await test_ppt_link_in_japanese_response()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY:")
    print(f"✅ Translations loaded: {'PASS' if translations_ok else 'FAIL'}")
    print(f"✅ English response: {'PASS' if english_ok else 'FAIL'}")
    print(f"✅ Japanese response: {'PASS' if japanese_ok else 'FAIL'}")
    
    if translations_ok and english_ok and japanese_ok:
        print("\n🎉 PPT link fix is working correctly!")
        return True
    else:
        print("\n❌ PPT link fix still needs work")
        return False

if __name__ == "__main__":
    asyncio.run(main())
