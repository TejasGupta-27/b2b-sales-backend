from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime, timedelta
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
        """Generate a professional PDF quotation with dynamic content"""
        print(f"🔍 PDF DEBUG: Quote data keys: {list(quote_data.keys())}")
        
        if 'line_items' in quote_data:
            print(f"🔍 PDF DEBUG: Line items count: {len(quote_data['line_items'])}")
            for i, item in enumerate(quote_data['line_items'][:3]):  # Show first 3 items
                print(f"🔍 PDF DEBUG: Item {i}: {item.get('name', 'NO NAME')} - ${item.get('unit_price', 0)}")
        
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
            # FIXED: Dynamic Company Header (Your company name, not customer's)
            seller_company = quote_data.get('seller_company_name', 'Otsuka-Shokai')
            seller_tagline = quote_data.get('seller_tagline', 'Professional Technology Solutions')
            
            print(f"🔍 PDF DEBUG: Using company name: {seller_company}")
            
            story.append(Paragraph(seller_company, self.styles['CompanyHeader']))
            story.append(Paragraph(seller_tagline, self.styles['Normal']))
            story.append(Spacer(1, 20))
            
            # FIXED: Dynamic Quote Title
            quote_title = quote_data.get('quote_title', 'TECHNOLOGY SOLUTION QUOTATION')
            print(f"🔍 PDF DEBUG: Quote title: {quote_title}")
            story.append(Paragraph(quote_title, self.styles['QuoteTitle']))
            
            # Quote Info Table
            quote_number = quote_data.get('quote_number', quote_data.get('id', 'N/A'))
            created_date = quote_data.get('created_at', datetime.now().isoformat())
            valid_until = quote_data.get('valid_until', datetime.now().isoformat())
            
            # Parse dates properly
            try:
                if isinstance(created_date, str):
                    created_dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                else:
                    created_dt = created_date
                    
                if isinstance(valid_until, str):
                    valid_dt = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
                else:
                    valid_dt = valid_until
            except:
                created_dt = datetime.now()
                valid_dt = datetime.now() + timedelta(days=30)
            
            quote_info_data = [
                ['Quote Number:', quote_number],
                ['Date:', created_dt.strftime('%B %d, %Y')],
                ['Valid Until:', valid_dt.strftime('%B %d, %Y')],
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
            
            # FIXED: Dynamic Customer Information
            customer_info = quote_data.get('customer_info', {})
            print(f"🔍 PDF DEBUG: Customer info keys: {list(customer_info.keys())}")
            
            if customer_info:
                story.append(Paragraph("Customer Information", self.styles['SectionHeader']))
                
                customer_data = []
                if customer_info.get('company_name'):
                    customer_data.append(['Company:', customer_info['company_name']])
                if customer_info.get('contact_name'):
                    customer_data.append(['Contact:', customer_info['contact_name']])
                if customer_info.get('email'):
                    customer_data.append(['Email:', customer_info['email']])
                if customer_info.get('phone'):
                    customer_data.append(['Phone:', customer_info['phone']])
                if customer_info.get('industry'):
                    customer_data.append(['Industry:', customer_info['industry']])
                
                print(f"🔍 PDF DEBUG: Customer data rows: {len(customer_data)}")
                
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
            
            # FIXED: Hardware Items Table with ACTUAL DATA
            items_title = quote_data.get('items_section_title', 'Recommended Solution')
            story.append(Paragraph(items_title, self.styles['SectionHeader']))
            
            line_items = quote_data.get('line_items', [])
            print(f"🔍 PDF DEBUG: Processing {len(line_items)} line items")
            
            if line_items:
                # Table headers
                hardware_data = [['Item', 'Description', 'Qty', 'Unit Price', 'Total']]
                
                for i, item in enumerate(line_items):
                    print(f"🔍 PDF DEBUG: Processing item {i}: {item}")
                    
                    # Get item data with fallbacks
                    name = item.get('name') or item.get('product_name') or f"Item {i+1}"
                    description = item.get('description') or item.get('product_description') or 'No description'
                    quantity = item.get('quantity', 1)
                    unit_price = float(item.get('unit_price') or item.get('price') or 0)
                    total_price = float(item.get('total_price') or (unit_price * quantity))
                    
                    # Add specifications if available
                    specs = item.get('specifications', {})
                    if specs and isinstance(specs, dict):
                        spec_lines = []
                        for key, value in list(specs.items())[:3]:  # Limit to 3 specs
                            spec_lines.append(f"{key}: {value}")
                        if spec_lines:
                            description += f"\n• {' • '.join(spec_lines)}"
                    
                    # Wrap description in Paragraph for proper text handling
                    desc_paragraph = Paragraph(description, self.styles['TableCell'])
                    
                    hardware_data.append([
                        Paragraph(name, self.styles['TableCell']),
                        desc_paragraph,
                        str(quantity),
                        f"${unit_price:,.2f}",
                        f"${total_price:,.2f}"
                    ])
                    
                    print(f"🔍 PDF DEBUG: Added row - {name}: ${unit_price} x {quantity} = ${total_price}")
                
                # Create table with proper column widths
                hardware_table = Table(
                    hardware_data, 
                    colWidths=[1.8*inch, 2.8*inch, 0.5*inch, 0.9*inch, 0.9*inch],
                    repeatRows=1
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
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),   # Item name
                    ('ALIGN', (1, 1), (1, -1), 'LEFT'),   # Description
                    ('ALIGN', (2, 1), (2, -1), 'CENTER'), # Qty
                    ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # Unit price
                    ('ALIGN', (4, 1), (4, -1), 'RIGHT'),  # Total
                    
                    # Padding and borders
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    
                    # Grid
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#048A81')),
                    
                    # Alternating row colors
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
                ]))
                
                story.append(hardware_table)
            else:
                # Fallback if no line items
                story.append(Paragraph("No items specified in this quote.", self.styles['Normal']))
            
            story.append(Spacer(1, 20))
            
            # FIXED: Dynamic Pricing Summary
            pricing = quote_data.get('pricing', {})
            subtotal = pricing.get('subtotal', 0)
            tax_amount = pricing.get('tax_amount', 0)
            total = pricing.get('total', subtotal + tax_amount)
            
            print(f"🔍 PDF DEBUG: Pricing - Subtotal: ${subtotal}, Tax: ${tax_amount}, Total: ${total}")
            
            story.append(Paragraph("Investment Summary", self.styles['SectionHeader']))
            
            pricing_data = [
                ['Subtotal:', f"${subtotal:,.2f}"],
                ['Tax:', f"${tax_amount:,.2f}"],
                ['', ''],  # Spacer
                ['Total Investment:', f"${total:,.2f}"],
            ]
            
            pricing_table = Table(pricing_data, colWidths=[3*inch, 1.5*inch])
            pricing_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -3), 'Helvetica'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -3), 11),
                ('FONTSIZE', (0, -1), (-1, -1), 14),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F0F8F0')),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#2E7D32')),
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