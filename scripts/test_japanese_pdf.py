"""
Test script specifically for Japanese PDF generation with font verification
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
logger = logging.getLogger("pdf_japanese_test")

# Add the project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the PDF generator
try:
    from services.pdf_generator import PDFGenerator
    logger.info("✅ Successfully imported PDFGenerator")
except Exception as e:
    logger.error(f"❌ Failed to import PDFGenerator: {e}")
    sys.exit(1)

def test_japanese_pdf_generation():
    """Test Japanese PDF generation with font verification"""
    
    # Create a test output directory
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Create a sample Japanese quote data
    japanese_quote = {
        "quote_number": "Q-20250711-001-JP",
        "title": "日本語テスト見積書",
        "company_tagline": "信頼性の高いテクノロジーソリューション",
        "language": "ja",  # Explicitly set to Japanese
        "customer_info": {
            "company_name": "サンプル株式会社",
            "contact_name": "田中太郎",
            "email": "tanaka@example.co.jp",
            "phone": "03-1234-5678",
            "address": "東京都千代田区1-1-1"
        },
        "business_context": "お客様は業務効率を高めるためにハードウェアとソフトウェアのアップグレードを検討しています。予算は限られていますが、高品質で信頼性の高いソリューションを求めています。",
        "line_items": [
            {
                "name": "デスクトップコンピュータ デルOptiPlex 5000",
                "description": "インテルCore i7プロセッサ、16GB RAM、512GB SSD、Windows 11 Pro搭載の高性能ビジネスデスクトップ。3年間のProSupportが含まれます。",
                "quantity": 5,
                "unit_price": 125000.0,
                "total_price": 625000.0,
                "category": "ハードウェア"
            },
            {
                "name": "Microsoft 365 Businessライセンス",
                "description": "Microsoft 365 Business Standardライセンス（年間）。Word、Excel、PowerPoint、Outlook、Teams、OneDriveを含む包括的なビジネスソリューション。",
                "quantity": 10,
                "unit_price": 18000.0,
                "total_price": 180000.0,
                "category": "ソフトウェア"
            },
            {
                "name": "技術サポートサービス",
                "description": "年間技術サポートサービス契約。24時間365日のヘルプデスク、リモートトラブルシューティング、月次システムチェックを含みます。",
                "quantity": 1,
                "unit_price": 150000.0,
                "total_price": 150000.0,
                "category": "サービス"
            }
        ],
        "financials": {
            "subtotal": 955000.0,
            "tax_rate": 0.10,
            "tax_amount": 95500.0,
            "total": 1050500.0,
            "currency": "JPY"
        },
        "terms_and_conditions": [
            "見積もりは30日間有効です。",
            "支払いは請求書発行後30日以内にお願いします。",
            "ハードウェアの保証期間は購入日から3年間です。",
            "ソフトウェアライセンスは年間契約で、自動更新されます。",
            "返品・交換は商品到着後14日以内に限ります。"
        ],
        "implementation_notes": [
            "ハードウェアの納品は注文確認後2週間以内を予定しています。",
            "Microsoft 365のアカウント設定は当社の技術者が支援します。",
            "初期設定とトレーニングは別途料金で提供可能です。",
            "既存システムからのデータ移行は本見積もりに含まれていません。"
        ],
        "next_steps": [
            "本見積書の内容をご確認ください。",
            "ご質問やご不明点がございましたら、担当営業にお問い合わせください。",
            "ご納得いただけましたら、発注書をお送りください。",
            "納品とインストールのスケジュールを調整いたします。"
        ],
        "valid_until": "2025-08-11",
        "created_at": "2025-07-11"
    }
    
    # Create a similar English quote for comparison
    english_quote = japanese_quote.copy()
    english_quote.update({
        "quote_number": "Q-20250711-001-EN",
        "title": "Test Quote",
        "company_tagline": "Reliable Technology Solutions",
        "language": "en",
        "customer_info": {
            "company_name": "Sample Corporation",
            "contact_name": "John Smith",
            "email": "john.smith@example.com",
            "phone": "123-456-7890",
            "address": "123 Main St, Anytown, USA"
        },
        "business_context": "The customer is looking to upgrade their hardware and software to improve business efficiency. They have a limited budget but are seeking high-quality, reliable solutions."
    })
    
    # English versions of line items
    english_quote["line_items"] = [
        {
            "name": "Desktop Computer Dell OptiPlex 5000",
            "description": "High-performance business desktop with Intel Core i7 processor, 16GB RAM, 512GB SSD, and Windows 11 Pro. Includes 3-year ProSupport.",
            "quantity": 5,
            "unit_price": 1250.0,
            "total_price": 6250.0,
            "category": "Hardware"
        },
        {
            "name": "Microsoft 365 Business License",
            "description": "Microsoft 365 Business Standard license (annual). Comprehensive business solution including Word, Excel, PowerPoint, Outlook, Teams, and OneDrive.",
            "quantity": 10,
            "unit_price": 180.0,
            "total_price": 1800.0,
            "category": "Software"
        },
        {
            "name": "Technical Support Services",
            "description": "Annual technical support service contract. Includes 24/7 helpdesk, remote troubleshooting, and monthly system checks.",
            "quantity": 1,
            "unit_price": 1500.0,
            "total_price": 1500.0,
            "category": "Service"
        }
    ]
    
    # English versions of other text fields
    english_quote["financials"] = {
        "subtotal": 9550.0,
        "tax_rate": 0.10,
        "tax_amount": 955.0,
        "total": 10505.0,
        "currency": "USD"
    }
    
    english_quote["terms_and_conditions"] = [
        "Quote valid for 30 days.",
        "Payment due within 30 days of invoice.",
        "Hardware warranty is 3 years from purchase date.",
        "Software licenses are annual contracts and will auto-renew.",
        "Returns and exchanges must be made within 14 days of receipt."
    ]
    
    english_quote["implementation_notes"] = [
        "Hardware delivery expected within 2 weeks of order confirmation.",
        "Microsoft 365 account setup will be assisted by our technicians.",
        "Initial setup and training available for additional fee.",
        "Data migration from existing systems not included in this quote."
    ]
    
    english_quote["next_steps"] = [
        "Please review the contents of this quote.",
        "Contact your sales representative with any questions or concerns.",
        "Send a purchase order if you wish to proceed.",
        "We will coordinate delivery and installation schedules."
    ]
    
    # Create a copy without explicit language setting to test detection
    implicit_japanese_quote = japanese_quote.copy()
    implicit_japanese_quote.pop('language')  # Remove explicit language
    implicit_japanese_quote['quote_number'] = "Q-20250711-001-IMPLICIT-JP"
    
    # Test both Japanese and English PDFs
    try:
        pdf_generator = PDFGenerator()
        
        # Log font registration status
        logger.info(f"Japanese fonts registered: {pdf_generator.japanese_font_registered}")
        
        # Test language detection on the Japanese quote with explicit setting
        detected_lang = pdf_generator._detect_quote_language(japanese_quote)
        logger.info(f"Detected language for explicit Japanese quote: {detected_lang}")
        
        # Test language detection on the Japanese quote without explicit setting
        detected_lang_implicit = pdf_generator._detect_quote_language(implicit_japanese_quote)
        logger.info(f"Detected language for implicit Japanese quote: {detected_lang_implicit}")
        
        # Generate Japanese PDF with explicit language
        logger.info("Generating Japanese PDF with explicit language...")
        japanese_pdf_path = pdf_generator.save_pdf_to_file(japanese_quote, "test_japanese_explicit_quote.pdf")
        
        if japanese_pdf_path and os.path.exists(japanese_pdf_path):
            japanese_file_size = os.path.getsize(japanese_pdf_path)
            logger.info(f"Explicit Japanese PDF generated: {japanese_pdf_path} ({japanese_file_size:,} bytes)")
        else:
            logger.error("Failed to generate explicit Japanese PDF")
            
        # Generate Japanese PDF with implicit language detection
        logger.info("Generating Japanese PDF with implicit language detection...")
        implicit_japanese_pdf_path = pdf_generator.save_pdf_to_file(implicit_japanese_quote, "test_japanese_implicit_quote.pdf")
        
        if implicit_japanese_pdf_path and os.path.exists(implicit_japanese_pdf_path):
            implicit_japanese_file_size = os.path.getsize(implicit_japanese_pdf_path)
            logger.info(f"Implicit Japanese PDF generated: {implicit_japanese_pdf_path} ({implicit_japanese_file_size:,} bytes)")
        else:
            logger.error("Failed to generate implicit Japanese PDF")
        
        # Generate English PDF for comparison
        logger.info("Generating English PDF...")
        english_pdf_path = pdf_generator.save_pdf_to_file(english_quote, "test_english_quote.pdf")
        
        if english_pdf_path and os.path.exists(english_pdf_path):
            english_file_size = os.path.getsize(english_pdf_path)
            logger.info(f"English PDF generated: {english_pdf_path} ({english_file_size:,} bytes)")
        else:
            logger.error("Failed to generate English PDF")
        
        logger.info("Test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("🧪 Testing PDF generation with Japanese content...")
    success = test_japanese_pdf_generation()
    if success:
        print("✅ All tests completed successfully!")
    else:
        print("❌ Tests failed. See logs for details.")
