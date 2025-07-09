import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
from services.pitch_deck_service import PitchDeckService

def build_test_quote():
    return {
        "customer": {
            "name": "Otsuka Corporation",
            "contact": "Taro Yamada",
            "email": "taro.yamada@otsuka.co.jp",
            "address": "1-2-3 Marunouchi, Chiyoda-ku, Tokyo, Japan"
        },
        "line_items": [
            #{"name": "Intel Core i9-13900K", "category": "cpu", "description": "High-end desktop CPU for gaming and productivity.", "specs": {"Cores": "24", "Threads": "32", "Base Clock": "3.0GHz", "Turbo Clock": "5.8GHz"}, "quantity": 1, "unit_price": 600.00, "warranty": "3 years", "support": "Standard support"},
            {"name": "ASUS ROG STRIX Z790-E Gaming", "category": "motherboard", "description": "ATX motherboard for Intel 13th Gen CPUs.", "specs": {"Chipset": "Intel Z790", "Form Factor": "ATX", "Memory Support": "DDR5"}, "quantity": 1, "unit_price": 400.00},
            {"name": "Corsair Vengeance 32GB DDR5", "category": "memory", "description": "High-speed DDR5 memory kit.", "specs": {"Capacity": "32GB", "Speed": "6000MHz"}, "quantity": 1, "unit_price": 200.00},
            {"name": "Samsung 980 PRO 2TB NVMe SSD", "category": "internal-hard-drive", "description": "High-performance NVMe SSD for fast storage.", "specs": {"Capacity": "2TB", "Type": "NVMe M.2"}, "quantity": 1, "unit_price": 250.00},
            {"name": "Corsair RM850x 850W PSU", "category": "power-supply", "description": "Fully modular power supply unit.", "specs": {"Wattage": "850W", "Efficiency": "80+ Gold"}, "quantity": 1, "unit_price": 150.00},
            {"name": "NZXT H510 Elite", "category": "case", "description": "Premium mid-tower ATX case.", "specs": {"Type": "Mid Tower", "Color": "White"}, "quantity": 1, "unit_price": 120.00},
            {"name": "Noctua NH-D15", "category": "cpu-cooler", "description": "High-performance air CPU cooler.", "specs": {"Type": "Air Cooler", "Fans": "2x 140mm"}, "quantity": 1, "unit_price": 100.00},
            {"name": "ASUS TUF Gaming VG27AQ", "category": "monitor", "description": "27-inch WQHD gaming monitor.", "specs": {"Size": "27-inch", "Resolution": "2560x1440", "Refresh Rate": "165Hz"}, "quantity": 1, "unit_price": 350.00}
        ],
        "total": 2170.00,
        "currency": "USD",
        "delivery_timeline": "2-3 weeks",
        "warranty": "3 years for CPU, 2 years for other components",
        "support": "Standard support for all components",
        "notes": "Quotation valid for 30 days. Includes assembly and basic testing."
    }

async def main():
    service = PitchDeckService()
    quote = build_test_quote()
    # Use realistic test data for both English and Japanese, focused on a CPU product
    realistic_data_en = {
        "slides": [
            {"title": "Customer Need", "content": [
                "Otsuka Corporation requires high-performance CPUs for their new engineering workstations.",
                "Reliable and scalable processing power to support business growth.",
                "Advanced compute for design, simulation, and AI workloads.",
                "Comprehensive warranty and support required.",
                "Efficient delivery and installation."
            ]},
            {"title": "Our Solution", "content": [
                "Intel Core i9-13900K: 24 cores, 32 threads, up to 5.8GHz turbo.",
                "Latest 13th Gen Intel architecture for top-tier performance.",
                "Compatible with DDR5 memory and PCIe 5.0 for future-proofing.",
                "3 years warranty and standard support included.",
                "Onsite installation and basic testing included."
            ]},
            {"title": "Product Overview", "content": [
                "Intel Core i9-13900K: 24 cores, 32 threads, 3.0GHz base, 5.8GHz turbo.",
                "Supports advanced workloads: engineering, AI, and simulation.",
                "Energy-efficient design with high reliability.",
                "Compatible with ASUS ROG STRIX Z790-E Gaming motherboard.",
                "All products covered by manufacturer warranty."
            ]},
            {"title": "Pricing Breakdown", "content": [
                "Intel Core i9-13900K: $600 each.",
                "ASUS ROG STRIX Z790-E Gaming: $400.",
                "Total: $1,000 USD (includes installation and testing).",
                "No hidden fees. Transparent pricing.",
                "Quotation valid for 30 days."
            ]},
            {"title": "Warranty & Support", "content": [
                "3 years warranty for CPU.",
                "2 years warranty for motherboard.",
                "Standard support for all components.",
                "Onsite installation and basic testing included.",
                "Remote diagnostics and proactive monitoring."
            ]},
            {"title": "Delivery Timeline", "content": [
                "Estimated delivery: 2-3 weeks from order confirmation.",
                "Onsite installation scheduled upon delivery.",
                "Minimal disruption to daily operations.",
                "Flexible scheduling to suit your needs.",
                "Dedicated project manager for smooth implementation."
            ]}
        ],
        "tables": [
            {
                "title": "Product Comparison",
                "columns": ["Product Name", "Key Features", "Price", "Vendor"],
                "rows": [
                    ["Intel Core i9-13900K", "24 cores, 32 threads, 5.8GHz turbo", "$600", "Intel"],
                    ["AMD Ryzen 9 7950X", "16 cores, 32 threads, 5.7GHz turbo", "$580", "AMD"],
                    ["Intel Core i7-13700K", "16 cores, 24 threads, 5.4GHz turbo", "$420", "Intel"]
                ]
            }
        ],
        "resolved_language": "en",
        "language_resolution": {"language": "en", "method": "test", "confidence": 1.0}
    }
    realistic_data_ja = {
        "slides": [
            {"title": "お客様のニーズ", "content": [
                "大塚株式会社は新しいエンジニアリングワークステーション向けに高性能CPUを必要としています。",
                "ビジネス成長を支える信頼性と拡張性のある処理能力。",
                "設計・シミュレーション・AI業務のための高度な計算力。",
                "包括的な保証とサポートが必要です。",
                "効率的な納品と設置。"
            ]},
            {"title": "当社のソリューション", "content": [
                "Intel Core i9-13900K：24コア、32スレッド、最大5.8GHzターボ。",
                "最新の第13世代Intelアーキテクチャによる最高クラスの性能。",
                "DDR5メモリとPCIe 5.0対応で将来性も抜群。",
                "3年間の保証と標準サポート付き。",
                "オンサイト設置と基本テストを含む。"
            ]},
            {"title": "製品概要", "content": [
                "Intel Core i9-13900K：24コア、32スレッド、3.0GHzベース、5.8GHzターボ。",
                "エンジニアリング・AI・シミュレーションなど高度な業務に対応。",
                "省エネ設計で高い信頼性。",
                "ASUS ROG STRIX Z790-E Gamingマザーボードと互換性あり。",
                "全製品にメーカー保証付き。"
            ]},
            {"title": "価格内訳", "content": [
                "Intel Core i9-13900K：1台あたり¥90,000。",
                "ASUS ROG STRIX Z790-E Gaming：¥60,000。",
                "合計：¥150,000（設置・テスト費用込み）。",
                "追加費用なし。透明な価格設定。",
                "見積有効期間は30日間。"
            ]},
            {"title": "保証・サポート", "content": [
                "CPUは3年間の保証。",
                "マザーボードは2年間の保証。",
                "全コンポーネントに標準サポート。",
                "オンサイト設置と基本テストを含む。",
                "リモート診断とプロアクティブモニタリング。"
            ]},
            {"title": "納品スケジュール", "content": [
                "注文確定後、納品予定：2～3週間。",
                "納品後にオンサイト設置を実施。",
                "日常業務への影響を最小限に。",
                "ご要望に応じた柔軟なスケジューリング。",
                "専任プロジェクトマネージャーによる円滑な導入。"
            ]},
            {"title": "次のステップ", "content": [
                "ご注文・納品スケジュールのご確認をお願いします。",
                "ソリューション仕様の最終確認。",
                "契約締結後、導入を開始。",
                "大塚と共にテクノロジーの未来へ。",
                "ご検討いただき誠にありがとうございます。"
            ]}
        ],
        "tables": [
            {
                "title": "製品比較",
                "columns": ["製品名", "主な特徴", "価格", "ベンダー"],
                "rows": [
                    ["Intel Core i9-13900K", "24コア、32スレッド、5.8GHzターボ", "¥90,000", "Intel"],
                    ["AMD Ryzen 9 7950X", "16コア、32スレッド、5.7GHzターボ", "¥87,000", "AMD"],
                    ["Intel Core i7-13700K", "16コア、24スレッド、5.4GHzターボ", "¥63,000", "Intel"]
                ]
            }
        ],
        "resolved_language": "ja",
        "language_resolution": {"language": "ja", "method": "test", "confidence": 1.0}
    }
    for lang, filename, test_data in [
        ("en", "test_en.pptx", realistic_data_en),
        ("ja", "test_ja.pptx", realistic_data_ja)
    ]:
        print(f"\nGenerating PPT for language: {lang}")
        product_category = quote["line_items"][0]["category"]
        output_path = await service.generate_ppt(test_data, filename, product_name=product_category)
        print(f"✅ PPT saved to: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
