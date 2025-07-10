#!/usr/bin/env python3
"""
Test script focusing on language detection order and style updates in PDF generation
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pdf_language_order_test")

# Add the project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the PDF generator
try:
    from services.pdf_generator import PDFGenerator
    logger.info("✅ Successfully imported PDFGenerator")
except Exception as e:
    logger.error(f"❌ Failed to import PDFGenerator: {e}")
    sys.exit(1)

def test_language_detection_order():
    """Test language detection order and style updates in PDF generation"""
    
    logger.info("🔍 Testing language detection order in save_pdf_to_file...")
    
    # Create PDF generator
    pdf_generator = PDFGenerator()
    
    # Test data with Japanese content but without explicit language setting
    implicit_japanese_quote = {
        "quote_number": "Q-20250711-002-JP",
        "title": "日本語の暗黙的な検出テスト",
        "company_tagline": "言語検出順序の確認",
        "customer_info": {
            "company_name": "テスト株式会社",
            "contact_name": "山田花子",
            "email": "yamada@example.jp",
            "phone": "03-9876-5432",
            "address": "東京都新宿区1-2-3"
        },
        "business_context": "これは日本語の暗黙的な検出をテストするためのデータです。言語が正しく検出され、適切なフォントが選択されるかを確認します。",
        "line_items": [
            {
                "name": "言語検出テスト商品",
                "description": "これは日本語テキストのフォント選択をテストするための商品です。長めの説明文を入れて、テキストの折り返しやフォーマットも確認します。",
                "quantity": 1,
                "unit_price": 10000.0,
                "total_price": 10000.0,
                "category": "テスト"
            }
        ],
        "financials": {
            "subtotal": 10000.0,
            "tax_rate": 0.10,
            "tax_amount": 1000.0,
            "total": 11000.0,
            "currency": "JPY"
        },
        "terms_and_conditions": [
            "これはテスト用の利用規約です。",
            "日本語フォントが正しく適用されているか確認してください。"
        ],
        "implementation_notes": [
            "言語検出の順序が重要です。",
            "スタイル更新前に言語が設定されていることを確認します。"
        ],
        "next_steps": [
            "テスト結果を確認してください。",
            "必要に応じてコードを修正してください。"
        ],
        "valid_until": "2025-08-11",
        "created_at": "2025-07-11"
    }
    
    # Create test output directory
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Test without explicit language setting (should detect Japanese)
    logger.info("🧪 Testing implicit Japanese language detection...")
    
    # Capture the detected language before saving
    detected_language = pdf_generator._detect_quote_language(implicit_japanese_quote)
    logger.info(f"🌐 Pre-detected language: {detected_language}")
    
    # Generate PDF file
    filename = "language_order_test.pdf"
    pdf_path = pdf_generator.save_pdf_to_file(
        implicit_japanese_quote,
        filename
    )
    
    if pdf_path and os.path.exists(pdf_path):
        file_size = os.path.getsize(pdf_path)
        logger.info(f"✅ PDF generated successfully!")
        logger.info(f"   File: {pdf_path}")
        logger.info(f"   Size: {file_size:,} bytes")
        
        # Verify the language was updated in the quote data
        if implicit_japanese_quote.get('language') == detected_language:
            logger.info("✅ Language correctly updated in quote data")
        else:
            logger.error(f"❌ Language not updated correctly. Expected: {detected_language}, Got: {implicit_japanese_quote.get('language')}")
    else:
        logger.error("❌ PDF generation failed")

if __name__ == "__main__":
    test_language_detection_order()
