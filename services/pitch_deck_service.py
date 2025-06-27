import os
import json
from openai import AzureOpenAI
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
#from config import settings
import logging

logger = logging.getLogger(__name__)

class PitchDeckService:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        self.deployment_name = settings.azure_openai_deployment_name
        
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
        """Safely hide placeholders without corrupting the slide structure"""
        shapes_to_remove = []
        
        for shape in slide.shapes:
            # Check if it's a placeholder
            if hasattr(shape, 'placeholder_format') and shape.placeholder_format is not None:
                shapes_to_remove.append(shape)
            # Also remove text boxes that might be default placeholders
            elif hasattr(shape, 'text_frame') and shape.text_frame is not None:
                # Check if it contains placeholder text
                if shape.text_frame.text.strip() in ['Click to add title', 'Click to add subtitle', 'Click to add text']:
                    shapes_to_remove.append(shape)
        
        # Remove identified placeholders
        for shape in shapes_to_remove:
            try:
                sp = shape._element
                sp.getparent().remove(sp)
            except:
                # If direct removal fails, try making it invisible
                try:
                    shape.width = 0
                    shape.height = 0
                except:
                    pass

    def clear_slide_content_safely(self, slide):
        """Safely clear slide content without corrupting the slide structure"""
        # Only remove content shapes, not structural elements
        shapes_to_remove = []
        
        for shape in slide.shapes:
            # Only remove shapes that are not essential slide structure
            if (hasattr(shape, 'shape_type') and 
                shape.shape_type in [1, 17, 14]):  # Text box, auto shape, picture
                shapes_to_remove.append(shape)
            elif hasattr(shape, 'text_frame') and shape.text_frame is not None:
                # Clear text content but keep the shape structure
                try:
                    shape.text_frame.clear()
                except:
                    shapes_to_remove.append(shape)
        
        # Remove non-essential shapes
        for shape in shapes_to_remove:
            try:
                sp = shape._element
                sp.getparent().remove(sp)
            except:
                # If removal fails, just hide it
                try:
                    shape.width = 0
                    shape.height = 0
                except:
                    pass

    async def extract_ppt_structure(self, quotation: str) -> dict:
        """Use Azure OpenAI to generate a detailed and persuasive sales pitch deck structure from the quotation."""
        prompt = f"""
You are a business assistant. Based on the product quotation below, generate a structured and persuasive PowerPoint sales pitch deck in **valid JSON** format.

### QUOTATION
\"\"\"
{quotation}
\"\"\"

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
   6. Product Comparison (see below)
   7. Delivery Timeline
   8. Call to Action

Each slide must contain a **title** and 5–6 persuasive bullet points.

3. Add a **comparison table** duplicating the same product 3 times with slightly varied names:
   - Copy the product specs from the quotation
   - Change the name to `"Product Name Variant 1"`, `"Variant 2"`, etc.
   - Add them to a table with the following structure:

### JSON OUTPUT FORMAT
Return your response as valid JSON:
{{
  "slides": [
    {{
      "title": "Slide Title",
      "content": ["Bullet 1", "Bullet 2", "..."]
    }},
    ...
  ],
  "tables": [
    {{
      "title": "Product Comparison",
      "columns": ["Product Name", "Price", "CPU", "RAM", "Storage", "Warranty", "Support"],
      "rows": [
        ["...Variant 1...", "...", "...", "...", "...", "...", "..."],
        ["...Variant 2...", "...", "...", "...", "...", "...", "..."],
        ["...Variant 3...", "...", "...", "...", "...", "...", "..."]
      ]
    }}
  ]
}}

✅ Use ONLY the product and specifications mentioned in the quotation — do NOT make up new ones.  
✅ Use slightly varied product names for realism.  
✅ Return valid JSON ONLY — no commentary, no markdown.
"""

        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )

        raw_output = response.choices[0].message.content.strip()

        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, list):
                return {"slides": parsed}
            elif isinstance(parsed, dict) and "slides" in parsed:
                return parsed
            else:
                raise ValueError("Parsed JSON is missing expected 'slides' structure.")
        except json.JSONDecodeError:
            logger.error("GPT response was not valid JSON. Response was:\n%s", raw_output)
            raise

    def add_comparison_table(self, slide, table_data):
        """Add comparison table with Japanese font support"""
        rows = len(table_data["rows"]) + 1  # +1 for header
        cols = len(table_data["columns"])
        left = Inches(0.5)
        top = Inches(1.5)
        width = Inches(9)
        height = Inches(5)

        table_shape = slide.shapes.add_table(rows, cols, left, top, width, height).table

        # Header row
        for col, header in enumerate(table_data["columns"]):
            cell = table_shape.cell(0, col)
            
            # Clear existing content and add with proper font
            cell.text_frame.clear()
            p = cell.text_frame.paragraphs[0]
            self._apply_font_to_paragraph(p, header, is_title=True)
            p.font.bold = True
            p.font.size = Pt(14)

        # Data rows
        for i, row in enumerate(table_data["rows"], start=1):
            for j, value in enumerate(row):
                cell = table_shape.cell(i, j)
                
                # Clear existing content and add with proper font
                cell.text_frame.clear()
                p = cell.text_frame.paragraphs[0]
                self._apply_font_to_paragraph(p, str(value), is_title=False)
                p.font.size = Pt(12)

    async def generate_ppt(self, data: dict, output_path: str = "Sales_Pitch_Deck.pptx"):
        """Generate a PowerPoint presentation from the structured data with Japanese support"""
        # Load template if it exists, otherwise create new presentation
        template_path = "../Data/assets/template.pptx"
        if os.path.exists(template_path):
            logger.info("Using template.pptx")
            prs = Presentation(template_path)
        else:
            logger.info("Creating new presentation (no template found)")
            prs = Presentation()
        
        # Color scheme
        TITLE_COLOR = RGBColor(44, 62, 80)
        ACCENT_COLOR = RGBColor(52, 152, 219)
        BODY_COLOR = RGBColor(80, 80, 80)

        # Create cover slide
        cover_slide = prs.slides.add_slide(prs.slide_layouts[0])
        self.hide_placeholders(cover_slide)  # Hide template placeholders
        
        # Add cover slide content with Japanese support
        title_box = cover_slide.shapes.add_textbox(Inches(1.5), Inches(1.5), Inches(7), Inches(2))
        tf = title_box.text_frame
        tf.clear()
        
        # Main title
        title_p = tf.paragraphs[0]
        main_title = "Sales Pitch Deck"
        self._apply_font_to_paragraph(title_p, main_title, is_title=True)
        title_p.font.size = Pt(44)
        title_p.font.bold = True
        title_p.font.color.rgb = TITLE_COLOR
        title_p.alignment = PP_ALIGN.CENTER
        
        # Subtitle
        subtitle_p = tf.add_paragraph()
        subtitle_text = "Generated from Quotation"
        self._apply_font_to_paragraph(subtitle_p, subtitle_text, is_title=False)
        subtitle_p.font.size = Pt(24)
        subtitle_p.font.color.rgb = ACCENT_COLOR
        subtitle_p.alignment = PP_ALIGN.CENTER

        # Create content slides
        for slide_data in data.get("slides", []):
            slide = prs.slides.add_slide(prs.slide_layouts[1])  # Use content layout
            self.hide_placeholders(slide)  # Hide template placeholders
            
            # Add title with Japanese support
            title_box = slide.shapes.add_textbox(Inches(0.7), Inches(0.5), Inches(8), Inches(1))
            tf = title_box.text_frame
            tf.clear()
            
            title_p = tf.paragraphs[0]
            self._apply_font_to_paragraph(title_p, slide_data["title"], is_title=True)
            title_p.font.size = Pt(32)
            title_p.font.bold = True
            title_p.font.color.rgb = TITLE_COLOR

            # Add accent line
            line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1.5), Inches(0.1), Inches(4))
            line.fill.solid()
            line.fill.fore_color.rgb = ACCENT_COLOR
            line.line.fill.background()

            # Add content with Japanese support
            content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(8), Inches(5))
            tf = content_box.text_frame
            tf.word_wrap = True
            tf.clear()

            for i, line_text in enumerate(slide_data["content"]):
                if i == 0:
                    # First paragraph already exists
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                
                bullet_text = f"• {line_text}"
                self._apply_font_to_paragraph(p, bullet_text, is_title=False)
                p.font.size = Pt(20)
                p.font.color.rgb = BODY_COLOR
                p.space_after = Pt(12)

        # Create table slides
        for table_data in data.get("tables", []):
            slide = prs.slides.add_slide(prs.slide_layouts[1])  # Use content layout
            self.hide_placeholders(slide)  # Hide template placeholders
            
            # Add title with Japanese support
            title_box = slide.shapes.add_textbox(Inches(0.7), Inches(0.5), Inches(8), Inches(1))
            tf = title_box.text_frame
            tf.clear()
            
            title_p = tf.paragraphs[0]
            self._apply_font_to_paragraph(title_p, table_data["title"], is_title=True)
            title_p.font.size = Pt(32)
            title_p.font.bold = True
            title_p.font.color.rgb = TITLE_COLOR
            
            # Add table with Japanese support
            self.add_comparison_table(slide, table_data)

        # Save presentation
        try:
            prs.save(output_path)
            logger.info("Presentation saved successfully to: %s", output_path)
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