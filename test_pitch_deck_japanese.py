"""
Test script for pitch deck generation with Japanese content.
This script tests language detection, PowerPoint generation, and PDF handling
with Japanese text.
"""
import asyncio
import logging
import os
import sys
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_pitch_deck_japanese")

# Import the PitchDeckService
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.pitch_deck_service import PitchDeckService

# Sample Japanese quotation
SAMPLE_JAPANESE_QUOTATION = """
見積書

株式会社大塚商事
東京都千代田区1-1-1

お客様：山田太郎様
日付：2025年7月10日

商品名：デルXPS 15ラップトップ
モデル：XPS 15 9530 (2025)
数量：10

仕様：
- CPU: Intel Core i9-13900H
- RAM: 64GB DDR5
- ストレージ: 2TB SSD
- グラフィックス: NVIDIA GeForce RTX 4070
- ディスプレイ: 15.6インチ 4K UHD+ タッチスクリーン
- OS: Windows 11 Pro

価格：
単価: ¥275,000
合計: ¥2,750,000 (税抜)
消費税 (10%): ¥275,000
総額: ¥3,025,000 (税込)

配送予定日: 注文確認後2週間以内
保証: 3年間のProSupportプレミアム保証付き
サポート: 24時間365日テクニカルサポート
支払条件: 請求書発行後30日以内

お問い合わせ:
田中一郎
sales@otsuka-corp.co.jp
03-1234-5678
"""

# Sample comparison products for testing tables
SAMPLE_SIMILAR_PRODUCTS = [
    {
        "name": "HP EliteBook 860",
        "name_ja": "HP エリートブック 860",
        "features": ["Intel Core i7", "32GB RAM", "1TB SSD"],
        "features_ja": ["インテル Core i7", "32GB メモリ", "1TB SSD"],
        "price": 1899.99,
        "vendor": "HP Inc.",
        "vendor_ja": "HPインク株式会社"
    },
    {
        "name": "Lenovo ThinkPad P1",
        "name_ja": "レノボ ThinkPad P1",
        "features": ["Intel Core i9", "64GB RAM", "2TB SSD"],
        "features_ja": ["インテル Core i9", "64GB メモリ", "2TB SSD"],
        "price": 2499.99,
        "vendor": "Lenovo",
        "vendor_ja": "レノボ株式会社"
    },
    {
        "name": "Apple MacBook Pro",
        "name_ja": "アップル MacBook Pro",
        "features": ["Apple M2 Pro", "32GB RAM", "1TB SSD"],
        "features_ja": ["アップル M2 Pro", "32GB メモリ", "1TB SSD"],
        "price": 2699.99,
        "vendor": "Apple Inc.",
        "vendor_ja": "アップル株式会社"
    }
]

def setup_test_environment():
    """Prepare test environment by creating necessary directories"""
    # Create test output directory
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Create data assets directory if it doesn't exist
    assets_dir = Path("Data/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a sample template.pptx if needed (can be skipped if exists)
    # We're just checking if it exists
    template_path = assets_dir / "template.pptx"
    if not template_path.exists():
        logger.warning(f"Template file not found at {template_path}. Service will use default PowerPoint template.")

    return output_dir

async def test_language_detection():
    """Test the language detection logic specifically"""
    logger.info("=== TESTING LANGUAGE DETECTION ===")
    
    # Create an instance with OpenAI disabled
    service = PitchDeckService()
    
    # Test explicit language setting
    result = await service.extract_ppt_structure(
        SAMPLE_JAPANESE_QUOTATION,
        language="ja"
    )
    
    logger.info(f"Language detection result with explicit 'ja': {result.get('resolved_language', 'unknown')}")
    
    # Test language detection (should detect Japanese)
    result = await service.extract_ppt_structure(
        SAMPLE_JAPANESE_QUOTATION,
        language=None  # No explicit language
    )
    
    logger.info(f"Language detection result with auto-detection: {result.get('resolved_language', 'unknown')}")
    logger.info(f"Detection method: {result.get('language_resolution', {}).get('method', 'unknown')}")
    logger.info(f"Confidence: {result.get('language_resolution', {}).get('confidence', 0)}")

    return result

async def test_pitch_deck_generation():
    """Test the pitch deck generation with Japanese content"""
    logger.info("\n=== TESTING PITCH DECK GENERATION ===")
    
    output_dir = setup_test_environment()
    
    # Create the service
    service = PitchDeckService()
    
    # Extract PPT structure with explicit Japanese language
    data = await service.extract_ppt_structure(
        SAMPLE_JAPANESE_QUOTATION,
        language="ja",
        include_comparison_table=True
    )
    
    logger.info(f"✅ PPT structure extracted with language: {data.get('resolved_language', 'unknown')}")
    
    # Print the first slide title to verify Japanese content
    if data and 'slides' in data and len(data['slides']) > 0:
        logger.info(f"First slide title: {data['slides'][0]['title']}")
    
    # Generate the PowerPoint
    output_path = output_dir / "Japanese_Pitch_Deck_Test.pptx"
    generated_path = await service.generate_ppt(
        data,
        output_path=str(output_path),
        similar_products=SAMPLE_SIMILAR_PRODUCTS,
        product_name="laptop"
    )
    
    logger.info(f"✅ PowerPoint presentation generated at: {generated_path}")
    
    return generated_path

async def test_comparison_table():
    """Test the comparison table generation specifically"""
    logger.info("\n=== TESTING COMPARISON TABLE ===")
    
    service = PitchDeckService()
    
    # Test Japanese table generation
    ja_table = service.create_comparison_table_from_products(
        SAMPLE_SIMILAR_PRODUCTS,
        title="製品比較",
        language="ja"
    )
    
    logger.info("Japanese table columns: " + ", ".join(ja_table["columns"]))
    logger.info(f"Sample row in Japanese: {ja_table['rows'][0]}")
    
    # Test English table generation for comparison
    en_table = service.create_comparison_table_from_products(
        SAMPLE_SIMILAR_PRODUCTS,
        title="Product Comparison",
        language="en"
    )
    
    logger.info("English table columns: " + ", ".join(en_table["columns"]))
    logger.info(f"Sample row in English: {en_table['rows'][0]}")
    
    return ja_table

async def run_all_tests():
    """Run all tests in sequence"""
    try:
        await test_language_detection()
        await test_comparison_table()
        await test_pitch_deck_generation()
        
        logger.info("\n✅ All tests completed successfully!")
    except Exception as e:
        logger.error(f"❌ Test failed with error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
