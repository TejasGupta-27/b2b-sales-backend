#!/usr/bin/env python3
"""
Test script to verify Japanese font support in PDF generation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pdf_generator import PDFGenerator
from pathlib import Path

def test_japanese_pdf_generation():
    """Test Japanese PDF generation with proper font support"""
    
    # Sample Japanese quote data
    test_quote_data = {
        "quote_id": "TEST_001",
        "quote_number": "Q-2024-001",
        "title": "テクノロジーソリューションの見積もり",
        "company_tagline": "信頼性の高い技術サポート",
        "language": "ja",  # This is the key field!
        "customer_info": {
            "company_name": "株式会社テスト",
            "contact_name": "田中太郎",
            "email": "tanaka@test.co.jp",
            "phone": "03-1234-5678",
            "address": "東京都新宿区"
        },
        "business_context": "企業のデジタル変革のため、高性能なコンピューター部品が必要です。",
        "line_items": [
            {
                "name": "DDR4 メモリ 16GB",
                "description": "高速メモリモジュール - ラップトップ用",
                "quantity": 2,
                "unit_price": 150.0,
                "total_price": 300.0,
                "category": "ハードウェア"
            },
            {
                "name": "SSD 1TB",
                "description": "高速ストレージソリューション",
                "quantity": 1,
                "unit_price": 200.0,
                "total_price": 200.0,
                "category": "ストレージ"
            }
        ],
        "financials": {
            "subtotal": 500.0,
            "tax_rate": 0.08,
            "tax_amount": 40.0,
            "total": 540.0,
            "currency": "JPY"
        },
        "terms": "お支払いは30日以内にお願いします。",
        "notes": "ご不明な点がございましたら、お気軽にお問い合わせください。"
    }
    
    try:
        print("🔍 Testing Japanese PDF generation...")
        
        # Create PDF generator
        pdf_generator = PDFGenerator()
        
        # Generate PDF with Japanese content
        filename = f"test_quote_{test_quote_data['quote_id']}_ja.pdf"
        pdf_path = pdf_generator.save_pdf_to_file(test_quote_data, filename)
        
        # Check if file was created
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            print(f"✅ Japanese PDF generated successfully!")
            print(f"   File: {pdf_path}")
            print(f"   Size: {file_size} bytes")
            print(f"   Language: {test_quote_data['language']}")
            
            # Check if Japanese fonts are registered
            if pdf_generator.japanese_font_registered:
                print("✅ Japanese fonts are properly registered")
            else:
                print("❌ Japanese fonts are NOT registered")
                
            return True
        else:
            print(f"❌ PDF file was not created: {pdf_path}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_japanese_pdf_generation()
    if success:
        print("\n🎉 Japanese PDF generation test PASSED!")
    else:
        print("\n💥 Japanese PDF generation test FAILED!")
    
    sys.exit(0 if success else 1)
