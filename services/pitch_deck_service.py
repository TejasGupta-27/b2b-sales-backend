import os
import json
from openai import AzureOpenAI
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from config import settings
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class PitchDeckService:
    def __init__(self):
        # Initialize Azure OpenAI client
        try:
            from config import settings
            self.client = AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
                azure_endpoint=settings.azure_openai_endpoint
            )
            self.deployment_name = settings.azure_openai_deployment_name
            self.client_configured = True
        except Exception as e:
            logger.warning(f"Azure OpenAI client not configured: {e}")
            self.client = None
            self.deployment_name = None
            self.client_configured = False
        
        # Font configuration for Japanese support
        self.japanese_fonts = [
            "Yu Gothic UI",      # Windows 10/11 default
            "Meiryo UI",         # Windows 7/8
            "MS Gothic",         # Fallback Windows
            "Hiragino Kaku Gothic ProN",  # macOS
            "Hiragino Sans",     # macOS newer
            "Noto Sans CJK JP",  # Linux/Cross-platform
            "Arial Unicode MS",  # Cross-platform fallback
        ]
        
        # Detect if system supports Japanese fonts
        self.title_font = self._get_available_font(bold=True)
        self.body_font = self._get_available_font(bold=False)
        
        logger.info(f"Using fonts - Title: {self.title_font}, Body: {self.body_font}")
    
    def _get_available_font(self, bold=False):
        """Get the best available font for Japanese text"""
        # For PowerPoint, we'll use fonts that are commonly available
        # PowerPoint will fallback gracefully if the font isn't available
        
        if bold:
            # For titles/headers - prefer stronger fonts
            preferred_fonts = [
                "Yu Gothic UI Semibold",
                "Yu Gothic UI",
                "Meiryo UI",
                "MS Gothic",
                "Hiragino Kaku Gothic ProN",
                "Arial Unicode MS",
                "Segoe UI"  # Fallback
            ]
        else:
            # For body text - prefer readable fonts
            preferred_fonts = [
                "Yu Gothic UI",
                "Meiryo UI", 
                "MS Gothic",
                "Hiragino Sans",
                "Noto Sans CJK JP",
                "Arial Unicode MS",
                "Segoe UI"  # Fallback
            ]
        
        # Return the first font (PowerPoint will handle fallbacks)
        return preferred_fonts[0]
    
    def _detect_japanese_text(self, text):
        """Detect if text contains Japanese characters"""
        if not text:
            return False
        
        # Check for Japanese character ranges
        for char in text:
            code = ord(char)
            # Hiragana: 0x3040-0x309F
            # Katakana: 0x30A0-0x30FF  
            # Kanji: 0x4E00-0x9FAF
            # Japanese punctuation: 0x3000-0x303F
            if (0x3000 <= code <= 0x303F or  # Japanese punctuation
                0x3040 <= code <= 0x309F or  # Hiragana
                0x30A0 <= code <= 0x30FF or  # Katakana
                0x4E00 <= code <= 0x9FAF):   # Kanji
                return True
        return False
    
    def _apply_font_to_paragraph(self, paragraph, text, is_title=False):
        """Apply appropriate font to paragraph based on text content"""
        paragraph.text = text
        
        # Detect if Japanese text is present
        has_japanese = self._detect_japanese_text(text)
        
        if has_japanese:
            # Use Japanese-compatible font
            font_name = self.title_font if is_title else self.body_font
        else:
            # Use standard fonts for English text
            font_name = "Segoe UI Semibold" if is_title else "Segoe UI"
        
        # Apply font settings
        paragraph.font.name = font_name
        
        # Set font for Asian text specifically (this helps with mixed content)
        if has_japanese:
            try:
                # This helps PowerPoint use the correct font for Asian characters
                paragraph.font._element.set(qn('a:eastAsianTheme'), 'minor')
            except:
                pass  # Ignore if this advanced setting fails
        
        return paragraph

    def hide_placeholders(self, slide):
        shapes_to_remove = []
        for shape in slide.shapes:
            if hasattr(shape, 'placeholder_format') and shape.placeholder_format is not None:
                shapes_to_remove.append(shape)
            elif hasattr(shape, 'text_frame') and shape.text_frame is not None:
                if shape.text_frame.text.strip() in ['Click to add title', 'Click to add subtitle', 'Click to add text']:
                    shapes_to_remove.append(shape)
        for shape in shapes_to_remove:
            try:
                sp = shape._element
                sp.getparent().remove(sp)
            except:
                try:
                    shape.width = 0
                    shape.height = 0
                except:
                    pass

    def clear_slide_content_safely(self, slide):
        shapes_to_remove = []
        for shape in slide.shapes:
            if hasattr(shape, 'shape_type') and shape.shape_type in [1, 17, 14]:
                shapes_to_remove.append(shape)
            elif hasattr(shape, 'text_frame') and shape.text_frame is not None:
                try:
                    shape.text_frame.clear()
                except:
                    shapes_to_remove.append(shape)
        for shape in shapes_to_remove:
            try:
                sp = shape._element
                sp.getparent().remove(sp)
            except:
                try:
                    shape.width = 0
                    shape.height = 0
                except:
                    pass

    # ✅ UPDATED: added `language` param with fallback and hybrid detection
    async def extract_ppt_structure(self, quotation: str, language: str = "en", include_comparison_table: bool = False) -> dict:
        """Generate a structured and persuasive sales pitch deck with hybrid language detection."""
        
        if not self.client_configured:
            logger.warning("Azure OpenAI client not configured, using fallback structure")
            return self._get_fallback_structure(language)
        
        # Hybrid language detection approach
        from services.language_service import LanguageService
        language_service = LanguageService()
        
        # Resolve language using hybrid approach
        language_resolution = language_service.resolve_language(
            explicit_language=language,      # From frontend/initialization
            text_content=quotation,         # Auto-detection from quote content
            context=None                    # No additional context for quotes
        )
        
        # Update language based on resolution
        resolved_language = language_resolution['language']
        detection_method = language_resolution['method']
        confidence = language_resolution['confidence']
        
        logger.info(f"🌐 Pitch Deck Language Resolution:")
        logger.info(f"   Input Language: {language}")
        logger.info(f"   Resolved Language: {resolved_language}")
        logger.info(f"   Detection Method: {detection_method}")
        logger.info(f"   Confidence: {confidence:.2f}")

        # Add language condition based on resolved language
        language_note = ""
        if resolved_language == "ja":
            language_note = "\n\n### LANGUAGE\nPlease write ALL slide titles, bullet points, and table headers in Japanese."
        elif resolved_language == "es":
            language_note = "\n\n### LANGUAGE\nPlease write ALL slide titles, bullet points, and table headers in Spanish."
        elif resolved_language == "fr":
            language_note = "\n\n### LANGUAGE\nPlease write ALL slide titles, bullet points, and table headers in French."
        elif resolved_language == "de":
            language_note = "\n\n### LANGUAGE\nPlease write ALL slide titles, bullet points, and table headers in German."
        elif resolved_language != "en":
            language_service_info = language_service.supported_languages.get(resolved_language, {})
            language_name = language_service_info.get('name', resolved_language)
            language_note = f"\n\n### LANGUAGE\nPlease write ALL slide titles, bullet points, and table headers in {language_name}."

        prompt = f"""
You are a business assistant. Based on the product quotation below, generate a structured and persuasive PowerPoint sales pitch deck in **valid JSON** format.

### QUOTATION
\"""
{quotation}
\"""

### TASKS
1. Analyze the quotation to identify:
   - Customer name
   - Product name
   - Specifications (CPU, RAM, Storage, etc.)
   - Price, Delivery Timeline, Warranty, Support options

2. Generate a slide deck in this order:
   1. Customer Need
   2. Our Solution
   3. Product Overview (specs)
   4. Pricing Breakdown
   5. Warranty & Support
   6. Delivery Timeline
   7. Call to Action

Each slide must contain a **title** and 5–6 persuasive bullet points.

### JSON OUTPUT FORMAT
Return your response as valid JSON:
{{
  "slides": [
    {{
      "title": "Slide Title",
      "content": ["Bullet 1", "Bullet 2", "..."]
    }},
    ...
  ]
}}

✅ Use ONLY the product and specifications mentioned in the quotation — do NOT make up new ones.
✅ Return valid JSON ONLY — no commentary, no markdown.

{language_note}
"""
        
        # If comparison table is requested, add it to the prompt
        if include_comparison_table:
            comparison_section = """
3. Add a **comparison table** for competitive analysis with the following structure:

Add this to your JSON response:
"tables": [
  {
    "title": "Product Comparison",
    "columns": ["Product Name", "Price", "CPU", "RAM", "Storage", "Warranty", "Support"],
    "rows": [
      ["Product 1", "Price 1", "CPU 1", "RAM 1", "Storage 1", "Warranty 1", "Support 1"],
      ["Product 2", "Price 2", "CPU 2", "RAM 2", "Storage 2", "Warranty 2", "Support 2"],
      ["Product 3", "Price 3", "CPU 3", "RAM 3", "Storage 3", "Warranty 3", "Support 3"]
    ]
  }
]

Note: The comparison table will be populated with real competitor data separately.
"""
            # Insert the comparison section before the JSON format
            prompt = prompt.replace("### JSON OUTPUT FORMAT", comparison_section + "\n### JSON OUTPUT FORMAT")

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )

            raw_output = response.choices[0].message.content.strip()

            try:
                parsed = json.loads(raw_output)
                if isinstance(parsed, list):
                    result = {"slides": parsed}
                elif isinstance(parsed, dict) and "slides" in parsed:
                    result = parsed
                else:
                    raise ValueError("Parsed JSON is missing expected 'slides' structure.")
                
                # Add language metadata to result
                result['language_resolution'] = language_resolution
                result['resolved_language'] = resolved_language
                
                return result
                
            except json.JSONDecodeError:
                logger.error("GPT response was not valid JSON. Response was:\n%s", raw_output)
                return self._get_fallback_structure(resolved_language)
                
        except Exception as e:
            logger.error(f"Error in extract_ppt_structure: {e}")
            return self._get_fallback_structure(resolved_language)
    
    def _get_fallback_structure(self, language: str = "en") -> dict:
        """Provide a fallback structure when OpenAI is not available with language support"""
        
        # Get localized fallback content
        if language == "ja":
            return {
                "slides": [
                    {
                        "title": "お客様のニーズ分析",
                        "content": [
                            "ビジネス要件の理解",
                            "技術的な課題と機会の特定",
                            "現在のインフラの制約評価",
                            "スケーラビリティと成長ニーズの決定",
                            "予算とタイムラインの制約評価"
                        ]
                    },
                    {
                        "title": "包括的なソリューション",
                        "content": [
                            "お客様のビジネスに合わせたテクノロジーソリューション",
                            "業界をリードする製品とサービス",
                            "既存システムとのシームレスな統合",
                            "包括的なサポートとメンテナンス",
                            "将来に対応したスケーラブルなアーキテクチャ"
                        ]
                    },
                    {
                        "title": "製品概要と仕様",
                        "content": [
                            "高性能ハードウェアコンポーネント",
                            "エンタープライズグレードソフトウェアソリューション",
                            "高度なセキュリティ機能とプロトコル",
                            "信頼性の高いパフォーマンスと稼働時間保証",
                            "エネルギー効率的で持続可能な設計"
                        ]
                    },
                    {
                        "title": "投資と価格の内訳",
                        "content": [
                            "プレミアムソリューションの競争力のある価格",
                            "隠れた料金のない透明なコスト構造",
                            "柔軟な支払いオプションと融資",
                            "大量購入の場合のボリュームディスカウント",
                            "費用対効果の高い総所有コストモデル"
                        ]
                    },
                    {
                        "title": "保証とサポートサービス",
                        "content": [
                            "包括的な保証カバレッジ",
                            "24時間365日の技術サポート体制",
                            "オンサイトサービスとメンテナンス",
                            "リモート監視と診断",
                            "定期的なアップデートとシステム最適化"
                        ]
                    },
                    {
                        "title": "配送スケジュールと実装",
                        "content": [
                            "効率的なプロジェクト計画と実行",
                            "日常業務への最小限の影響",
                            "段階的な実装アプローチ",
                            "スタッフトレーニングと知識移転",
                            "実装後のサポートと最適化"
                        ]
                    },
                    {
                        "title": "次のステップとお取引",
                        "content": [
                            "詳細な技術コンサルテーションのスケジューリング",
                            "ソリューション仕様の確認と最終化",
                            "プロジェクトタイムラインとマイルストーンの確認",
                            "契約書に署名し、実装を開始",
                            "技術エクセレンスへの旅を始めましょう"
                        ]
                    }
                ],
                "language_resolution": {
                    "language": language,
                    "method": "fallback",
                    "confidence": 1.0
                },
                "resolved_language": language
            }
        else:
            # English fallback (existing structure)
            return {
                "slides": [
                    {
                        "title": "Customer Needs Analysis",
                        "content": [
                            "Understanding your business requirements",
                            "Identifying technology gaps and opportunities",
                            "Assessing current infrastructure limitations",
                            "Determining scalability and growth needs",
                            "Evaluating budget and timeline constraints"
                        ]
                    },
                    {
                        "title": "Our Comprehensive Solution",
                        "content": [
                            "Tailored technology solutions for your business",
                            "Industry-leading products and services",
                            "Seamless integration with existing systems",
                            "Comprehensive support and maintenance",
                            "Future-ready scalable architecture"
                        ]
                    },
                    {
                        "title": "Product Overview & Specifications",
                        "content": [
                            "High-performance hardware components",
                            "Enterprise-grade software solutions",
                            "Advanced security features and protocols",
                            "Reliable performance and uptime guarantees",
                            "Energy-efficient and sustainable design"
                        ]
                    },
                    {
                        "title": "Investment & Pricing Breakdown",
                        "content": [
                            "Competitive pricing for premium solutions",
                            "Transparent cost structure with no hidden fees",
                            "Flexible payment options and financing",
                            "Volume discounts for bulk purchases",
                            "Cost-effective total ownership model"
                        ]
                    },
                    {
                        "title": "Warranty & Support Services",
                        "content": [
                            "Comprehensive warranty coverage",
                            "24/7 technical support availability",
                            "On-site service and maintenance",
                            "Remote monitoring and diagnostics",
                            "Regular updates and system optimization"
                        ]
                    },
                    {
                        "title": "Delivery Timeline & Implementation",
                        "content": [
                            "Efficient project planning and execution",
                            "Minimal disruption to daily operations",
                            "Phased implementation approach",
                            "Staff training and knowledge transfer",
                            "Post-implementation support and optimization"
                        ]
                    },
                    {
                        "title": "Next Steps & Call to Action",
                        "content": [
                            "Schedule a detailed technical consultation",
                            "Review and finalize solution specifications",
                            "Confirm project timeline and milestones",
                            "Sign agreement and initiate implementation",
                            "Begin your journey to technology excellence"
                        ]
                    }
                ],
                "language_resolution": {
                    "language": language,
                    "method": "fallback",
                    "confidence": 1.0
                },
                "resolved_language": language
            }

    def add_comparison_table(self, slide, table_data):
        """Add comparison table with improved styling and Japanese font support"""
        rows = len(table_data["rows"]) + 1  # +1 for header
        cols = len(table_data["columns"])
        left = Inches(0.5)
        top = Inches(1.8)
        width = Inches(9)
        height = Inches(4.5)

        table_shape = slide.shapes.add_table(rows, cols, left, top, width, height).table
        
        # Set table style
        table_shape.table_direction = 0  # Left to right
        
        # Header row with improved styling
        for col, header in enumerate(table_data["columns"]):
            cell = table_shape.cell(0, col)
            
            # Clear existing content and add with proper font
            cell.text_frame.clear()
            p = cell.text_frame.paragraphs[0]
            self._apply_font_to_paragraph(p, header, is_title=True)
            p.font.bold = True
            p.font.size = Pt(14)
            p.font.color.rgb = RGBColor(255, 255, 255)  # White text
            p.alignment = PP_ALIGN.CENTER
            
            # Set cell background color
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(52, 73, 94)  # Dark blue
            
            # Add margins
            cell.margin_left = Inches(0.1)
            cell.margin_right = Inches(0.1)
            cell.margin_top = Inches(0.1)
            cell.margin_bottom = Inches(0.1)

        # Data rows with improved styling
        for i, row in enumerate(table_data["rows"], start=1):
            for j, value in enumerate(row):
                cell = table_shape.cell(i, j)
                
                # Clear existing content and add with proper font
                cell.text_frame.clear()
                p = cell.text_frame.paragraphs[0]
                self._apply_font_to_paragraph(p, str(value), is_title=False)
                p.font.size = Pt(12)
                p.font.color.rgb = RGBColor(44, 62, 80)  # Dark text
                p.alignment = PP_ALIGN.CENTER
                
                # Set alternating row colors
                if i % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(248, 249, 250)  # Light gray
                else:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(255, 255, 255)  # White
                
                # Add margins
                cell.margin_left = Inches(0.1)
                cell.margin_right = Inches(0.1)
                cell.margin_top = Inches(0.1)
                cell.margin_bottom = Inches(0.1)

    def create_comparison_table_from_products(self, similar_products: List[Dict[str, Any]], title: str = "Product Comparison") -> Dict[str, Any]:
        """Create a comparison table using real similar products from hybrid retriever"""
        
        if not similar_products:
            logger.warning("No similar products provided for comparison table")
            return {
                "title": title,
                "columns": ["Product Name", "Key Features", "Price", "Vendor"],
                "rows": [
                    ["No similar products found", "N/A", "N/A", "N/A"]
                ]
            }
        
        # Define table structure
        comparison_table = {
            "title": title,
            "columns": ["Product Name", "Key Features", "Price", "Vendor"],
            "rows": []
        }
        
        # Process up to 3 similar products
        for i, product in enumerate(similar_products[:3]):
            if not product:
                continue
                
            # Extract product information with fallbacks
            name = product.get('name', f'Product {i+1}')
            description = product.get('description', product.get('summary', 'N/A'))
            
            # Truncate description to fit in table
            if description and len(description) > 100:
                description = description[:97] + "..."
            
            # Handle price formatting
            price = product.get('price', 'N/A')
            if isinstance(price, (int, float)) and price > 0:
                price = f"${price:,.2f}"
            elif isinstance(price, str) and price.replace('.', '').replace(',', '').isdigit():
                try:
                    price_num = float(price.replace(',', ''))
                    price = f"${price_num:,.2f}"
                except:
                    price = str(price)
            else:
                price = "Contact for pricing"
            
            # Get vendor/brand
            vendor = product.get('brand', product.get('vendor', product.get('manufacturer', 'N/A')))
            
            comparison_table["rows"].append([
                name,
                description,
                price,
                vendor
            ])
        
        # Ensure we have at least 3 rows for better presentation
        while len(comparison_table["rows"]) < 3:
            row_num = len(comparison_table["rows"]) + 1
            comparison_table["rows"].append([
                f"Alternative Solution {row_num}",
                "Contact us for additional product options",
                "Quote on request",
                "Various vendors"
            ])
        
        logger.info(f"Created comparison table with {len(comparison_table['rows'])} products")
        return comparison_table

    async def generate_ppt(self, data: dict, output_path: str = "Sales_Pitch_Deck.pptx", similar_products: List[Dict[str, Any]] = None):
        """Generate a PowerPoint presentation from the structured data with hybrid language support and optional similar products"""
        
        # Get resolved language from data
        resolved_language = data.get('resolved_language', 'en')
        language_resolution = data.get('language_resolution', {})
        
        logger.info(f"🌐 Generating presentation in resolved language: {resolved_language}")
        if language_resolution:
            logger.info(f"   Detection method: {language_resolution.get('method', 'unknown')}")
            logger.info(f"   Confidence: {language_resolution.get('confidence', 0):.2f}")
        
        # Always resolve template path relative to project root
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, "..", "Data", "assets", "template.pptx")
        template_path = os.path.abspath(template_path)

        if os.path.exists(template_path):
            logger.info(f"Using template.pptx at {template_path}")
            prs = Presentation(template_path)
        else:
            logger.info("Creating new presentation (no template found)")
            prs = Presentation()
        
        # Color scheme
        TITLE_COLOR = RGBColor(44, 62, 80)
        ACCENT_COLOR = RGBColor(52, 152, 219)
        BODY_COLOR = RGBColor(80, 80, 80)

        # Create cover slide with improved design
        cover_slide = prs.slides.add_slide(prs.slide_layouts[0])
        self.hide_placeholders(cover_slide)  # Hide template placeholders
        
        # Add main title box with improved styling
        title_box = cover_slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(2))
        tf = title_box.text_frame
        tf.clear()
        tf.margin_left = Inches(0.3)
        tf.margin_right = Inches(0.3)
        tf.margin_top = Inches(0.2)
        tf.margin_bottom = Inches(0.2)
        
        # Main title with language support
        title_p = tf.paragraphs[0]
        if resolved_language == "ja":
            main_title = "営業プレゼンテーション"
        elif resolved_language == "es":
            main_title = "Presentación de Ventas"
        elif resolved_language == "fr":
            main_title = "Présentation de Vente"
        elif resolved_language == "de":
            main_title = "Verkaufspräsentation"
        else:
            main_title = "Sales Pitch Deck"
            
        self._apply_font_to_paragraph(title_p, main_title, is_title=True)
        title_p.font.size = Pt(48)
        title_p.font.bold = True
        title_p.font.color.rgb = TITLE_COLOR
        title_p.alignment = PP_ALIGN.CENTER
        
        # Add decorative elements
        # Top accent line
        top_line = cover_slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 
            Inches(1.5), Inches(1.5), Inches(7), Inches(0.1)
        )
        top_line.fill.solid()
        top_line.fill.fore_color.rgb = ACCENT_COLOR
        top_line.line.fill.background()
        
        # Bottom accent line
        bottom_line = cover_slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 
            Inches(1.5), Inches(4.2), Inches(7), Inches(0.1)
        )
        bottom_line.fill.solid()
        bottom_line.fill.fore_color.rgb = ACCENT_COLOR
        bottom_line.line.fill.background()
        
        # Subtitle with improved styling and language support
        subtitle_box = cover_slide.shapes.add_textbox(Inches(1), Inches(4.5), Inches(8), Inches(1))
        tf_sub = subtitle_box.text_frame
        tf_sub.clear()
        tf_sub.margin_left = Inches(0.3)
        tf_sub.margin_right = Inches(0.3)
        tf_sub.margin_top = Inches(0.1)
        tf_sub.margin_bottom = Inches(0.1)
        
        subtitle_p = tf_sub.paragraphs[0]
        if resolved_language == "ja":
            subtitle_text = "見積もり分析から生成"
        elif resolved_language == "es":
            subtitle_text = "Generado desde Análisis de Cotización"
        elif resolved_language == "fr":
            subtitle_text = "Généré depuis l'Analyse de Devis"
        elif resolved_language == "de":
            subtitle_text = "Erstellt aus Angebotsanalyse"
        else:
            subtitle_text = "Generated from Quotation Analysis"
            
        self._apply_font_to_paragraph(subtitle_p, subtitle_text, is_title=False)
        subtitle_p.font.size = Pt(24)
        subtitle_p.font.color.rgb = ACCENT_COLOR
        subtitle_p.alignment = PP_ALIGN.CENTER
        
        # Add company info box with language support
        company_box = cover_slide.shapes.add_textbox(Inches(1), Inches(6), Inches(8), Inches(1))
        tf_company = company_box.text_frame
        tf_company.clear()
        tf_company.margin_left = Inches(0.3)
        tf_company.margin_right = Inches(0.3)
        tf_company.margin_top = Inches(0.1)
        tf_company.margin_bottom = Inches(0.1)
        
        company_p = tf_company.paragraphs[0]
        if resolved_language == "ja":
            company_text = "プロフェッショナルテクノロジーソリューション"
        elif resolved_language == "es":
            company_text = "Soluciones Tecnológicas Profesionales"
        elif resolved_language == "fr":
            company_text = "Solutions Technologiques Professionnelles"
        elif resolved_language == "de":
            company_text = "Professionelle Technologielösungen"
        else:
            company_text = "Professional Technology Solutions"
            
        self._apply_font_to_paragraph(company_p, company_text, is_title=False)
        company_p.font.size = Pt(18)
        company_p.font.color.rgb = RGBColor(100, 100, 100)
        company_p.alignment = PP_ALIGN.CENTER

        # Create content slides with improved formatting
        for i, slide_data in enumerate(data.get("slides", [])):
            slide = prs.slides.add_slide(prs.slide_layouts[1])  # Use content layout
            self.hide_placeholders(slide)  # Hide template placeholders
            
            # Add title with improved styling and centering
            title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(1.2))
            tf = title_box.text_frame
            tf.clear()
            tf.margin_left = Inches(0.2)
            tf.margin_right = Inches(0.2)
            tf.margin_top = Inches(0.1)
            tf.margin_bottom = Inches(0.1)
            
            title_p = tf.paragraphs[0]
            self._apply_font_to_paragraph(title_p, slide_data["title"], is_title=True)
            title_p.font.size = Pt(36)
            title_p.font.bold = True
            title_p.font.color.rgb = TITLE_COLOR
            title_p.alignment = PP_ALIGN.CENTER

            # Add decorative underline
            underline_shape = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 
                Inches(2), Inches(1.3), Inches(6), Inches(0.05)
            )
            underline_shape.fill.solid()
            underline_shape.fill.fore_color.rgb = ACCENT_COLOR
            underline_shape.line.fill.background()

            # Add content with improved formatting and center alignment
            content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(8.4), Inches(5.5))
            tf = content_box.text_frame
            tf.word_wrap = True
            tf.clear()
            tf.margin_left = Inches(0.3)
            tf.margin_right = Inches(0.3)
            tf.margin_top = Inches(0.2)
            tf.margin_bottom = Inches(0.2)

            for j, line_text in enumerate(slide_data["content"]):
                if j == 0:
                    # First paragraph already exists
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                
                bullet_text = f"• {line_text}"
                self._apply_font_to_paragraph(p, bullet_text, is_title=False)
                p.font.size = Pt(18)
                p.font.color.rgb = BODY_COLOR
                p.alignment = PP_ALIGN.LEFT
                p.space_after = Pt(16)  # Increased spacing for better readability
                p.space_before = Pt(8)   # Add space before each bullet
                
                # Add some color variation for visual interest
                if j % 2 == 0:
                    p.font.color.rgb = BODY_COLOR
                else:
                    p.font.color.rgb = RGBColor(60, 60, 60)  # Slightly lighter
            
            # Add slide number
            slide_number_box = slide.shapes.add_textbox(Inches(8.5), Inches(7.2), Inches(1), Inches(0.5))
            tf_num = slide_number_box.text_frame
            tf_num.clear()
            
            num_p = tf_num.paragraphs[0]
            self._apply_font_to_paragraph(num_p, f"{i+2}", is_title=False)  # +2 because cover slide is 1
            num_p.font.size = Pt(12)
            num_p.font.color.rgb = RGBColor(150, 150, 150)
            num_p.alignment = PP_ALIGN.RIGHT

        # Create table slides - check if we have similar products to replace any existing table
        tables_to_process = data.get("tables", [])
        
        # If we have similar products, create a comparison table
        if similar_products:
            if resolved_language == "ja":
                comparison_title = "製品比較"
            elif resolved_language == "es":
                comparison_title = "Comparación de Productos"
            elif resolved_language == "fr":
                comparison_title = "Comparaison de Produits"
            elif resolved_language == "de":
                comparison_title = "Produktvergleich"
            else:
                comparison_title = "Product Comparison"
                
            comparison_table = self.create_comparison_table_from_products(similar_products, comparison_title)
            
            # Replace any existing comparison table or add new one
            comparison_found = False
            for i, table_data in enumerate(tables_to_process):
                if "comparison" in table_data.get("title", "").lower() or "product" in table_data.get("title", "").lower():
                    tables_to_process[i] = comparison_table
                    comparison_found = True
                    logger.info("Replaced existing comparison table with similar products")
                    break
            
            # If no comparison table found, add the new one
            if not comparison_found:
                tables_to_process.append(comparison_table)
                logger.info("Added new comparison table with similar products")
        
        # Create table slides with improved formatting
        for table_data in tables_to_process:
            slide = prs.slides.add_slide(prs.slide_layouts[1])  # Use content layout
            self.hide_placeholders(slide)  # Hide template placeholders
            
            # Add title with improved styling and centering
            title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(1.2))
            tf = title_box.text_frame
            tf.clear()
            tf.margin_left = Inches(0.2)
            tf.margin_right = Inches(0.2)
            tf.margin_top = Inches(0.1)
            tf.margin_bottom = Inches(0.1)
            
            title_p = tf.paragraphs[0]
            self._apply_font_to_paragraph(title_p, table_data["title"], is_title=True)
            title_p.font.size = Pt(32)
            title_p.font.bold = True
            title_p.font.color.rgb = TITLE_COLOR
            title_p.alignment = PP_ALIGN.CENTER
            
            # Add decorative underline
            underline_shape = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 
                Inches(2), Inches(1.3), Inches(6), Inches(0.05)
            )
            underline_shape.fill.solid()
            underline_shape.fill.fore_color.rgb = ACCENT_COLOR
            underline_shape.line.fill.background()
            
            # Add table with improved positioning
            self.add_comparison_table(slide, table_data)

        try:
            prs.save(output_path)
            logger.info("Presentation saved successfully to: %s", output_path)
            logger.info(f"🌐 Presentation generated in {resolved_language} using {language_resolution.get('method', 'unknown')} detection")
            return output_path
        except Exception as e:
            logger.error("Error saving presentation: %s", e)
            raise

# Test function for Japanese PowerPoint generation
def test_japanese_ppt():
    """Test Japanese text in PowerPoint generation"""
    import asyncio
    
    async def run_test():
        service = PitchDeckService()
        
        # Test data with Japanese content
        test_data = {
            "slides": [
                {
                    "title": "お客様のニーズ",
                    "content": [
                        "高性能なワークステーションが必要",
                        "信頼性の高いシステムを求めています",
                        "効率的な作業環境の構築",
                        "長期サポートが重要",
                        "コストパフォーマンスを重視"
                    ]
                },
                {
                    "title": "私たちのソリューション",
                    "content": [
                        "最新技術を活用した高性能PC",
                        "24時間365日のサポート体制",
                        "カスタマイズ可能な構成",
                        "長期保証による安心",
                        "競争力のある価格設定"
                    ]
                }
            ],
            "tables": [
                {
                    "title": "製品比較表",
                    "columns": ["製品名", "価格", "CPU", "メモリ", "ストレージ", "保証", "サポート"],
                    "rows": [
                        ["ワークステーション Pro", "¥300,000", "Intel i7", "32GB", "1TB SSD", "3年", "24/7"],
                        ["ワークステーション Advanced", "¥350,000", "Intel i7", "32GB", "1TB SSD", "3年", "24/7"],
                        ["ワークステーション Premium", "¥400,000", "Intel i7", "32GB", "1TB SSD", "3年", "24/7"]
                    ]
                }
            ]
        }
        
        output_path = await service.generate_ppt(test_data, "japanese_test_presentation.pptx")
        print(f"✅ Japanese test PowerPoint saved to: {output_path}")
    
    # Note: You'll need to handle the async call appropriately in your application
    # This is just for demonstration
    try:
        asyncio.run(run_test())
    except RuntimeError:
        # If already in an async context, use this instead
        print("Run test_japanese_ppt() in an async context")

if __name__ == "__main__":
    test_japanese_ppt()
