from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, Any
import os
from pathlib import Path

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.japanese_font_registered = False
        self._register_japanese_fonts()
        self._setup_custom_styles()
    
    def _register_japanese_fonts(self):
        """Register Japanese fonts for use in PDF"""
        try:
            # Option 1: Use system fonts (Windows/Mac/Linux)
            font_paths = [
                # Windows paths
                r"C:\Windows\Fonts\msgothic.ttc",
                r"C:\Windows\Fonts\msmincho.ttc", 
                r"C:\Windows\Fonts\meiryo.ttc",
                r"C:\Windows\Fonts\NotoSansJP-Regular.ttc",
                # Mac paths
                "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/Library/Fonts/Arial Unicode MS.ttf",
                # Linux paths
                "/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttc",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                # Common locations
                "./fonts/NotoSansJP-Regular.ttf",
                "./fonts/GenShinGothic-Regular.ttf",
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        # Register the font
                        pdfmetrics.registerFont(TTFont('JapaneseFont', font_path))
                        self.japanese_font_registered = True
                        print(f"✅ Japanese font registered: {font_path}")
                        break
                    except Exception as e:
                        print(f"❌ Failed to register font {font_path}: {e}")
                        continue
            
            if not self.japanese_font_registered:
                print("⚠️  No Japanese fonts found. Attempting to download Noto Sans CJK...")
                self._download_noto_font()
                
        except Exception as e:
            print(f"❌ Font registration error: {e}")
    
    def _download_noto_font(self):
        """Download Noto Sans CJK font as fallback"""
        try:
            import requests
            
            # Create fonts directory
            fonts_dir = Path("fonts")
            fonts_dir.mkdir(exist_ok=True)
            
            # Download Noto Sans CJK
            font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansJP-Regular.otf"
            font_path = fonts_dir / "NotoSansJP-Regular.otf"
            
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
            print(f"❌ Failed to download/register font: {e}")
            print("💡 Please manually install a Japanese font or use alternative solution")
    
    def _setup_custom_styles(self):
        """Setup custom styles for the PDF"""
        # Determine font to use
        font_name = 'JapaneseFont' if self.japanese_font_registered else 'Helvetica'
        
        # Company header style
        self.styles.add(ParagraphStyle(
            name='CompanyHeader',
            parent=self.styles['Heading1'],
            fontName=font_name,
            fontSize=24,
            textColor=colors.HexColor('#2E4057'),
            alignment=TA_CENTER,
            spaceAfter=30
        ))
        
        # Quote title style
        self.styles.add(ParagraphStyle(
            name='QuoteTitle',
            parent=self.styles['Heading1'],
            fontName=font_name,
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
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
            quote_info = [
                ['Quote Number:', quote_data.get('quote_number', 'N/A')],
                ['Date:', quote_data.get('created_at', '')[:10] if quote_data.get('created_at') else 'N/A'],
                ['Valid Until:', quote_data.get('valid_until', '')[:10] if quote_data.get('valid_until') else 'N/A'],
            ]
            
            quote_table = Table(quote_info, colWidths=[2*inch, 3*inch])
            quote_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(quote_table)
            story.append(Spacer(1, 20))
            
            # Customer information
            customer_info = quote_data.get('customer_info', {})
            if customer_info:
                story.append(Paragraph('Customer Information', self.styles['Heading2']))
                
                customer_data = []
                if customer_info.get('company'):
                    customer_data.append(['Company:', customer_info['company']])
                if customer_info.get('contact'):
                    customer_data.append(['Contact:', customer_info['contact']])
                if customer_info.get('email'):
                    customer_data.append(['Email:', customer_info['email']])
                if customer_info.get('phone'):
                    customer_data.append(['Phone:', customer_info['phone']])
                
                if customer_data:
                    customer_table = Table(customer_data, colWidths=[2*inch, 3*inch])
                    customer_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]))
                    story.append(customer_table)
                story.append(Spacer(1, 20))
            
            # Line items with better text wrapping
            story.append(Paragraph('Quote Details', self.styles['Heading2']))
            
            line_items = quote_data.get('line_items', [])
            if line_items:
                # Create table headers
                table_data = [['Item', 'Description', 'Qty', 'Unit Price', 'Total']]
                
                # Add line items with text wrapping
                for item in line_items:
                    # Wrap description text in Paragraph for better formatting
                    description = item.get('description', '')
                    if len(description) > 50:  # If description is long, use paragraph style
                        desc_para = Paragraph(description, self.styles['TableCell'])
                    else:
                        desc_para = description
                    
                    table_data.append([
                        Paragraph(item.get('name', ''), self.styles['TableCell']),
                        desc_para,
                        str(item.get('quantity', 1)),
                        f"${item.get('unit_price', 0):,.2f}",
                        f"${item.get('total_price', 0):,.2f}"
                    ])
                
                # Create table with adjusted column widths
                items_table = Table(table_data, colWidths=[1.2*inch, 3*inch, 0.6*inch, 0.8*inch, 0.9*inch])
                items_table.setStyle(TableStyle([
                    # Header styling
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # Data styling
                    ('FONTNAME', (0, 1), (-1, -1), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica'),
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
            pricing_data = [
                ['Subtotal:', f"${quote_data.get('subtotal', 0):,.2f} {currency}"],
                ['Tax:', f"${quote_data.get('tax_amount', 0):,.2f} {currency}"],
                ['Total:', f"${quote_data.get('total', 0):,.2f} {currency}"]
            ]
            
            pricing_table = Table(pricing_data, colWidths=[4*inch, 2*inch])
            pricing_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -1), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, 1), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica'),
                ('FONTNAME', (1, 2), (1, 2), 'JapaneseFont' if self.japanese_font_registered else 'Helvetica-Bold'),
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
                story.append(Paragraph('Terms and Conditions', self.styles['Heading2']))
                for term in terms:
                    story.append(Paragraph(f"• {term}", self.styles['JapaneseText']))
                story.append(Spacer(1, 15))
            
            # Implementation notes
            implementation_notes = quote_data.get('implementation_notes', [])
            if implementation_notes:
                story.append(Paragraph('Implementation Notes', self.styles['Heading2']))
                for note in implementation_notes:
                    story.append(Paragraph(f"• {note}", self.styles['JapaneseText']))
                story.append(Spacer(1, 15))
            
            # Next steps
            next_steps = quote_data.get('next_steps', [])
            if next_steps:
                story.append(Paragraph('Next Steps', self.styles['Heading2']))
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
        'quote_title': 'テクノロジーソリューション見積書',
        'company_tagline': 'プロフェッショナル技術ソリューション',
        'quote_number': 'Q-2024-001',
        'created_at': '2024-01-15',
        'valid_until': '2024-02-15',
        'customer_info': {
            'company': '株式会社テスト',
            'contact': '田中太郎',
            'email': 'tanaka@test.co.jp',
            'phone': '03-1234-5678'
        },
        'line_items': [
            {
                'name': 'ソフトウェア開発',
                'description': 'カスタムソフトウェアの開発とテスト',
                'quantity': 1,
                'unit_price': 500000,
                'total_price': 500000
            }
        ],
        'subtotal': 500000,
        'tax_amount': 50000,
        'total': 550000,
        'currency': 'JPY',
        'terms_and_conditions': [
            '支払いは30日以内にお願いします',
            '仕様変更は別途料金が発生します'
        ]
    }
    
    generator = PDFGenerator()
    pdf_path = generator.save_pdf_to_file(test_data, 'japanese_test.pdf')
    print(f"✅ Japanese test PDF saved to: {pdf_path}")

if __name__ == "__main__":
    test_japanese_fonts()