from io import BytesIO
import re
import requests
from pathlib import Path
from typing import Any, Dict
from datetime import datetime, timedelta
import os
from services.language_service import LanguageService
import logging

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                  Spacer, Table, TableStyle)

logger = logging.getLogger(__name__)

# If you use 'font_url', define it or import it as well:
font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansJP-Regular.otf"

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.japanese_font_registered = False
        self._register_japanese_fonts()
        self._setup_custom_styles()
        self.language_service = LanguageService()
        self._setup_localized_labels()
    
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
        """Detect the primary language of the quote content with explicit override support"""
        try:
            # PRIORITY 1: Check for explicit language setting (your approach)
            explicit_language = quote_data.get('language')
            if explicit_language and explicit_language in self.labels:
                logger.info(f"🌐 Using explicit language setting: {explicit_language}")
                return explicit_language
            
            # PRIORITY 2: Auto-detect from content (other branch approach)
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
                
                logger.info(f"🌐 Auto-detected language: {detected_language} (confidence: {confidence:.2f})")
                
                # Only use detected language if confidence is high and language is supported
                if confidence > 0.7 and detected_language in self.labels:
                    logger.info(f"✅ Using auto-detected language: {detected_language}")
                    return detected_language
                else:
                    logger.warning(f"⚠️ Low confidence or unsupported auto-detected language: {detected_language}")
            else:
                logger.warning("⚠️ No text content found for language detection")
                
            # PRIORITY 3: Check user context language (fallback)
            customer_info = quote_data.get('customer_info', {})
            context_language = customer_info.get('language') or customer_info.get('preferred_language')
            if context_language and context_language in self.labels:
                logger.info(f"🌐 Using customer context language: {context_language}")
                return context_language
            
            # PRIORITY 4: Default to English
            logger.info("🌐 Falling back to default language: en")
            return 'en'
                
        except Exception as e:
            logger.error(f"❌ Language detection failed: {e}, using English")
            return 'en'

    def _get_localized_labels(self, language: str) -> Dict[str, str]:
        """Get localized labels for the specified language with fallback"""
        try:
            # Try to get labels for requested language
            if language in self.labels:
                return self.labels[language]
            
            # Log warning and fall back to English
            logger.warning(f"⚠️ Language {language} not supported, falling back to English")
            return self.labels.get('en', {
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
            })
        except Exception as e:
            logger.error(f"❌ Error getting localized labels: {e}")
            return self.labels.get('en', {})

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
                ('FONTNAME', (0, 0), (0, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica'),
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
                        ('FONTNAME', (0, 0), (0, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'JapaneseFont' if (self.japanese_font_registered and quote_data.get('language') == 'ja') else 'Helvetica'),
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
            
            # Pricing summary with localized labels and currency formatting
            currency = quote_data.get('currency', 'USD')
            currency_symbol = quote_data.get('currency_symbol', '$')
            subtotal = quote_data.get('subtotal', 0)
            tax_amount = quote_data.get('tax_amount', 0)
            total = quote_data.get('total', 0)
            
            pricing_data = [
                [labels['subtotal'], self._format_currency(quote_data.get('subtotal', 0), language, currency)],
                [labels['tax'], self._format_currency(quote_data.get('tax_amount', 0), language, currency)],
                [labels['total_amount'], self._format_currency(quote_data.get('total', 0), language, currency)]
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
            
            # Terms and conditions with localized header
            terms = quote_data.get('terms_and_conditions', [])
            if terms:
                story.append(Paragraph(labels['terms_and_conditions'], self.styles['Heading2']))
                for term in terms:
                    story.append(Paragraph(f"• {term}", self.styles['JapaneseText']))
                story.append(Spacer(1, 15))
            
            # Implementation notes with localized header
            implementation_notes = quote_data.get('implementation_notes', [])
            if implementation_notes:
                story.append(Paragraph(labels['implementation_notes'], self.styles['Heading2']))
                for note in implementation_notes:
                    story.append(Paragraph(f"• {note}", self.styles['JapaneseText']))
                story.append(Spacer(1, 15))
            
            # Next steps with localized header
            next_steps = quote_data.get('next_steps', [])
            if next_steps:
                story.append(Paragraph(labels['next_steps'], self.styles['Heading2']))
                for step in next_steps:
                    story.append(Paragraph(f"• {step}", self.styles['JapaneseText']))
            
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
        
        # Update styles based on quote language
        language = quote_data.get('language', 'en')
        self.update_styles_for_language(language)
        
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
=======
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
>>>>>>> 76756e64cf6aae5fc409c305c75140d75a58391b
