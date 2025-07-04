from io import BytesIO
import re
import requests
from pathlib import Path
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                  Spacer, Table, TableStyle)

# If you use 'font_url', define it or import it as well:
font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansJP-Regular.otf"

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.japanese_font_registered = False
        self._register_japanese_fonts()
        self._setup_custom_styles()
    
    def _register_japanese_fonts(self):
        """Register Japanese fonts for use in PDF"""
        try:
            fonts_dir = Path("fonts")
            fonts_dir.mkdir(exist_ok=True)
            font_path = fonts_dir / "NotoSansJP-Regular.ttf"
            if not font_path.exists():
                print("📥 Downloading Noto Sans CJK font...")
                response = requests.get(font_url, timeout=30)
                response.raise_for_status()
                
                with open(font_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Font downloaded: {font_path}")
            
            # Register the downloaded font
            pdfmetrics.registerFont(TTFont('JapaneseFont', str(font_path)))
            self.japanese_font_registered = True
            print("✅ Japanese font registered successfully")
            
        except Exception as e:
            print(f"❌ Font registration error: {e}")
    
    def _setup_custom_styles(self):
        """Setup custom styles for the PDF"""
        # Use standard font initially - will be updated per language
        font_name = 'Helvetica'
        
        # Company header style
        self.styles.add(ParagraphStyle(
            name='CompanyHeader',
            parent=self.styles['Normal'],  # Changed from Heading1 to Normal
            fontName=font_name,
            fontSize=24,
            textColor=colors.HexColor('#2E4057'),
            alignment=TA_CENTER,
            spaceAfter=30
        ))
        
        # Quote title style
        self.styles.add(ParagraphStyle(
            name='QuoteTitle',
            parent=self.styles['Normal'],  # Changed from Heading1 to Normal
            fontName=font_name,
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Normal'],  # Changed from Heading3 to Normal
            fontName=font_name,
            fontSize=14,
            textColor=colors.HexColor('#2E4057'),
            alignment=TA_LEFT,
            spaceAfter=12,
            spaceBefore=20
        ))
        
        # Table cell style for descriptions
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontName=font_name,
            fontSize=9,
            leading=11,
            leftIndent=2,
            rightIndent=2,
            spaceAfter=0,
            spaceBefore=0
        ))
        
        # Small text style
        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontName=font_name,
            fontSize=8,
            leading=10
        ))
        
        # Add custom styles for the new quote format
        self.styles.add(ParagraphStyle(
            name='CompanyTagline',
            parent=self.styles['Normal'],
            fontName=font_name,
            fontSize=10,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER,
            spaceAfter=20
        ))
        
        # Japanese text style
        self.styles.add(ParagraphStyle(
            name='JapaneseText',
            parent=self.styles['Normal'],
            fontName=font_name,
            fontSize=10,
            leading=14,
            alignment=TA_LEFT
        ))
    
    def update_styles_for_language(self, language: str = "en"):
        """Update PDF styles to use appropriate fonts for the given language"""
        if language == "ja" and self.japanese_font_registered:
            # Update all styles to use Japanese font
            for style_name in ['CompanyHeader', 'QuoteTitle', 'SectionHeader', 'TableCell', 'SmallText', 'CompanyTagline', 'JapaneseText']:
                if style_name in self.styles:
                    self.styles[style_name].fontName = 'JapaneseFont'
            
            # Update Normal style as well
            if 'Normal' in self.styles:
                self.styles['Normal'].fontName = 'JapaneseFont'
        
        print(f"✅ Styles updated for language: {language}")
    
    def _format_japanese_text(self, text: str, max_width: int = 50) -> str:
        """Format Japanese text with proper line breaks and spacing"""
        if not text:
            return text
            
        # Check if text contains Japanese characters
        has_japanese = any(
            0x3000 <= ord(char) <= 0x9FAF  # Japanese character ranges
            for char in text
        )
        
        if not has_japanese:
            return text
            
        # For Japanese text, add soft breaks at logical points
        # Add zero-width spaces after certain characters to allow line breaks
        japanese_break_chars = ['、', '。', '！', '？', '：', '；', '）', '】', '』', '」']
        
        formatted_text = text
        for char in japanese_break_chars:
            # Add a zero-width space after punctuation to allow line breaks
            formatted_text = formatted_text.replace(char, char + '\u200B')
        
        # Also add breaks after certain particles and conjunctions
        particles = ['は', 'が', 'を', 'に', 'で', 'と', 'の', 'から', 'まで', 'より', 'など']
        for particle in particles:
            formatted_text = formatted_text.replace(particle, particle + '\u200B')
        
        # If text is still too long, add manual line breaks
        if len(formatted_text) > max_width:
            # Split into roughly equal parts
            mid_point = len(formatted_text) // 2
            # Find the nearest break point
            for i in range(mid_point - 10, mid_point + 10):
                if i < len(formatted_text) and formatted_text[i] in ['、', '。', ' ', '\u200B']:
                    formatted_text = formatted_text[:i+1] + '\n' + formatted_text[i+1:]
                    break
        
        return formatted_text
    
    def _create_table_paragraph(self, text: str, style_name: str = 'TableCell') -> Paragraph:
        """Create a paragraph with proper Japanese text formatting"""
        formatted_text = self._format_japanese_text(text, max_width=40)
        return Paragraph(formatted_text, self.styles[style_name])
    
    def generate_quote_pdf(self, quote_data: Dict[str, Any]) -> BytesIO:
        """Generate PDF from quote data with Japanese support"""
        buffer = BytesIO()
        
        try:
            # Create PDF document with better margins
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=50,
                leftMargin=50,
                topMargin=50,
                bottomMargin=50
            )
            
            # Build PDF content
            story = []
            
            # Header with title and tagline
            story.append(Paragraph(quote_data.get('quote_title', 'Technology Solution Quote'), self.styles['QuoteTitle']))
            story.append(Paragraph(quote_data.get('company_tagline', 'Professional Technology Solutions'), self.styles['CompanyTagline']))
            story.append(Spacer(1, 12))
            
            # Quote information
            labels = quote_data.get('labels', {})
            quote_info = [
                [labels.get('quote_number', 'Quote Number:'), quote_data.get('quote_number', 'N/A')],
                [labels.get('date', 'Date:'), quote_data.get('created_at', '')[:10] if quote_data.get('created_at') else 'N/A'],
                [labels.get('valid_until', 'Valid Until:'), quote_data.get('valid_until', '')[:10] if quote_data.get('valid_until') else 'N/A'],
            ]
            
            quote_table = Table(quote_info, colWidths=[2*inch, 3*inch])
            quote_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(quote_table)
            story.append(Spacer(1, 20))
            
            # Customer information
            customer_info = quote_data.get('customer_info', {})
            if customer_info:
                story.append(Paragraph(labels.get('customer_information', 'Customer Information'), self.styles['SectionHeader']))
                
                customer_data = []
                if customer_info.get('company'):
                    customer_data.append([labels.get('company', 'Company:'), customer_info['company']])
                if customer_info.get('contact'):
                    customer_data.append([labels.get('contact', 'Contact:'), customer_info['contact']])
                if customer_info.get('email'):
                    customer_data.append([labels.get('email', 'Email:'), customer_info['email']])
                if customer_info.get('phone'):
                    customer_data.append([labels.get('phone', 'Phone:'), customer_info['phone']])
                
                if customer_data:
                    customer_table = Table(customer_data, colWidths=[2*inch, 3*inch])
                    customer_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]))
                    story.append(customer_table)
                story.append(Spacer(1, 20))
            
            # Line items with better text wrapping
            labels = quote_data.get('labels', {})
            story.append(Paragraph(labels.get('quote_details', 'Quote Details'), self.styles['SectionHeader']))
            
            line_items = quote_data.get('line_items', [])
            if line_items:
                # Create table headers with localized labels
                table_data = [[
                    labels.get('item', 'Item'), 
                    labels.get('description', 'Description'), 
                    labels.get('qty', 'Qty'), 
                    labels.get('unit_price', 'Unit Price'), 
                    labels.get('total', 'Total')
                ]]
                
                # Add line items with text wrapping
                for item in line_items:
                    # Use proper Japanese text formatting
                    name = item.get('name', '')
                    description = item.get('description', '')
                    
                    # Create paragraphs with proper Japanese formatting
                    name_para = self._create_table_paragraph(name)
                    desc_para = self._create_table_paragraph(description)
                    
                    # Get currency symbol from quote data
                    currency_symbol = quote_data.get('currency_symbol', '$')
                    
                    table_data.append([
                        name_para,
                        desc_para,
                        str(item.get('quantity', 1)),
                        f"{currency_symbol}{item.get('unit_price', 0):,.2f}",
                        f"{currency_symbol}{item.get('total_price', 0):,.2f}"
                    ])
                
                # Create table with adjusted column widths
                items_table = Table(table_data, colWidths=[1.2*inch, 3*inch, 0.6*inch, 0.8*inch, 0.9*inch])
                items_table.setStyle(TableStyle([
                    # Header styling
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # Data styling
                    ('FONTNAME', (0, 1), (-1, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Right align numbers
                    ('ALIGN', (0, 1), (1, -1), 'LEFT'),    # Left align text
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),   # Top align for better text wrapping
                    
                    # Grid
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    
                    # Alternating row colors
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                    
                    # Add padding for better readability
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ]))
                
                # Enable automatic row splitting for long content
                items_table.repeatRows = 1  # Repeat header row on new pages
                story.append(items_table)
                story.append(Spacer(1, 20))
            
            # Pricing summary
            currency = quote_data.get('currency', 'USD')
            currency_symbol = quote_data.get('currency_symbol', '$')
            subtotal = quote_data.get('subtotal', 0)
            tax_amount = quote_data.get('tax_amount', 0)
            total = quote_data.get('total', 0)
            
            pricing_data = [
                [labels.get('subtotal', 'Subtotal:'), f"{currency_symbol}{subtotal:,.2f}"],
                [labels.get('tax', 'Tax:'), f"{currency_symbol}{tax_amount:,.2f}"],
                [labels.get('total_amount', 'Total:'), f"{currency_symbol}{total:,.2f}"]
            ]
            
            pricing_table = Table(pricing_data, colWidths=[4*inch, 2*inch])
            pricing_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, 1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica'),
                ('FONTNAME', (1, 2), (1, 2), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('FONTSIZE', (1, 2), (1, 2), 12),  # Larger total
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LINEBELOW', (0, 1), (-1, 1), 1, colors.black),  # Line above total
            ]))
            story.append(pricing_table)
            story.append(Spacer(1, 30))
            
            # Terms and conditions
            terms = quote_data.get('terms_and_conditions', [])
            if terms:
                story.append(Paragraph(labels.get('terms_and_conditions', 'Terms and Conditions'), self.styles['SectionHeader']))
                for term in terms:
                    story.append(Paragraph(f"• {term}", self.styles['JapaneseText']))
                story.append(Spacer(1, 15))
            
            # Implementation notes
            implementation_notes = quote_data.get('implementation_notes', [])
            if implementation_notes:
                story.append(Paragraph(labels.get('implementation_notes', 'Implementation Notes'), self.styles['SectionHeader']))
                for note in implementation_notes:
                    story.append(Paragraph(f"• {note}", self.styles['JapaneseText']))
                story.append(Spacer(1, 15))
            
            # Next steps
            next_steps = quote_data.get('next_steps', [])
            if next_steps:
                story.append(Paragraph(labels.get('next_steps', 'Next Steps'), self.styles['SectionHeader']))
                for step in next_steps:
                    story.append(Paragraph(f"• {step}", self.styles['JapaneseText']))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            print(f"❌ PDF generation error: {str(e)}")
            raise e
    
    def save_pdf_to_file(self, quote_data: Dict[str, Any], filename: str = None) -> str:
        """Save PDF to file and return the file path"""
        if filename is None:
            quote_id = quote_data.get('quote_id', 'quote')
            filename = f"quote_{quote_id}.pdf"
        
        # Update styles based on quote language
        language = quote_data.get('language', 'en')
        self.update_styles_for_language(language)
        
        # Ensure the quotes directory exists
        quotes_dir = Path("Data/quotes")
        quotes_dir.mkdir(exist_ok=True)
        
        file_path = quotes_dir / filename
        
        # Generate PDF
        pdf_buffer = self.generate_quote_pdf(quote_data)
        
        # Save to file
        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        return str(file_path)

# Test function to verify Japanese font support
def test_japanese_fonts():
    """Test Japanese font rendering"""
    test_data = {
    "quote_number": "Q-20240627-001",
    "title": "Quote for DDR4 16GB (8GBx2) Laptop Memory Modules",
    "company_tagline": "Reliable and Cost-Effective Memory Solutions for Your Laptop",
    "customer_info": {
        "company_name": "Unknown",
        "contact_name": "Unknown",
        "email": "unknown@example.com",
        "phone": None,
        "address": None
    },
    "business_context": "The customer requires reliable and cost-effective DDR4 laptop memory modules with 16GB total capacity (8GBx2) for programming and light video editing tasks. Stability and performance are prioritized, with a budget range of 7,000 to 10,000 JPY. The customer prefers trusted brands with good cost performance and requests a quick quote within 1-2 days.",
    "line_items": [
        {
        "name": "Crucial 16GB Kit (8GBx2) DDR4 3200MHz Laptop Memory",
        "description": "Reliable DDR4 3200MHz memory kit suitable for programming and video editing, offering stable performance and excellent cost efficiency.",
        "quantity": 1,
        "unit_price": 4800.0,
        "total_price": 4800.0,
        "category": "Hardware"
        },
        {
        "name": "Kingston 16GB Kit (8GBx2) DDR4 2666MHz Laptop Memory",
        "description": "Trusted Kingston DDR4 memory kit with 2666MHz speed, optimized for stability and cost performance, ideal for everyday programming and multimedia tasks.",
        "quantity": 1,
        "unit_price": 5200.0,
        "total_price": 5200.0,
        "category": "Hardware"
        }
    ],
    "financials": {
        "subtotal": 10000.0,
        "tax_rate": 0.08,
        "tax_amount": 800.0,
        "total": 10800.0,
        "currency": "JPY"
    },
    "terms_and_conditions": [
        "Prices are valid for 30 days from the quote date.",
        "Payment terms: 30 days net from invoice date.",
        "Warranty: Standard manufacturer warranty applies to all products.",
        "Delivery: Estimated delivery within 5 business days after order confirmation.",
        "Returns: Returns accepted within 14 days of delivery if products are unopened and in original packaging."
    ],
    "implementation_notes": [
        "Confirm compatibility of memory modules with the customer's laptop model before purchase.",
        "Installation can be performed by the customer or a professional technician.",
        "Ensure BIOS is updated to support the new memory modules for optimal performance."
    ],
    "next_steps": [
        "Review the proposed memory options and select preferred product.",
        "Confirm order details and provide shipping information.",
        "Process payment to initiate order fulfillment.",
        "Schedule delivery and installation as needed."
    ],
    "valid_until": "2024-07-27",
    "created_at": "2024-06-27",
    "language": "en",
    "quote_id": "001",
    "generation_method": "pydantic_structured_internationalized",
    "data_source": "conversation_only",
    "pdf_generated": True,
    "pdf_path": "Data/quotes/quote_001_en.pdf",
    "pdf_url": "/api/quotes/download-pdf/001",
    "file_size": 13458,
    }
    
    generator = PDFGenerator()
    pdf_path = generator.save_pdf_to_file(test_data, 'japanese_test.pdf')
    print(f"✅ Japanese test PDF saved to: {pdf_path}")

if __name__ == "__main__":
    test_japanese_fonts()