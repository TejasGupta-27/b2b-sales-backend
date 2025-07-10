"""
Test Japanese language detection in quotations and generate presentation
for manual validation of Japanese fonts and text.
"""
import asyncio
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("japanese_quotation_test")

# Import the PitchDeckService
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.pitch_deck_service import PitchDeckService

# Sample Japanese quotation
JAPANESE_QUOTATION = """
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

async def test_japanese_quotation():
    """Test handling of Japanese quotation"""
    logger.info("Testing Japanese quotation handling")
    
    # Initialize the service
    pitch_deck_service = PitchDeckService()
    
    # Test with explicit Japanese language flag
    logger.info("1. Testing with explicit 'ja' language flag")
    structure = await pitch_deck_service.extract_ppt_structure(
        JAPANESE_QUOTATION, 
        language="ja", 
        include_comparison_table=True
    )
    
    logger.info(f"Resolved language: {structure.get('resolved_language')}")
    logger.info(f"First slide title: {structure['slides'][0]['title']}")
    
    # Test with auto-detection
    logger.info("2. Testing with language auto-detection")
    auto_structure = await pitch_deck_service.extract_ppt_structure(
        JAPANESE_QUOTATION, 
        language=None,  # Auto-detect
        include_comparison_table=True
    )
    
    logger.info(f"Auto-detected language: {auto_structure.get('resolved_language')}")
    logger.info(f"Detection method: {auto_structure.get('language_resolution', {}).get('method')}")
    
    # Generate PowerPoint
    logger.info("3. Generating PowerPoint with Japanese content")
    ppt_path = await pitch_deck_service.generate_ppt(
        structure,
        output_path="Japanese_Test.pptx",
        product_name="laptop"
    )
    
    logger.info(f"PowerPoint generated at: {ppt_path}")
    logger.info("Test completed successfully!")
    
    return ppt_path

if __name__ == "__main__":
    asyncio.run(test_japanese_quotation())
