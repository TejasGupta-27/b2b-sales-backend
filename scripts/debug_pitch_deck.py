import sys
import os
import json
import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import required services
from services.pitch_deck_service import PitchDeckService
from services.pdf_generator import PDFGenerator
from config import settings

async def test_japanese_quotation():
    """Test generating a pitch deck and PDF for a Japanese quotation"""
    
    # 1. Create a test Japanese quotation
    ja_quote = {
        "quote_number": "Q-20250710-001",
        "title": "16GB DDR5メモリモジュール見積もり",
        "company_tagline": "最先端のメモリソリューションでビジネスを加速",
        "customer_info": {
            "company_name": "テスト株式会社",
            "contact_name": "山田太郎",
            "email": "yamada@test.co.jp",
            "address": "東京都千代田区1-1-1"
        },
        "business_context": "お客様は新しいエンジニアリングワークステーション向けに高速メモリを必要としています。",
        "line_items": [
            {
                "name": "Corsair Vengeance 16GB DDR5-6000",
                "category": "memory",
                "description": "高速DDR5メモリモジュール",
                "specs": {"容量": "16GB", "速度": "6000MHz", "レイテンシ": "CL36"},
                "quantity": 2,
                "unit_price": 15000.00,
                "warranty": "永久保証",
                "support": "標準サポート"
            }
        ],
        "financials": {
            "subtotal": 30000.00,
            "tax": 3000.00,
            "total": 33000.00,
            "currency": "JPY"
        },
        "terms_and_conditions": "お支払いは請求書発行後30日以内にお願いします。",
        "implementation_notes": "特別な取り付け手順はありません。",
        "next_steps": "ご承認いただけましたら、発注書をお送りください。",
        "valid_until": "2025-08-10",
        "created_at": "2025-07-10",
        "language": "ja",
        "language_detection": {"language": "ja", "method": "explicit", "confidence": 1.0}
    }
    
    # 2. Test pitch deck generation
    logger.info("🔍 Testing PitchDeckService with Japanese quotation")
    pitch_service = PitchDeckService()
    
    # Debug: Check if the service correctly initialized
    logger.info(f"✅ PitchDeckService initialized with client_configured={getattr(pitch_service, 'client_configured', 'undefined')}")
    logger.info(f"✅ Using fonts - Title: {pitch_service.title_font}, Body: {pitch_service.body_font}")
    
    # Convert dictionary to JSON string for the extract_ppt_structure method
    quote_json = json.dumps(ja_quote, ensure_ascii=False)
    
    # Debug: Test Japanese text detection
    sample_texts = [
        "English text only",
        "Mixed English and 日本語",
        "完全な日本語テキスト",
        ja_quote["title"]
    ]
    for text in sample_texts:
        is_japanese = pitch_service._detect_japanese_text(text)
        logger.info(f"Japanese detection for '{text}': {is_japanese}")
    
    # 3. Generate the structure with explicit Japanese language
    logger.info("📊 Generating deck structure for Japanese quotation")
    deck_structure = await pitch_service.extract_ppt_structure(
        quotation=quote_json, 
        language="ja",
        include_comparison_table=True
    )
    
    # Debug: Check the structure
    logger.info(f"🔍 Deck structure type: {type(deck_structure)}")
    if isinstance(deck_structure, dict):
        logger.info(f"🔍 Deck structure keys: {list(deck_structure.keys())}")
        logger.info(f"🔍 Resolved language: {deck_structure.get('resolved_language', 'not found')}")
        if 'slides' in deck_structure:
            logger.info(f"🔍 Number of slides: {len(deck_structure['slides'])}")
            logger.info(f"🔍 First slide title: {deck_structure['slides'][0]['title'] if deck_structure['slides'] else 'No slides'}")
    
    # 4. Generate the actual PowerPoint
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_outputs")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "test_japanese_deck.pptx")
    
    # Create a list of similar products for the comparison table
    similar_products = [
        {
            "name": "Corsair Vengeance 16GB DDR5-6000",
            "key_features": "高速DDR5、CL36レイテンシ",
            "price": 15000.00,
            "vendor": "Corsair"
        },
        {
            "name": "Kingston FURY Beast 16GB DDR5-6000",
            "key_features": "高性能メモリ、低レイテンシ",
            "price": 14500.00,
            "vendor": "Kingston"
        },
        {
            "name": "G.Skill Trident Z5 16GB DDR5-6000",
            "key_features": "RGBライティング、安定性",
            "price": 16000.00,
            "vendor": "G.Skill"
        }
    ]
    
    logger.info(f"📊 Generating PowerPoint to {output_path}")
    result_path = await pitch_service.generate_ppt(
        data=deck_structure,
        output_path=output_path,
        similar_products=similar_products,
        product_name="memory"
    )
    
    logger.info(f"✅ PowerPoint generated: {result_path}")
    
    # 5. Test PDF generation
    logger.info("📄 Testing PDF generation with Japanese quotation")
    pdf_generator = PDFGenerator()
    
    # Check language support
    supported_langs = pdf_generator.get_supported_languages()
    logger.info(f"📄 Supported languages: {supported_langs}")
    
    # Update styles for Japanese
    pdf_generator.update_styles_for_language("ja")
    
    # Generate PDF
    pdf_path = os.path.join(output_dir, "test_japanese_quote.pdf")
    result_pdf_path = pdf_generator.save_pdf_to_file(ja_quote, pdf_path)
    
    logger.info(f"✅ PDF generated: {result_pdf_path}")
    
    return {
        "deck_path": result_path,
        "pdf_path": result_pdf_path,
        "deck_structure": deck_structure
    }

async def main():
    """Main entry point"""
    try:
        logger.info("🚀 Starting Japanese quotation test")
        results = await test_japanese_quotation()
        logger.info("✅ Test completed successfully")
        logger.info(f"🔍 Generated files:")
        logger.info(f"   PowerPoint: {results['deck_path']}")
        logger.info(f"   PDF: {results['pdf_path']}")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
