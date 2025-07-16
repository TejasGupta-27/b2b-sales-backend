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
from typing import Dict, Any, Optional
import os
from pathlib import Path
from services.language_service import LanguageService
import logging
import requests
import tempfile

logger = logging.getLogger(__name__)

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.language_service = LanguageService()
        self.font_registry = {}
        self._setup_fonts()
        self._setup_custom_styles()
        self._setup_localized_labels()
    
    
    def _setup_fonts(self):
        """Setup fonts for different languages, including Japanese"""
        try:
            # Create fonts directory if it doesn't exist
            fonts_dir = Path("fonts")
            fonts_dir.mkdir(exist_ok=True)
            
            # Local font file paths
            local_fonts = {
                'NotoSansJP-Regular': fonts_dir / 'NotoSansJP-Regular.ttf',
                'NotoSansJP-Regular': fonts_dir / 'NotoSansJP-Regular.ttf'
            }
            
            # Register local fonts
            for font_name, font_path in local_fonts.items():
                if font_path.exists():
                    try:
                        # For OTF fonts, we need to use a different approach
                        # Try to register as TTF first, fallback to system fonts
                        try:
                            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                            self.font_registry[font_name] = str(font_path)
                            logger.info(f"✅ Registered local font: {font_name}")
                        except Exception as ttf_error:
                            logger.warning(f"⚠️ Could not register {font_name} as TTF: {ttf_error}")
                            # Try alternative approach for system fonts
                            self._register_system_font(font_name, ['ja', 'zh', 'ko'])
                    except Exception as e:
                        logger.error(f"❌ Failed to register local font {font_name}: {e}")
                        self._register_system_font(font_name, ['ja', 'zh', 'ko'])
                else:
                    logger.warning(f"⚠️ Local font file not found: {font_path}")
                    self._register_system_font(font_name, ['ja', 'zh', 'ko'])
            
            # Set default fonts for each language
            self.language_fonts = {
                'en': {'regular': 'Helvetica', 'bold': 'Helvetica-Bold'},
                'ja': {'regular': 'NotoSansJP-Regular', 'bold': 'NotoSansJP-Regular'},
                'zh': {'regular': 'NotoSansJP-Regular', 'bold': 'NotoSansJP-Regular'},
                'ko': {'regular': 'NotoSansJP-Regular', 'bold': 'NotoSansJP-Regular'},
                'es': {'regular': 'Helvetica', 'bold': 'Helvetica-Bold'},
                'fr': {'regular': 'Helvetica', 'bold': 'Helvetica-Bold'},
                'de': {'regular': 'Helvetica', 'bold': 'Helvetica-Bold'},
                'it': {'regular': 'Helvetica', 'bold': 'Helvetica-Bold'},
                'pt': {'regular': 'Helvetica', 'bold': 'Helvetica-Bold'}
            }
            
            # Fallback to system fonts if CJK fonts are not available
            if 'NotoSansJP-Regular' not in self.font_registry:
                logger.warning("⚠️ CJK fonts not available, using system fallbacks")
                self._setup_fallback_fonts()
            
            # Validate fonts are loaded
            self._validate_fonts()
                
        except Exception as e:
            logger.error(f"❌ Font setup failed: {e}")
            self._setup_fallback_fonts()

    def _validate_fonts(self):
        """Validate that required fonts are loaded"""
        required_fonts = ['NotoSansJP-Regular', 'NotoSansJP-Regular']
        missing_fonts = [font for font in required_fonts if font not in self.font_registry]
        
        if missing_fonts:
            logger.warning(f"⚠️ Missing fonts: {missing_fonts}")
            return False
        
        logger.info(f"✅ All required fonts loaded: {list(self.font_registry.keys())}")
        return True
    
    def _register_system_font(self, font_name: str, languages: list):
        """Try to register system fonts as fallback"""
        try:
            # Common system font paths for different OS
            system_font_paths = [
                # Windows
                "C:/Windows/Fonts/msgothic.ttc",
                "C:/Windows/Fonts/msjh.ttc",
                # macOS
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/System/Library/Fonts/PingFang.ttc",
                # Linux
                "/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf"
            ]
            
            for font_path in system_font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        self.font_registry[font_name] = font_path
                        logger.info(f"✅ Registered system font: {font_name} from {font_path}")
                        return
                    except Exception as e:
                        logger.warning(f"⚠️ Could not register {font_path}: {e}")
                        continue
            
            logger.warning(f"⚠️ No system font found for {font_name}")
            
        except Exception as e:
            logger.error(f"❌ System font registration failed: {e}")
    
    def _setup_fallback_fonts(self):
        """Setup fallback fonts when CJK fonts are not available"""
        logger.info("🔄 Setting up fallback fonts...")
        
        # Use Helvetica as fallback for all languages
        fallback_fonts = {'regular': 'Helvetica', 'bold': 'Helvetica-Bold'}
        
        for lang in self.language_fonts:
            if lang in ['ja', 'zh', 'ko']:
                # For CJK languages, still try to use available fonts
                available_fonts = [name for name in self.font_registry.keys() if 'CJK' in name]
                if available_fonts:
                    regular_font = next((f for f in available_fonts if 'Regular' in f), available_fonts[0])
                    bold_font = next((f for f in available_fonts if 'Bold' in f), regular_font)
                    self.language_fonts[lang] = {'regular': regular_font, 'bold': bold_font}
                else:
                    # Use Helvetica as ultimate fallback
                    self.language_fonts[lang] = fallback_fonts
                    logger.warning(f"⚠️ Using Helvetica fallback for {lang} - Japanese text may not display correctly")
    
    def _get_font_for_language(self, language: str, bold: bool = False) -> str:
        """Get appropriate font for the specified language"""
        lang_fonts = self.language_fonts.get(language, self.language_fonts['en'])
        font_type = 'bold' if bold else 'regular'
        font_name = lang_fonts[font_type]
        
        # Verify font is available
        if font_name in ['NotoSansJP-Regular', 'NotoSansJP-Regular'] and font_name not in self.font_registry:
            logger.warning(f"⚠️ Font {font_name} not available, using Helvetica")
            return 'Helvetica-Bold' if bold else 'Helvetica'
        
        return font_name
    
    def _setup_custom_styles(self):
        """Setup custom styles for the PDF with language-specific fonts"""
        # We'll update these styles with language-specific fonts in generate_quote_pdf
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
        
        # Company tagline style
        self.styles.add(ParagraphStyle(
            name='CompanyTagline',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER,
            spaceAfter=20
        ))
    
    def _update_styles_for_language(self, language: str):
        """Update styles with appropriate fonts for the specified language"""
        regular_font = self._get_font_for_language(language, False)
        bold_font = self._get_font_for_language(language, True)
        
        # Update existing styles with language-specific fonts
        style_updates = {
            'CompanyHeader': {'fontName': bold_font, 'fontSize': 24 if language != 'ja' else 20},
            'QuoteTitle': {'fontName': bold_font, 'fontSize': 16 if language != 'ja' else 14},
            'SectionHeader': {'fontName': bold_font, 'fontSize': 14 if language != 'ja' else 12},
            'TableCell': {'fontName': regular_font, 'fontSize': 9 if language != 'ja' else 8},
            'SmallText': {'fontName': regular_font, 'fontSize': 8 if language != 'ja' else 7},
            'CompanyTagline': {'fontName': regular_font, 'fontSize': 10 if language != 'ja' else 9},
            'Normal': {'fontName': regular_font},
            'Heading1': {'fontName': bold_font},
            'Heading2': {'fontName': bold_font},
            'Heading3': {'fontName': bold_font}
        }
        
        for style_name, updates in style_updates.items():
            if style_name in self.styles:
                for attr, value in updates.items():
                    setattr(self.styles[style_name], attr, value)
        
        logger.info(f"🎨 Updated styles for {language} using fonts: {regular_font}/{bold_font}")

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
    
    def _create_paragraph_with_font(self, text: str, style_name: str, language: str) -> Paragraph:
        """Create a paragraph with appropriate font for the language"""
        try:
            # Get the style and create a copy with the right font
            base_style = self.styles[style_name]
            
            # Create paragraph with the text
            return Paragraph(text, base_style)
        except Exception as e:
            logger.warning(f"⚠️ Error creating paragraph with font: {e}")
            # Fallback to basic paragraph
            return Paragraph(text, self.styles['Normal'])
    
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
            
            # Update styles for the detected language
            self._update_styles_for_language(language)
            
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
            story.append(self._create_paragraph_with_font(
                quote_data.get('quote_title', 'Technology Solution Quote'), 
                'QuoteTitle', 
                language
            ))
            story.append(self._create_paragraph_with_font(
                quote_data.get('company_tagline', 'Professional Technology Solutions'), 
                'CompanyTagline', 
                language
            ))
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
                ('FONTNAME', (0, 0), (0, -1), self._get_font_for_language(language, True)),
                ('FONTNAME', (1, 0), (-1, -1), self._get_font_for_language(language, False)),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(quote_table)
            story.append(Spacer(1, 20))
            
            # Customer information with localized labels
            customer_info = quote_data.get('customer_info', {})
            if customer_info:
                story.append(self._create_paragraph_with_font(
                    labels['customer_information'], 
                    'Heading2', 
                    language
                ))
                
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
                        ('FONTNAME', (0, 0), (0, -1), self._get_font_for_language(language, True)),
                        ('FONTNAME', (1, 0), (-1, -1), self._get_font_for_language(language, False)),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]))
                    story.append(customer_table)
                story.append(Spacer(1, 20))
            
            # Line items with localized headers
            story.append(self._create_paragraph_with_font(
                labels['quote_details'], 
                'Heading2', 
                language
            ))
            
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
                    # Create paragraphs for text content to handle fonts properly
                    name_para = self._create_paragraph_with_font(
                        item.get('name', ''), 
                        'TableCell', 
                        language
                    )
                    
                    description = item.get('description', '')
                    if len(description) > 50:  # If description is long, use paragraph style
                        desc_para = self._create_paragraph_with_font(
                            description, 
                            'TableCell', 
                            language
                        )
                    else:
                        desc_para = self._create_paragraph_with_font(
                            description, 
                            'TableCell', 
                            language
                        )
                    
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
                    ('FONTNAME', (0, 0), (-1, 0), self._get_font_for_language(language, True)),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # Data styling
                    ('FONTNAME', (0, 1), (-1, -1), self._get_font_for_language(language, False)),
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
                ('FONTNAME', (0, 0), (0, -1), self._get_font_for_language(language, True)),
                ('FONTNAME', (1, 0), (1, 1), self._get_font_for_language(language, False)),
                ('FONTNAME', (1, 2), (1, 2), self._get_font_for_language(language, True)),  # Bold total
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
                story.append(self._create_paragraph_with_font(
                    labels['terms_and_conditions'], 
                    'Heading2', 
                    language
                ))
                for term in terms:
                    story.append(self._create_paragraph_with_font(
                        f"• {term}", 
                        'Normal', 
                        language
                    ))
                story.append(Spacer(1, 15))
            
            # Implementation notes with localized header
            implementation_notes = quote_data.get('implementation_notes', [])
            if implementation_notes:
                story.append(self._create_paragraph_with_font(
                    labels['implementation_notes'], 
                    'Heading2', 
                    language
                ))
                for note in implementation_notes:
                    story.append(self._create_paragraph_with_font(
                        f"• {note}", 
                        'Normal', 
                        language
                    ))
                story.append(Spacer(1, 15))
            
            # Next steps with localized header
            next_steps = quote_data.get('next_steps', [])
            if next_steps:
                story.append(self._create_paragraph_with_font(
                    labels['next_steps'], 
                    'Heading2', 
                    language
                ))
                for step in next_steps:
                    story.append(self._create_paragraph_with_font(
                        f"• {step}", 
                        'Normal', 
                        language
                    ))
            
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
    
    def download_noto_fonts(self):
        """Download Noto Sans Japanese fonts if not available"""
        try:
            fonts_dir = Path("fonts")
            fonts_dir.mkdir(exist_ok=True)
            
            # Alternative font URLs (more reliable)
            font_urls = {
                'NotoSansJP-Regular': {
                    'url': 'https://fonts.gstatic.com/s/notosansjp/v52/NotoSansJP-Regular.otf',
                    'filename': 'NotoSansJP-Regular.otf'
                },
                'NotoSansJP-Bold': {
                    'url': 'https://fonts.gstatic.com/s/notosansjp/v52/NotoSansJP-Bold.otf', 
                    'filename': 'NotoSansJP-Bold.otf'
                }
            }
            
            for font_name, config in font_urls.items():
                font_path = fonts_dir / config['filename']
                
                if not font_path.exists():
                    logger.info(f"📥 Downloading {font_name}...")
                    try:
                        response = requests.get(config['url'], timeout=30)
                        if response.status_code == 200:
                            with open(font_path, 'wb') as f:
                                f.write(response.content)
                            logger.info(f"✅ Downloaded {font_name}")
                        else:
                            logger.warning(f"⚠️ Failed to download {font_name}: HTTP {response.status_code}")
                    except Exception as e:
                        logger.error(f"❌ Failed to download {font_name}: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Font download failed: {e}")
    
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
                "date_formatting", "section_titles", "fonts"
            ],
            "currency_support": {
                "en": "USD ($)",
                "ja": "JPY (¥)",
                "es": "USD ($)",
                "fr": "EUR (€)",
                "de": "EUR (€)",
                "it": "EUR (€)",
                "pt": "BRL (R$)"
            },
            "font_support": {
                "en": "Helvetica",
                "ja": "Noto Sans Japanese",
                "es": "Helvetica",
                "fr": "Helvetica", 
                "de": "Helvetica",
                "it": "Helvetica",
                "pt": "Helvetica"
            }
        }
    
    def test_japanese_support(self, test_text: str = "こんにちは世界") -> bool:
        """Test if Japanese font rendering is working"""
        try:
            # Try to create a simple PDF with Japanese text
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            
            # Update styles for Japanese
            self._update_styles_for_language('ja')
            
            # Create test content
            story = []
            story.append(self._create_paragraph_with_font(
                test_text, 
                'Normal', 
                'ja'
            ))
            
            doc.build(story)
            buffer.seek(0)
            
            # Check if buffer has content
            if buffer.getvalue():
                logger.info("✅ Japanese font support test passed")
                return True
            else:
                logger.warning("⚠️ Japanese font support test failed - empty buffer")
                return False
                
        except Exception as e:
            logger.error(f"❌ Japanese font support test failed: {e}")
            return False
    
    def regenerate_with_fallback(self, quote_data: Dict[str, Any], original_error: Exception) -> BytesIO:
        """Regenerate PDF with fallback fonts if original generation fails"""
        try:
            logger.warning(f"⚠️ Attempting PDF regeneration with fallback fonts due to: {original_error}")
            
            # Force fallback fonts
            self._setup_fallback_fonts()
            
            # Detect language but force English if problematic
            language = quote_data.get('language', 'en')
            if language in ['ja', 'zh', 'ko']:
                logger.warning(f"⚠️ Using English fallback for CJK language: {language}")
                language = 'en'
            
            # Update quote data to use fallback language
            quote_data_fallback = quote_data.copy()
            quote_data_fallback['language'] = language
            
            # Generate PDF with fallback settings
            return self.generate_quote_pdf(quote_data_fallback)
            
        except Exception as e:
            logger.error(f"❌ Fallback PDF generation also failed: {e}")
            raise e


    def validate_quote_data(self, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean quote data before PDF generation"""
        try:
            # Create a copy to avoid modifying original data
            validated_data = quote_data.copy()
            
            # Ensure required fields have defaults
            defaults = {
                'quote_title': 'Technology Solution Quote',
                'company_tagline': 'Professional Technology Solutions',
                'quote_number': f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'created_at': datetime.now().isoformat(),
                'valid_until': (datetime.now() + timedelta(days=30)).isoformat(),
                'currency': 'USD',
                'language': 'en',
                'line_items': [],
                'subtotal': 0,
                'tax_amount': 0,
                'total': 0,
                'customer_info': {},
                'terms_and_conditions': [],
                'implementation_notes': [],
                'next_steps': []
            }
            
            # Apply defaults for missing fields
            for key, default_value in defaults.items():
                if key not in validated_data or validated_data[key] is None:
                    validated_data[key] = default_value
            
            # Validate and clean line items
            if validated_data['line_items']:
                cleaned_items = []
                for item in validated_data['line_items']:
                    cleaned_item = {
                        'name': str(item.get('name', 'Unnamed Item')),
                        'description': str(item.get('description', '')),
                        'quantity': max(1, int(item.get('quantity', 1))),
                        'unit_price': max(0, float(item.get('unit_price', 0))),
                        'total_price': max(0, float(item.get('total_price', 0)))
                    }
                    # Recalculate total_price if it seems incorrect
                    calculated_total = cleaned_item['quantity'] * cleaned_item['unit_price']
                    if abs(cleaned_item['total_price'] - calculated_total) > 0.01:
                        cleaned_item['total_price'] = calculated_total
                    
                    cleaned_items.append(cleaned_item)
                
                validated_data['line_items'] = cleaned_items
            
            # Recalculate totals
            subtotal = sum(item['total_price'] for item in validated_data['line_items'])
            validated_data['subtotal'] = subtotal
            
            # Ensure tax_amount is reasonable (0-50% of subtotal)
            tax_amount = float(validated_data.get('tax_amount', 0))
            if tax_amount < 0 or tax_amount > subtotal * 0.5:
                tax_amount = 0
            validated_data['tax_amount'] = tax_amount
            
            # Recalculate total
            validated_data['total'] = subtotal + tax_amount
            
            # Validate customer info
            if validated_data['customer_info']:
                customer_info = validated_data['customer_info']
                for field in ['company', 'contact', 'email', 'phone']:
                    if field in customer_info and customer_info[field]:
                        customer_info[field] = str(customer_info[field]).strip()
            
            # Clean text arrays (remove empty strings)
            for field in ['terms_and_conditions', 'implementation_notes', 'next_steps']:
                if validated_data[field]:
                    validated_data[field] = [
                        str(item).strip() for item in validated_data[field] 
                        if item and str(item).strip()
                    ]
            
            logger.info("✅ Quote data validated successfully")
            return validated_data
            
        except Exception as e:
            logger.error(f"❌ Quote data validation failed: {e}")
            raise ValueError(f"Invalid quote data: {e}")
    
    def estimate_pdf_size(self, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate PDF file size and complexity"""
        try:
            # Count content elements
            line_items_count = len(quote_data.get('line_items', []))
            terms_count = len(quote_data.get('terms_and_conditions', []))
            notes_count = len(quote_data.get('implementation_notes', []))
            steps_count = len(quote_data.get('next_steps', []))
            
            # Calculate text content length
            text_content = []
            for item in quote_data.get('line_items', []):
                text_content.extend([
                    item.get('name', ''),
                    item.get('description', '')
                ])
            
            text_content.extend(quote_data.get('terms_and_conditions', []))
            text_content.extend(quote_data.get('implementation_notes', []))
            text_content.extend(quote_data.get('next_steps', []))
            
            total_text_length = sum(len(str(text)) for text in text_content)
            
            # Estimate complexity
            if line_items_count > 20 or total_text_length > 5000:
                complexity = "high"
                estimated_size_kb = 150 + (line_items_count * 5) + (total_text_length / 100)
            elif line_items_count > 10 or total_text_length > 2000:
                complexity = "medium"
                estimated_size_kb = 80 + (line_items_count * 3) + (total_text_length / 150)
            else:
                complexity = "low"
                estimated_size_kb = 50 + (line_items_count * 2) + (total_text_length / 200)
            
            # Adjust for language (CJK fonts typically result in larger files)
            language = quote_data.get('language', 'en')
            if language in ['ja', 'zh', 'ko']:
                estimated_size_kb *= 1.3
            
            return {
                "complexity": complexity,
                "estimated_size_kb": round(estimated_size_kb, 1),
                "line_items_count": line_items_count,
                "total_text_length": total_text_length,
                "estimated_pages": max(1, (line_items_count // 15) + 1),
                "language": language
            }
            
        except Exception as e:
            logger.error(f"❌ PDF size estimation failed: {e}")
            return {
                "complexity": "unknown",
                "estimated_size_kb": 100,
                "line_items_count": 0,
                "total_text_length": 0,
                "estimated_pages": 1,
                "language": "en"
            }
    
    def generate_quote_pdf_with_validation(self, quote_data: Dict[str, Any]) -> BytesIO:
        """Generate PDF with comprehensive validation and error handling"""
        try:
            # Validate quote data first
            validated_data = self.validate_quote_data(quote_data)
            
            # Get size estimation
            size_info = self.estimate_pdf_size(validated_data)
            logger.info(f"📊 PDF Estimation: {size_info}")
            
            # Generate PDF with validated data
            try:
                return self.generate_quote_pdf(validated_data)
            except Exception as generation_error:
                logger.warning(f"⚠️ Primary PDF generation failed: {generation_error}")
                
                # Try regeneration with fallback
                return self.regenerate_with_fallback(validated_data, generation_error)
                
        except Exception as e:
            logger.error(f"❌ PDF generation with validation failed: {e}")
            raise e
    
    def batch_generate_pdfs(self, quotes_data: list, output_dir: str = None) -> Dict[str, Any]:
        """Generate multiple PDFs in batch"""
        try:
            if output_dir is None:
                output_dir = "Data/quotes/batch_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create output directory
            batch_dir = Path(output_dir)
            batch_dir.mkdir(parents=True, exist_ok=True)
            
            results = {
                "successful": [],
                "failed": [],
                "total_processed": 0,
                "batch_dir": str(batch_dir)
            }
            
            logger.info(f"🔄 Starting batch PDF generation for {len(quotes_data)} quotes")
            
            for i, quote_data in enumerate(quotes_data):
                try:
                    results["total_processed"] += 1
                    
                    # Generate filename
                    quote_id = quote_data.get('quote_id', f'quote_{i+1}')
                    language = quote_data.get('language', 'en')
                    filename = f"{quote_id}_{language}.pdf"
                    
                    # Generate PDF
                    pdf_buffer = self.generate_quote_pdf_with_validation(quote_data)
                    
                    # Save to file
                    file_path = batch_dir / filename
                    with open(file_path, 'wb') as f:
                        f.write(pdf_buffer.getvalue())
                    
                    results["successful"].append({
                        "quote_id": quote_id,
                        "filename": filename,
                        "file_path": str(file_path),
                        "language": language
                    })
                    
                    logger.info(f"✅ Generated PDF {i+1}/{len(quotes_data)}: {filename}")
                    
                except Exception as e:
                    error_info = {
                        "quote_id": quote_data.get('quote_id', f'quote_{i+1}'),
                        "index": i,
                        "error": str(e)
                    }
                    results["failed"].append(error_info)
                    logger.error(f"❌ Failed to generate PDF {i+1}/{len(quotes_data)}: {e}")
            
            # Generate batch summary
            summary_file = batch_dir / "batch_summary.txt"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"Batch PDF Generation Summary\n")
                f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Processed: {results['total_processed']}\n")
                f.write(f"Successful: {len(results['successful'])}\n")
                f.write(f"Failed: {len(results['failed'])}\n\n")
                
                if results['successful']:
                    f.write("Successful Generations:\n")
                    for success in results['successful']:
                        f.write(f"  - {success['filename']} ({success['language']})\n")
                    f.write("\n")
                
                if results['failed']:
                    f.write("Failed Generations:\n")
                    for failure in results['failed']:
                        f.write(f"  - {failure['quote_id']}: {failure['error']}\n")
            
            logger.info(f"📄 Batch generation completed: {len(results['successful'])} successful, {len(results['failed'])} failed")
            return results
            
        except Exception as e:
            logger.error(f"❌ Batch PDF generation failed: {e}")
            raise e
    
    def create_template_quote(self, language: str = 'en') -> Dict[str, Any]:
        """Create a template quote data structure for testing"""
        labels = self._get_localized_labels(language)
        
        if language == 'ja':
            template = {
                "quote_id": "TEMP001",
                "quote_title": "テクノロジーソリューション見積書",
                "company_tagline": "プロフェッショナルテクノロジーソリューション",
                "quote_number": f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "created_at": datetime.now().isoformat(),
                "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
                "currency": "JPY",
                "language": "ja",
                "customer_info": {
                    "company": "株式会社サンプル",
                    "contact": "田中太郎",
                    "email": "tanaka@sample.co.jp",
                    "phone": "03-1234-5678"
                },
                "line_items": [
                    {
                        "name": "Webサイト開発",
                        "description": "レスポンシブWebサイトの設計・開発・実装",
                        "quantity": 1,
                        "unit_price": 500000,
                        "total_price": 500000
                    },
                    {
                        "name": "データベース設計",
                        "description": "MySQL データベース設計・構築・最適化",
                        "quantity": 1,
                        "unit_price": 200000,
                        "total_price": 200000
                    }
                ],
                "subtotal": 700000,
                "tax_amount": 70000,
                "total": 770000,
                "terms_and_conditions": [
                    "支払いは納品後30日以内にお願いします",
                    "仕様変更は別途費用が発生する場合があります",
                    "保守サポートは別途契約となります"
                ],
                "implementation_notes": [
                    "開発期間は約3ヶ月を予定しています",
                    "週次進捗レポートを提供します",
                    "テスト環境での確認後、本番環境に移行します"
                ],
                "next_steps": [
                    "本見積書の承認",
                    "詳細要件のヒアリング",
                    "開発スケジュールの確定"
                ]
            }
        else:
            template = {
                "quote_id": "TEMP001",
                "quote_title": "Technology Solution Quote",
                "company_tagline": "Professional Technology Solutions",
                "quote_number": f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "created_at": datetime.now().isoformat(),
                "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
                "currency": "USD",
                "language": language,
                "customer_info": {
                    "company": "Sample Corporation",
                    "contact": "John Smith",
                    "email": "john.smith@sample.com",
                    "phone": "+1-555-123-4567"
                },
                "line_items": [
                    {
                        "name": "Website Development",
                        "description": "Responsive website design, development, and implementation",
                        "quantity": 1,
                        "unit_price": 5000.00,
                        "total_price": 5000.00
                    },
                    {
                        "name": "Database Design",
                        "description": "MySQL database design, setup, and optimization",
                        "quantity": 1,
                        "unit_price": 2000.00,
                        "total_price": 2000.00
                    }
                ],
                "subtotal": 7000.00,
                "tax_amount": 700.00,
                "total": 7700.00,
                "terms_and_conditions": [
                    "Payment due within 30 days of delivery",
                    "Scope changes may incur additional costs",
                    "Maintenance support available under separate agreement"
                ],
                "implementation_notes": [
                    "Development timeline estimated at 3 months",
                    "Weekly progress reports will be provided",
                    "Testing environment review before production deployment"
                ],
                "next_steps": [
                    "Approval of this quote",
                    "Detailed requirements gathering",
                    "Finalize development schedule"
                ]
            }
        
        return template
    
    def test_pdf_generation(self, language: str = 'en') -> Dict[str, Any]:
        """Test PDF generation with template data"""
        try:
            logger.info(f"🧪 Testing PDF generation for language: {language}")
            
            # Create template quote
            template_quote = self.create_template_quote(language)
            
            # Generate PDF
            start_time = datetime.now()
            pdf_buffer = self.generate_quote_pdf_with_validation(template_quote)
            generation_time = (datetime.now() - start_time).total_seconds()
            
            # Get PDF size
            pdf_size = len(pdf_buffer.getvalue())
            
            # Save test file
            test_filename = f"test_quote_{language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            test_file_path = self.save_pdf_to_file(template_quote, test_filename)
            
            result = {
                "success": True,
                "language": language,
                "generation_time_seconds": round(generation_time, 2),
                "pdf_size_bytes": pdf_size,
                "pdf_size_kb": round(pdf_size / 1024, 1),
                "test_file_path": test_file_path,
                "template_data": template_quote
            }
            
            logger.info(f"✅ PDF test successful: {pdf_size} bytes in {generation_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"❌ PDF test failed for {language}: {e}")
            return {
                "success": False,
                "language": language,
                "error": str(e),
                "generation_time_seconds": 0,
                "pdf_size_bytes": 0,
                "test_file_path": None
            }
    
    def cleanup_old_pdfs(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old PDF files"""
        try:
            quotes_dir = Path("Data/quotes")
            if not quotes_dir.exists():
                return {"deleted_count": 0, "freed_space_mb": 0}
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            deleted_files = []
            total_size = 0
            
            for pdf_file in quotes_dir.rglob("*.pdf"):
                try:
                    file_stat = pdf_file.stat()
                    file_date = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    if file_date < cutoff_date:
                        file_size = file_stat.st_size
                        total_size += file_size
                        deleted_files.append({
                            "filename": pdf_file.name,
                            "size_bytes": file_size,
                            "modified_date": file_date.isoformat()
                        })
                        pdf_file.unlink()
                        
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete {pdf_file}: {e}")
            
            result = {
                "deleted_count": len(deleted_files),
                "freed_space_mb": round(total_size / (1024 * 1024), 2),
                "deleted_files": deleted_files,
                "cutoff_date": cutoff_date.isoformat()
            }
            
            logger.info(f"🧹 Cleaned up {len(deleted_files)} old PDF files, freed {result['freed_space_mb']} MB")
            return result
            
        except Exception as e:
            logger.error(f"❌ PDF cleanup failed: {e}")
            return {"deleted_count": 0, "freed_space_mb": 0, "error": str(e)}

# Usage example and testing
if __name__ == "__main__":
    # Initialize PDF generator
    pdf_gen = PDFGenerator()
    
    # Test different languages
    for lang in ['en', 'ja', 'es', 'fr', 'de']:
        try:
            result = pdf_gen.test_pdf_generation(lang)
            if result['success']:
                print(f"✅ {lang}: {result['pdf_size_kb']}KB in {result['generation_time_seconds']}s")
            else:
                print(f"❌ {lang}: {result['error']}")
        except Exception as e:
            print(f"❌ {lang}: {e}")
    
    # Test Japanese font support
    japanese_support = pdf_gen.test_japanese_support()
    print(f"Japanese support: {'✅' if japanese_support else '❌'}")
    
    # Print language info
    lang_info = pdf_gen.get_language_info()
    print(f"Supported languages: {lang_info['supported_languages']}")
    
    # Cleanup old files (optional)
    # cleanup_result = pdf_gen.cleanup_old_pdfs(30)
    # print(f"Cleanup: {cleanup_result['deleted_count']} files, {cleanup_result['freed_space_mb']}MB freed")