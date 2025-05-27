from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime
from typing import Dict, Any
import os
from pathlib import Path

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom styles for the PDF"""
        # Company header style
        self.styles.add(ParagraphStyle(
            name='CompanyHeader',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2E4057'),
            alignment=TA_CENTER,
            spaceAfter=30
        ))
        
        # Quote title style
        self.styles.add(ParagraphStyle(
            name='QuoteTitle',
            parent=self.styles['Heading2'],
            fontSize=18,
            textColor=colors.HexColor('#048A81'),
            alignment=TA_LEFT,
            spaceAfter=20
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
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
            fontSize=8,
            leading=10
        ))
    
    def generate_quote_pdf(self, quote_data: Dict[str, Any]) -> BytesIO:
        """Generate a professional PDF quotation"""
        print(f"DEBUG: PDF Generator received quote with keys: {list(quote_data.keys())}")
        
        if 'line_items' in quote_data:
            print(f"DEBUG: Line items count: {len(quote_data['line_items'])}")
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        story = []
        
        try:
            # Company Header
            story.append(Paragraph("Otsuka Corporation", self.styles['CompanyHeader']))
            story.append(Paragraph("Professional Business Hardware Solutions", self.styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Quote Header
            story.append(Paragraph("HARDWARE QUOTATION", self.styles['QuoteTitle']))
            
            # Quote Info Table
            quote_number = quote_data.get('quote_number', quote_data.get('id', 'N/A'))
            quote_info_data = [
                ['Quote Number:', quote_number],
                ['Date:', datetime.fromisoformat(quote_data.get('created_at', datetime.now().isoformat())).strftime('%B %d, %Y')],
                ['Valid Until:', datetime.fromisoformat(quote_data.get('valid_until', datetime.now().isoformat())).strftime('%B %d, %Y')],
            ]
            
            quote_info_table = Table(quote_info_data, colWidths=[1.5*inch, 3*inch])
            quote_info_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(quote_info_table)
            story.append(Spacer(1, 15))
            
            # Customer Information
            customer_info = quote_data.get('customer_info', {})
            if customer_info.get('company_name'):
                story.append(Paragraph("Customer Information", self.styles['SectionHeader']))
                
                customer_data = []
                if customer_info.get('company_name'):
                    customer_data.append(['Company:', customer_info['company_name']])
                if customer_info.get('contact_name'):
                    customer_data.append(['Contact:', customer_info['contact_name']])
                if customer_info.get('email'):
                    customer_data.append(['Email:', customer_info['email']])
                if customer_info.get('industry'):
                    customer_data.append(['Industry:', customer_info['industry']])
                
                if customer_data:
                    customer_table = Table(customer_data, colWidths=[1.5*inch, 4*inch])
                    customer_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    story.append(customer_table)
                    story.append(Spacer(1, 15))
            
            # Hardware Items Table
            story.append(Paragraph("Recommended Hardware Solution", self.styles['SectionHeader']))
            
            line_items = quote_data.get('line_items', [])
            if line_items:
                # Table headers
                hardware_data = [['Item', 'Description', 'Qty', 'Unit Price', 'Total']]
                
                for item in line_items:
                    # Clean and format the description
                    description = item.get('description', 'N/A')
                    
                    # Add specifications in a cleaner format
                    specs = item.get('specifications', {})
                    if specs:
                        spec_lines = []
                        for key, value in specs.items():
                            spec_lines.append(f"{key}: {value}")
                        if spec_lines:
                            description += f"\nSpecs: {', '.join(spec_lines)}"
                    
                    # Wrap description in Paragraph for proper text handling
                    desc_paragraph = Paragraph(description, self.styles['TableCell'])
                    
                    hardware_data.append([
                        Paragraph(item.get('name', 'N/A'), self.styles['TableCell']),
                        desc_paragraph,
                        str(item.get('quantity', 1)),
                        f"${item.get('unit_price', 0):,.2f}",
                        f"${item.get('total_price', 0):,.2f}"
                    ])
                
                # Create table with proper column widths
                hardware_table = Table(
                    hardware_data, 
                    colWidths=[1.8*inch, 2.8*inch, 0.5*inch, 0.9*inch, 0.9*inch],
                    repeatRows=1  # Repeat header on new pages
                )
                
                hardware_table.setStyle(TableStyle([
                    # Header styling
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#048A81')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    
                    # Data styling
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),   # Item name - left
                    ('ALIGN', (1, 1), (1, -1), 'LEFT'),   # Description - left
                    ('ALIGN', (2, 1), (2, -1), 'CENTER'), # Qty - center
                    ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # Unit price - right
                    ('ALIGN', (4, 1), (4, -1), 'RIGHT'),  # Total - right
                    
                    # Cell padding and borders
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    
                    # Grid
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#048A81')),
                    
                    # Row colors for better readability
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
                ]))
                
                story.append(hardware_table)
            
            story.append(Spacer(1, 20))
            
            # Pricing Summary
            story.append(Paragraph("Investment Summary", self.styles['SectionHeader']))
            
            pricing = quote_data.get('pricing', {})
            pricing_data = [
                ['Subtotal:', f"${pricing.get('subtotal', 0):,.2f}"],
                ['Tax ({:.1f}%):'.format(pricing.get('tax_rate', 0) * 100), f"${pricing.get('tax_amount', 0):,.2f}"],
                ['', ''],  # Spacer row
                ['Total Investment:', f"${pricing.get('total', 0):,.2f}"],
            ]
            
            pricing_table = Table(pricing_data, colWidths=[3*inch, 1.5*inch])
            pricing_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -2), 'Helvetica'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Bold total row
                ('FONTSIZE', (0, 0), (-1, -2), 11),
                ('FONTSIZE', (0, -1), (-1, -1), 14),  # Larger total
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),  # Line above total
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F0F8F0')),  # Light green for total
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#2E7D32')),  # Dark green text
            ]))
            story.append(pricing_table)
            story.append(Spacer(1, 20))
            
            # Terms and Conditions
            story.append(Paragraph("Terms and Conditions", self.styles['SectionHeader']))
            
            terms = quote_data.get('terms', [])
            for i, term in enumerate(terms, 1):
                story.append(Paragraph(f"{i}. {term}", self.styles['Normal']))
                story.append(Spacer(1, 4))
            
            # Notes
            notes = quote_data.get('notes', [])
            if notes:
                story.append(Spacer(1, 15))
                story.append(Paragraph("Additional Notes", self.styles['SectionHeader']))
                for note in notes:
                    story.append(Paragraph(f"• {note}", self.styles['Normal']))
                    story.append(Spacer(1, 3))
            
            story.append(Spacer(1, 25))
            
            # Footer
            story.append(Paragraph("Thank you for considering our hardware solutions. We look forward to supporting your business technology needs!", self.styles['Normal']))
            story.append(Spacer(1, 15))
            story.append(Paragraph("For questions about this quote, please contact us at sales@techsolutions.com or call (555) 123-4567", self.styles['SmallText']))
            
            # Build PDF
            print(f"DEBUG: Building PDF with {len(story)} elements")
            doc.build(story)
            buffer.seek(0)
            print(f"DEBUG: PDF buffer size: {len(buffer.getvalue())} bytes")
            
        except Exception as e:
            print(f"DEBUG: Error building PDF: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        return buffer
    
    def save_pdf_to_file(self, quote_data: Dict[str, Any], filename: str = None) -> str:
        """Save PDF to file and return the file path"""
        if filename is None:
            quote_id = quote_data.get('id', 'quote')
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