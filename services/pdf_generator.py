from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import os
from pathlib import Path
from services.language_service import LanguageService
import logging

logger = logging.getLogger(__name__)

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.language_service = LanguageService()
        self._setup_localized_labels()
    
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
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER
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
        
        # Add custom styles for the new quote format
        self.styles.add(ParagraphStyle(
            name='CompanyTagline',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER,
            spaceAfter=20
        ))

    def _setup_localized_labels(self):
        """Setup localized labels for different languages"""
        self.labels = {
            'en': {
                'quote_number': 'Quote Number:',
                'date': 'Date:',
                'valid_until': 'Valid Until:',
                'customer_information': 'Customer Information',
                'company': 'Company:',
                'contact': 'Contact:',
                'email': 'Email:',
                'phone': 'Phone:',
                'quote_details': 'Quote Details',
                'item': 'Item',
                'description': 'Description',
                'qty': 'Qty',
                'unit_price': 'Unit Price',
                'total': 'Total',
                'subtotal': 'Subtotal:',
                'tax': 'Tax:',
                'total_amount': 'Total:',
                'terms_and_conditions': 'Terms and Conditions',
                'implementation_notes': 'Implementation Notes',
                'next_steps': 'Next Steps',
                'currency_symbol': '$'
            },
            'ja': {
                'quote_number': '見積番号：',
                'date': '日付：',
                'valid_until': '有効期限：',
                'customer_information': '顧客情報',
                'company': '会社名：',
                'contact': '担当者：',
                'email': 'メールアドレス：',
                'phone': '電話番号：',
                'quote_details': '見積詳細',
                'item': '項目',
                'description': '説明',
                'qty': '数量',
                'unit_price': '単価',
                'total': '合計',
                'subtotal': '小計：',
                'tax': '税金：',
                'total_amount': '合計：',
                'terms_and_conditions': '利用規約',
                'implementation_notes': '実装ノート',
                'next_steps': '次のステップ',
                'currency_symbol': '¥'
            },
            'es': {
                'quote_number': 'Número de Cotización:',
                'date': 'Fecha:',
                'valid_until': 'Válido Hasta:',
                'customer_information': 'Información del Cliente',
                'company': 'Empresa:',
                'contact': 'Contacto:',
                'email': 'Correo Electrónico:',
                'phone': 'Teléfono:',
                'quote_details': 'Detalles de la Cotización',
                'item': 'Artículo',
                'description': 'Descripción',
                'qty': 'Cant.',
                'unit_price': 'Precio Unitario',
                'total': 'Total',
                'subtotal': 'Subtotal:',
                'tax': 'Impuesto:',
                'total_amount': 'Total:',
                'terms_and_conditions': 'Términos y Condiciones',
                'implementation_notes': 'Notas de Implementación',
                'next_steps': 'Próximos Pasos',
                'currency_symbol': '$'
            },
            'fr': {
                'quote_number': 'Numéro de Devis:',
                'date': 'Date:',
                'valid_until': 'Valide Jusqu\'au:',
                'customer_information': 'Informations Client',
                'company': 'Entreprise:',
                'contact': 'Contact:',
                'email': 'E-mail:',
                'phone': 'Téléphone:',
                'quote_details': 'Détails du Devis',
                'item': 'Article',
                'description': 'Description',
                'qty': 'Qté',
                'unit_price': 'Prix Unitaire',
                'total': 'Total',
                'subtotal': 'Sous-total:',
                'tax': 'Taxe:',
                'total_amount': 'Total:',
                'terms_and_conditions': 'Termes et Conditions',
                'implementation_notes': 'Notes d\'Implémentation',
                'next_steps': 'Prochaines Étapes',
                'currency_symbol': '€'
            },
            'de': {
                'quote_number': 'Angebotsnummer:',
                'date': 'Datum:',
                'valid_until': 'Gültig bis:',
                'customer_information': 'Kundeninformationen',
                'company': 'Unternehmen:',
                'contact': 'Kontakt:',
                'email': 'E-Mail:',
                'phone': 'Telefon:',
                'quote_details': 'Angebotsdetails',
                'item': 'Artikel',
                'description': 'Beschreibung',
                'qty': 'Menge',
                'unit_price': 'Einzelpreis',
                'total': 'Gesamt',
                'subtotal': 'Zwischensumme:',
                'tax': 'Steuer:',
                'total_amount': 'Gesamt:',
                'terms_and_conditions': 'Geschäftsbedingungen',
                'implementation_notes': 'Implementierungshinweise',
                'next_steps': 'Nächste Schritte',
                'currency_symbol': '€'
            },
            'it': {
                'quote_number': 'Numero Preventivo:',
                'date': 'Data:',
                'valid_until': 'Valido Fino al:',
                'customer_information': 'Informazioni Cliente',
                'company': 'Azienda:',
                'contact': 'Contatto:',
                'email': 'Email:',
                'phone': 'Telefono:',
                'quote_details': 'Dettagli Preventivo',
                'item': 'Articolo',
                'description': 'Descrizione',
                'qty': 'Qtà',
                'unit_price': 'Prezzo Unitario',
                'total': 'Totale',
                'subtotal': 'Subtotale:',
                'tax': 'Tasse:',
                'total_amount': 'Totale:',
                'terms_and_conditions': 'Termini e Condizioni',
                'implementation_notes': 'Note di Implementazione',
                'next_steps': 'Prossimi Passi',
                'currency_symbol': '€'
            },
            'pt': {
                'quote_number': 'Número da Cotação:',
                'date': 'Data:',
                'valid_until': 'Válido Até:',
                'customer_information': 'Informações do Cliente',
                'company': 'Empresa:',
                'contact': 'Contato:',
                'email': 'E-mail:',
                'phone': 'Telefone:',
                'quote_details': 'Detalhes da Cotação',
                'item': 'Item',
                'description': 'Descrição',
                'qty': 'Qtd',
                'unit_price': 'Preço Unitário',
                'total': 'Total',
                'subtotal': 'Subtotal:',
                'tax': 'Imposto:',
                'total_amount': 'Total:',
                'terms_and_conditions': 'Termos e Condições',
                'implementation_notes': 'Notas de Implementação',
                'next_steps': 'Próximos Passos',
                'currency_symbol': 'R$'
            }
        }

    def _detect_quote_language(self, quote_data: Dict[str, Any]) -> str:
        """Detect the primary language of the quote content"""
        try:
            # Collect text content for language detection
            text_content = []
            
            # Add quote title and tagline
            if quote_data.get('quote_title'):
                text_content.append(quote_data['quote_title'])
            if quote_data.get('company_tagline'):
                text_content.append(quote_data['company_tagline'])
            
            # Add line item descriptions
            line_items = quote_data.get('line_items', [])
            for item in line_items:
                if item.get('name'):
                    text_content.append(item['name'])
                if item.get('description'):
                    text_content.append(item['description'])
            
            # Add terms and conditions
            terms = quote_data.get('terms_and_conditions', [])
            text_content.extend(terms)
            
            # Add implementation notes
            notes = quote_data.get('implementation_notes', [])
            text_content.extend(notes)
            
            # Add next steps
            steps = quote_data.get('next_steps', [])
            text_content.extend(steps)
            
            # Combine all text for detection
            combined_text = ' '.join(text_content)
            
            if combined_text.strip():
                # Use language service to detect language
                detection_result = self.language_service.detect_language(combined_text)
                detected_language = detection_result['primary_language']
                confidence = detection_result['primary_confidence']
                
                logger.info(f"🌐 PDF Language Detection: {detected_language} (confidence: {confidence:.2f})")
                
                # Only use detected language if confidence is high and language is supported
                if confidence > 0.7 and detected_language in self.labels:
                    return detected_language
                else:
                    logger.warning(f"⚠️ Low confidence or unsupported language: {detected_language}, using English")
                    return 'en'
            else:
                logger.warning("⚠️ No text content found for language detection, using English")
                return 'en'
                
        except Exception as e:
            logger.error(f"❌ Language detection failed: {e}, using English")
            return 'en'

    def _get_localized_labels(self, language: str) -> Dict[str, str]:
        """Get localized labels for the specified language"""
        return self.labels.get(language, self.labels['en'])

    def _format_currency(self, amount: float, language: str, currency: str = None) -> str:
        """Format currency amount based on language and currency"""
        if currency and currency.upper() in ['JPY', 'YEN']:
            # Japanese Yen - no decimal places
            return f"¥{amount:,.0f}"
        elif currency and currency.upper() in ['EUR', 'EURO']:
            # Euro
            return f"€{amount:,.2f}"
        elif language == 'ja':
            # Japanese - use Yen format
            return f"¥{amount:,.0f}"
        elif language in ['de', 'fr', 'it'] and not currency:
            # European languages default to Euro
            return f"€{amount:,.2f}"
        elif language == 'pt':
            # Portuguese - Brazilian Real
            return f"R${amount:,.2f}"
        else:
            # Default to USD format
            return f"${amount:,.2f}"
    
    def generate_quote_pdf(self, quote_data: Dict[str, Any]) -> BytesIO:
        """Generate PDF from quote data with multilingual support"""
        buffer = BytesIO()
        
        try:
            # Detect language from quote content
            auto_detected_language = self._detect_quote_language(quote_data)
            
            # Use provided language or auto-detected language
            language = quote_data.get('language', auto_detected_language)
            if language not in self.labels:
                logger.warning(f"⚠️ Unsupported language: {language}, using English")
                language = 'en'
            
            logger.info(f"📄 Generating PDF in language: {language}")
            
            # Get localized labels
            labels = self._get_localized_labels(language)
            
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
            
            # Quote information with localized labels
            quote_info = [
                [labels['quote_number'], quote_data.get('quote_number', 'N/A')],
                [labels['date'], quote_data.get('created_at', '')[:10] if quote_data.get('created_at') else 'N/A'],
                [labels['valid_until'], quote_data.get('valid_until', '')[:10] if quote_data.get('valid_until') else 'N/A'],
            ]
            
            quote_table = Table(quote_info, colWidths=[2*inch, 3*inch])
            quote_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(quote_table)
            story.append(Spacer(1, 20))
            
            # Customer information with localized labels
            customer_info = quote_data.get('customer_info', {})
            if customer_info:
                story.append(Paragraph(labels['customer_information'], self.styles['Heading2']))
                
                customer_data = []
                if customer_info.get('company'):
                    customer_data.append([labels['company'], customer_info['company']])
                if customer_info.get('contact'):
                    customer_data.append([labels['contact'], customer_info['contact']])
                if customer_info.get('email'):
                    customer_data.append([labels['email'], customer_info['email']])
                if customer_info.get('phone'):
                    customer_data.append([labels['phone'], customer_info['phone']])
                
                if customer_data:
                    customer_table = Table(customer_data, colWidths=[2*inch, 3*inch])
                    customer_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]))
                    story.append(customer_table)
                story.append(Spacer(1, 20))
            
            # Line items with localized headers
            story.append(Paragraph(labels['quote_details'], self.styles['Heading2']))
            
            line_items = quote_data.get('line_items', [])
            if line_items:
                # Create table headers with localized labels
                table_data = [[
                    labels['item'], 
                    labels['description'], 
                    labels['qty'], 
                    labels['unit_price'], 
                    labels['total']
                ]]
                
                # Add line items with proper currency formatting
                currency = quote_data.get('currency', 'USD')
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
                        self._format_currency(item.get('unit_price', 0), language, currency),
                        self._format_currency(item.get('total_price', 0), language, currency)
                    ])
                
                # Create table with adjusted column widths
                items_table = Table(table_data, colWidths=[1.2*inch, 3*inch, 0.6*inch, 0.8*inch, 0.9*inch])
                items_table.setStyle(TableStyle([
                    # Header styling
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # Data styling
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
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
            
            # Pricing summary with localized labels and currency formatting
            currency = quote_data.get('currency', 'USD')
            pricing_data = [
                [labels['subtotal'], self._format_currency(quote_data.get('subtotal', 0), language, currency)],
                [labels['tax'], self._format_currency(quote_data.get('tax_amount', 0), language, currency)],
                [labels['total_amount'], self._format_currency(quote_data.get('total', 0), language, currency)]
            ]
            
            pricing_table = Table(pricing_data, colWidths=[4*inch, 2*inch])
            pricing_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, 1), 'Helvetica'),
                ('FONTNAME', (1, 2), (1, 2), 'Helvetica-Bold'),  # Bold total
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('FONTSIZE', (1, 2), (1, 2), 12),  # Larger total
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LINEBELOW', (0, 1), (-1, 1), 1, colors.black),  # Line above total
            ]))
            story.append(pricing_table)
            story.append(Spacer(1, 30))
            
            # Terms and conditions with localized header
            terms = quote_data.get('terms_and_conditions', [])
            if terms:
                story.append(Paragraph(labels['terms_and_conditions'], self.styles['Heading2']))
                for term in terms:
                    story.append(Paragraph(f"• {term}", self.styles['Normal']))
                story.append(Spacer(1, 15))
            
            # Implementation notes with localized header
            implementation_notes = quote_data.get('implementation_notes', [])
            if implementation_notes:
                story.append(Paragraph(labels['implementation_notes'], self.styles['Heading2']))
                for note in implementation_notes:
                    story.append(Paragraph(f"• {note}", self.styles['Normal']))
                story.append(Spacer(1, 15))
            
            # Next steps with localized header
            next_steps = quote_data.get('next_steps', [])
            if next_steps:
                story.append(Paragraph(labels['next_steps'], self.styles['Heading2']))
                for step in next_steps:
                    story.append(Paragraph(f"• {step}", self.styles['Normal']))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            logger.info(f"✅ PDF generated successfully in {language}")
            return buffer
            
        except Exception as e:
            logger.error(f"❌ PDF generation error: {str(e)}")
            raise e
    
    def save_pdf_to_file(self, quote_data: Dict[str, Any], filename: str = None) -> str:
        """Save PDF to file and return the file path with multilingual support"""
        if filename is None:
            quote_id = quote_data.get('quote_id', 'quote')
            language = quote_data.get('language', 'en')
            filename = f"quote_{quote_id}_{language}.pdf"
        
        # Ensure the quotes directory exists
        quotes_dir = Path("Data/quotes")
        quotes_dir.mkdir(exist_ok=True)
        
        file_path = quotes_dir / filename
        
        # Generate PDF with multilingual support
        pdf_buffer = self.generate_quote_pdf(quote_data)
        
        # Save to file
        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        logger.info(f"📄 PDF saved to: {file_path}")
        return str(file_path)

    def get_supported_languages(self) -> list:
        """Get list of supported languages for PDF generation"""
        return list(self.labels.keys())

    def get_language_info(self) -> Dict[str, Any]:
        """Get comprehensive language support information"""
        return {
            "supported_languages": self.get_supported_languages(),
            "auto_detection_enabled": True,
            "language_service": "LanguageService with langdetect",
            "default_language": "en",
            "localized_elements": [
                "headers", "labels", "currency_formatting", 
                "date_formatting", "section_titles"
            ],
            "currency_support": {
                "en": "USD ($)",
                "ja": "JPY (¥)",
                "es": "USD ($)",
                "fr": "EUR (€)",
                "de": "EUR (€)",
                "it": "EUR (€)",
                "pt": "BRL (R$)"
            }
        } 