import json
import uuid
from typing import List, Dict, Any, Optional
import logging
from .base import AIProvider, AIMessage, AIResponse
from .function_models import QuoteLineItem
from services.pdf_generator import PDFGenerator
from services.elasticsearch_vector_service import get_elasticsearch_service
from .dynamic_extraction_agent import DynamicExtractionAgent
from services.localisation import get_quote_translations, get_translation
from pydantic import BaseModel, Field
from pathlib import Path
from services.prompt_manager import get_prompt_manager
from services.metrics_service import get_metrics_service
from services.language_service import LanguageService
import os

logger = logging.getLogger(__name__)

class QuoteLineItem(BaseModel):
    """Individual line item in a quote"""
    name: str = Field(description="Product/service name")
    description: str = Field(description="Detailed description")
    quantity: int = Field(default=1, description="Quantity")
    unit_price: float = Field(description="Price per unit")
    total_price: float = Field(description="Total price for this line item")
    category: str = Field(default="", description="Product category (e.g., Hardware, Software, Services, etc.)")

class QuoteCustomerInfo(BaseModel):
    """Customer information for the quote"""
    company_name: str = Field(description="Company name")
    contact_name: str = Field(description="Primary contact name")
    email: str = Field(description="Contact email")
    phone: Optional[str] = Field(default=None, description="Phone number")
    address: Optional[str] = Field(default=None, description="Company address")

class QuoteFinancials(BaseModel):
    """Financial breakdown of the quote"""
    subtotal: float = Field(description="Subtotal before tax")
    tax_rate: float = Field(default=0.08, description="Tax rate as decimal")
    tax_amount: float = Field(description="Tax amount")
    total: float = Field(description="Final total amount")
    currency: str = Field(default="USD", description="Currency code")

class StructuredQuote(BaseModel):
    """Complete structured quote for PDF and pitch deck generation"""
    quote_number: str = Field(description="Unique quote number")
    title: str = Field(description="Professional quote title")
    company_tagline: str = Field(description="Company tagline")
    
    # Customer and business info
    customer_info: QuoteCustomerInfo = Field(description="Customer information")
    business_context: str = Field(description="Business context and use case")
    
    # Products and pricing
    line_items: List[QuoteLineItem] = Field(description="List of products/services")
    financials: QuoteFinancials = Field(description="Financial breakdown")
    
    # Terms and next steps
    terms_and_conditions: List[str] = Field(description="Terms and conditions")
    implementation_notes: List[str] = Field(description="Implementation details")
    next_steps: List[str] = Field(description="Next steps for customer")
    
    # Metadata
    valid_until: str = Field(description="Quote expiration date")
    created_at: str = Field(description="Quote creation date")
    language: str = Field(default="en", description="Quote language (en/ja)")

class QuoteGenerationAgent(AIProvider):
    """Dynamic quote generation with Pydantic function calling and internationalization"""

    def __init__(self, base_provider: AIProvider, language: str = 'en', **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.pdf_generator = PDFGenerator()
        self.elasticsearch = get_elasticsearch_service()
        self.data_extractor = DynamicExtractionAgent(base_provider)
        self.language = language
        print(f"🌐 [DEBUG] QuoteGenerationAgent initialized with language: {self.language}")
        # Initialize metrics service
        self.metrics_service = get_metrics_service()
    
    # Add the set_language method
    def set_language(self, language: str):
        """Explicitly set the agent's language."""
        prev_language = self.language
        self.language = language
        logger.info(f"🌐 QuoteGenerationAgent: Manually setting language from {prev_language} to {language}")

    @property
    def provider_name(self) -> str:
        return "quote_generation_agent"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """This agent only generates quotes, not conversational responses"""
        if hasattr(self.base_provider, 'usage_tracker'):
            self.usage_tracker = self.base_provider.usage_tracker
            
        return AIResponse(
            content="Quote Generation Agent - use generate_quote_from_conversation method",
            model="quote-agent",
            provider=self.provider_name,
            usage={}
        )
    
    async def generate_quote_from_conversation(
        self,
        conversation_messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate quote using hybrid language detection approach"""

        logger.info(f"🔍 Quote Agent: Starting quote generation with hybrid language detection")

        try:
            # Get translations for the specified language (may be updated after detection)
            t = get_quote_translations(self.language)
            
            if not conversation_messages:
                logger.error("❌ No conversation messages provided")
                self.metrics_service.record_quote_generation(status="failed")
                raise ValueError("No conversation messages available for quote generation")
            
            # Prepare conversation text for analysis
            conversation_parts = []
            for msg in conversation_messages:
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    if msg.content:
                        conversation_parts.append(f"{msg.role}: {msg.content}")
                elif isinstance(msg, dict):
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if content:
                        conversation_parts.append(f"{role}: {content}")
                elif isinstance(msg, str):
                    conversation_parts.append(f"user: {msg}")
            
            conversation_text = "\n".join(conversation_parts)
            
            if not conversation_text.strip():
                logger.error("❌ No valid conversation content found")
                self.metrics_service.record_quote_generation(status="failed")
                raise ValueError("No valid conversation content available")

            # HYBRID LANGUAGE DETECTION
            language_service = LanguageService()
            
            # Resolve language using hybrid approach
            language_resolution = language_service.resolve_language(
                explicit_language=self.language,  # From frontend/initialization
                text_content=conversation_text,   # Auto-detection
                context=customer_context          # Fallback context
            )
            
            # Update language based on resolution
            resolved_language = language_resolution['language']
            detection_method = language_resolution['method']
            confidence = language_resolution['confidence']
            
            logger.info(f"🌐 Language Resolution:")
            logger.info(f"   Resolved Language: {resolved_language}")
            logger.info(f"   Detection Method: {detection_method}")
            logger.info(f"   Confidence: {confidence:.2f}")
            
            # Update translations if language changed
            if resolved_language != self.language:
                logger.info(f"🔄 Language changed from {self.language} to {resolved_language}")
                self.language = resolved_language
                t = get_quote_translations(resolved_language)

            # Prepare safe context for AI
            safe_context = self._safe_serialize_context(customer_context)
            
            # Use the appropriate prompt from translations
            quote_prompt = t["quote_prompt"].format(
                conversation_text=conversation_text,
                safe_context=safe_context
            )
            
            # Add explicit language instruction for consistency
            if resolved_language == "ja":
                quote_prompt += "\n必ず日本語で回答してください。すべての内容を日本語で記載してください。"
            elif resolved_language != "en":
                language_name = language_service.supported_languages.get(resolved_language, {}).get('name', resolved_language)
                quote_prompt += f"\nPlease respond in {language_name}. All content should be in {language_name}."
            
            # Use Pydantic function calling to generate structured quote
            response = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=quote_prompt)],
                StructuredQuote
            )
            
            # Convert to dictionary and add metadata
            quote_dict = response.model_dump()
            quote_dict['language'] = resolved_language  # Use resolved language
            quote_dict['language_detection'] = language_resolution  # Add detection metadata
            
            quote_id = quote_dict['quote_number'].split('-')[-1] if '-' in quote_dict['quote_number'] else str(uuid.uuid4())[:8]
            
            quote_dict.update({
                'quote_id': quote_id,
                'generation_method': 'pydantic_structured_internationalized',
                'data_source': 'conversation_only'
            })
            
            logger.info(f"✅ Quote generated successfully: {quote_dict['quote_number']} (Language: {self.language})")
            logger.info(f"🔍 Quote dict after initial generation: {json.dumps(quote_dict, indent=2, default=str)}")
            
            # Generate PDF with correct language
            quote_dict = await self._generate_quote_pdf(quote_dict, language=resolved_language)
            
            logger.info(f"✅ Quote generated in {resolved_language} using {detection_method} method")
            return quote_dict
            
        except Exception as e:
            logger.error(f"❌ Quote generation failed: {str(e)}")
            # Record failed quote generation
            self.metrics_service.record_quote_generation(status="failed")
            return None
    
    async def _generate_quote_pdf(self, quote_dict: Dict[str, Any], language: str = "en") -> Dict[str, Any]:
        """Generate PDF for the quote with comprehensive debugging"""
        try:
            logger.info(f"🔍 Starting PDF generation with language: {language}")
            pdf_generator = PDFGenerator()
            
            # Get quote ID for file naming
            quote_id = quote_dict.get('quote_id', 'unknown')
            
            # Create filename
            filename = f"quote_{quote_id}_{language}.pdf"
            
            # When calling the PDF generator, pass the language for proper font selection
            pdf_quote_data = self._convert_quote_for_pdf(quote_dict)
            pdf_quote_data['language'] = language  # Ensure language is passed to PDF generator
            pdf_path = pdf_generator.save_pdf_to_file(pdf_quote_data, filename)
            
            # Check if file was actually created
            if pdf_path and os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                logger.info(f"✅ PDF generated successfully: {pdf_path} ({file_size} bytes)")
                
                quote_dict.update({
                    'pdf_generated': True,
                    'pdf_path': pdf_path,
                    'pdf_url': f'/api/quotes/download-pdf/{quote_id}?language={language}',
                    'file_size': file_size,
                })
            else:
                logger.error(f"❌ PDF file was not created: {pdf_path}")
                quote_dict.update({
                    'pdf_generated': False,
                    'pdf_error': 'PDF file was not created',
                    'pdf_path': pdf_path
                })
            
            return quote_dict
            
        except Exception as e:
            logger.error(f"❌ PDF generation failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            quote_dict.update({
                'pdf_generated': False,
                'pdf_error': f'PDF generation failed: {str(e)}'
            })
            return quote_dict

    def _convert_quote_for_pdf(self, quote_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Convert the structured quote format to PDF generator format with proper translations"""
        try:
            logger.info(f"🔍 Converting quote format for PDF generator (Language: {self.language})")
            
            # Get translations for the specified language
            t = get_quote_translations(self.language)
            pdf_labels = t["pdf_labels"]
            exchange_rate = 150 if self.language == "ja" else 1  # Example exchange rate for USD to JPY
            
            # Handle customer_info format conversion
            customer_info = quote_dict.get('customer_info', {})
            pdf_customer_info = {}
            
            if isinstance(customer_info, dict):
                pdf_customer_info['company'] = customer_info.get('company_name', 'Valued Customer')
                pdf_customer_info['contact'] = customer_info.get('contact_name', 'Dear Customer')
                pdf_customer_info['email'] = customer_info.get('email', '')
                pdf_customer_info['phone'] = customer_info.get('phone', '')
                pdf_customer_info['address'] = customer_info.get('address', '')
            
            # Handle financials format conversion
            financials = quote_dict.get('financials', {})
            
            # Convert currency based on language
            currency_symbol = "¥" if self.language == "ja" else "$"
            currency_code = "JPY" if self.language == "ja" else "USD"
            
            # Adjust amounts for Japanese currency (multiply by exchange rate if needed)
            if self.language == "ja" and financials.get('currency', 'USD') == 'USD':
                # Convert USD to JPY (approximate rate: 1 USD = 150 JPY)
                subtotal = financials.get('subtotal', 0) * exchange_rate
                tax_amount = financials.get('tax_amount', 0) * exchange_rate
                total = financials.get('total', 0) * exchange_rate
            else:
                subtotal = financials.get('subtotal', 0)
                tax_amount = financials.get('tax_amount', 0)
                total = financials.get('total', 0)
            
            # Convert line items with proper currency
            line_items = []
            for item in quote_dict.get('line_items', []):
                if isinstance(item, dict):
                    converted_item = item.copy()
                    if self.language == "ja" and financials.get('currency', 'USD') == 'USD':
                        converted_item['unit_price'] = item.get('unit_price', 0) * exchange_rate
                        converted_item['total_price'] = item.get('total_price', 0) * exchange_rate
                    line_items.append(converted_item)
                else:
                    line_items.append(item)
            
            # Convert to the format expected by PDF generator with translations
            pdf_quote_data = {
                'quote_number': quote_dict.get('quote_number', 'N/A'),
                'language': quote_dict.get('language', 'en'),
                'quote_id': quote_dict.get('quote_id', 'unknown'),
                'created_at': quote_dict.get('created_at', ''),
                'valid_until': quote_dict.get('valid_until', ''),
                'quote_title': quote_dict.get('title', 'Professional Quote'),
                'company_tagline': quote_dict.get('company_tagline', 'Quality Products & Services'),
                'customer_info': pdf_customer_info,
                'line_items': line_items,
                'subtotal': subtotal,
                'tax_rate': financials.get('tax_rate', 0) if financials else 0,
                'tax_amount': tax_amount,
                'total': total,
                'currency': currency_code,
                'currency_symbol': currency_symbol,
                'terms_and_conditions': quote_dict.get('terms_and_conditions', []),
                'implementation_notes': quote_dict.get('implementation_notes', []),
                'next_steps': quote_dict.get('next_steps', []),
                'language': self.language,
                'labels': pdf_labels  # Add translated labels
            }
            
            logger.info(f"✅ PDF quote data converted successfully for {self.language}")
            return pdf_quote_data
            
        except Exception as e:
            logger.error(f"❌ Quote format conversion failed: {str(e)}")
            # Return minimal safe format with fallback
            t = get_quote_translations(self.language)
            return {
                'quote_number': quote_dict.get('quote_number', 'N/A'),
                'quote_id': quote_dict.get('quote_id', 'unknown'),
                'quote_title': quote_dict.get('title', 'Professional Quote'),
                'company_tagline': quote_dict.get('company_tagline', 'Quality Products & Services'),
                'customer_info': {'company': 'Valued Customer', 'contact': 'Dear Customer'},
                'line_items': [],
                'subtotal': 0,
                'tax_amount': 0,
                'total': 0,
                'currency': 'USD' if self.language == "en" else 'JPY',
                'currency_symbol': '$' if self.language == "en" else '¥',
                'terms_and_conditions': [],
                'implementation_notes': [],
                'next_steps': [],
                'language': self.language,
                'labels': t["pdf_labels"]
            }

    def format_quote_response(self, quote: Dict[str, Any], language: str) -> str:
        """Format the quote response using translations."""
        t = get_translation("quote_prompt", language)
        return f"{t['intro']}\n{t['quote_number'].format(quote_number=quote['quote_number'])}"

    def _safe_serialize_context(self, context):
        """Safely serialize context for logging or prompt injection."""
        import json
        try:
            return json.dumps(context, ensure_ascii=False, default=str)
        except Exception as e:
            return f"<Unserializable context: {e}>"