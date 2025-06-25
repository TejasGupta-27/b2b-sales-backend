import json
import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from io import BytesIO
import logging
from .base import AIProvider, AIMessage, AIResponse
from .function_models import QuoteData, CustomerInfo, QuoteLineItem
from services.pdf_generator import PDFGenerator
from services.elasticsearch_service import get_elasticsearch_service
from .dynamic_extraction_agent import DynamicExtractionAgent
from services.localisation import get_quote_translations
from pydantic import BaseModel, Field
from pathlib import Path
from services.prompt_manager import get_prompt_manager
import os
from langdetect import detect

logger = logging.getLogger(__name__)

class QuoteLineItem(BaseModel):
    """Individual line item in a quote"""
    name: str = Field(description="Product/service name")
    description: str = Field(description="Detailed description")
    quantity: int = Field(default=1, description="Quantity")
    unit_price: float = Field(description="Price per unit")
    total_price: float = Field(description="Total price for this line item")
    category: str = Field(default="Technology", description="Product category")

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
    
    def __init__(self, base_provider: AIProvider, language: str = "en", **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.pdf_generator = PDFGenerator()
        self.elasticsearch = get_elasticsearch_service()
        self.data_extractor = DynamicExtractionAgent(base_provider)
        self.language = language
        
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
        """Generate quote using simplified workflow with conversation messages directly"""
        
        logger.info(f"🔍 Quote Agent: Starting quote generation for language: {self.language}")
        
        try:
            # Get translations for the specified language
            t = get_quote_translations(self.language)
            
            if not conversation_messages:
                logger.error("❌ No conversation messages provided")
                raise ValueError("No conversation messages available for quote generation")
            
            logger.info(f"✅ Found {len(conversation_messages)} conversation messages")
            
            # Prepare conversation text for AI analysis
            conversation_parts = []
            for i, msg in enumerate(conversation_messages):
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
                raise ValueError("No valid conversation content available")

            # Prepare safe context for AI
            safe_context = self._safe_serialize_context(customer_context)
            
            # Use the appropriate prompt from translations
            quote_prompt = t["quote_prompt"].format(
                conversation_text=conversation_text,
                safe_context=safe_context
            )
            print(f"🔍 Debug - Quote prompt length: {len(quote_prompt)}")
            
            # Use Pydantic function calling to generate structured quote
            response = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=quote_prompt)],
                StructuredQuote
            )
            
            # Convert to dictionary and add metadata
            quote_dict = response.model_dump()
            quote_dict['language'] = self.language  # Ensure language is set
            
            quote_id = quote_dict['quote_number'].split('-')[-1] if '-' in quote_dict['quote_number'] else str(uuid.uuid4())[:8]
            
            quote_dict.update({
                'quote_id': quote_id,
                'generation_method': 'pydantic_structured_internationalized',
                'data_source': 'conversation_only'
            })
            
            print("🔍 Debug - Starting PDF generation...")
            
            # Generate PDF
            quote_dict = await self._generate_quote_pdf(quote_dict, lang=lang)
            print(f"🔍 Debug - PDF generation completed")
            print(f"🔍 Debug - Final quote_dict keys: {list(quote_dict.keys())}")
            
            logger.info(f"✅ Quote generated successfully: {quote_dict['quote_number']} (Language: {self.language})")
            return quote_dict
            
        except Exception as e:
            logger.error(f"❌ Quote generation failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def _generate_quote_pdf(self, quote_dict: Dict[str, Any], language: str = "en") -> Dict[str, Any]:
        """Generate PDF for the quote with comprehensive debugging"""
        try:
            logger.info(f"🔍 Starting PDF generation with language: {language}")
            
            from services.pdf_generator import PDFGenerator
            pdf_generator = PDFGenerator()
            
            # Get quote ID for file naming
            quote_id = quote_dict.get('quote_id', 'unknown')
            quote_number = quote_dict.get('quote_number', 'QUOTE-UNKNOWN')
            
            # Create filename
            filename = f"quote_{quote_id}_{language}.pdf"
            
            # Convert the quote dict to match the PDF generator's expected format with translations
            pdf_quote_data = self._convert_quote_for_pdf(quote_dict)
            
            # When calling the PDF generator, pass the lang or set font accordingly
            pdf_quote_data = self._convert_quote_for_pdf(quote_dict)
            if language == "ja":
                pdf_quote_data['font'] = "NotoSansCJKjp"  # or another Japanese font available in your PDF generator
            pdf_path = pdf_generator.save_pdf_to_file(pdf_quote_data, filename)
            
            # Check if file was actually created
            if pdf_path and os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                logger.info(f"✅ PDF generated successfully: {pdf_path} ({file_size} bytes)")
                
                quote_dict.update({
                    'pdf_generated': True,
                    'pdf_path': pdf_path,
                    'pdf_url': f'/api/quotes/download-pdf/{quote_id}',
                    'file_size': file_size,
                    'pdf_language': self.language
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
                exchange_rate = 150
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
                'quote_id': quote_dict.get('quote_id', 'unknown'),
                'created_at': quote_dict.get('created_at', ''),
                'valid_until': quote_dict.get('valid_until', ''),
                'quote_title': quote_dict.get('title', 'Technology Solution Quote'),
                'company_tagline': quote_dict.get('company_tagline', 'Professional Technology Solutions'),
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
                'quote_title': quote_dict.get('title', 'Technology Solution Quote'),
                'company_tagline': quote_dict.get('company_tagline', 'Professional Technology Solutions'),
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

    def format_quote_response(self, quote_dict: Dict[str, Any]) -> str:
        """Format the quote response with proper translations"""
        t = get_quote_translations(self.language)
        
        # Extract financial info
        financials = quote_dict.get('financials', {})
        subtotal = financials.get('subtotal', 0)
        tax = financials.get('tax_amount', 0)
        total = financials.get('total', 0)
        currency = financials.get('currency', 'USD')
        
        # Convert to local currency if needed
        if self.language == "ja" and currency == "USD":
            exchange_rate = 150  # USD to JPY
            subtotal *= exchange_rate
            tax *= exchange_rate
            total *= exchange_rate
        
        # Build response
        response_parts = [
            t["intro"],
            "",
            t["quote_number"].format(quote_number=quote_dict.get('quote_number', 'N/A')),
            "",
            t["analysis"],
            "",
            t["investment_summary"]
        ]
        
        # Add financial summary
        response_parts.extend([
            t["subtotal"].format(subtotal=subtotal),
            t["tax"].format(tax=tax),
            t["total"].format(total=total),
            t["valid_until"].format(date=quote_dict.get('valid_until', 'N/A'))
        ])
        
        response_parts.append("")
        
        # Add PDF link
        if quote_dict.get('pdf_generated'):
            pdf_url = quote_dict.get('pdf_url', '#')
            response_parts.append(t["pdf_ready"].format(url=pdf_url))
        else:
            response_parts.append(t["pdf_pending"])
            if quote_dict.get('pdf_error'):
                response_parts.append(t["pdf_error"])
        
        response_parts.extend([
            "",
            t["next_steps"]
        ])
        
        # Add next steps list
        next_steps = t["next_without_ppt"]
        for i, step in enumerate(next_steps, 1):
            response_parts.append(step)
        
        response_parts.extend([
            "",
            t["confidence_note"]
        ])
        
        return "\n".join(response_parts)

    def generate_bilingual_quote_response(self, quote_dict: Dict[str, Any]) -> Dict[str, str]:
        """Generate quote responses in both English and Japanese"""
        return {
            "en": self.format_quote_response(quote_dict, "en"),
            "ja": self.format_quote_response(quote_dict, "ja")
        }

    def _serialize_quote_for_storage(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize quote data for storage by removing circular references"""
        serialized = quote.copy()
        
        # Remove any potential circular references
        if 'metadata' in serialized:
            del serialized['metadata']
            
        # Ensure all nested objects are JSON serializable
        for key, value in serialized.items():
            if isinstance(value, (dict, list)):
                serialized[key] = json.loads(json.dumps(value, default=str))
            elif not isinstance(value, (str, int, float, bool, type(None))):
                serialized[key] = str(value)
                
        return serialized

    def _safe_serialize_context(self, context: Optional[Dict[str, Any]]) -> str:
        """Serialize customer context safely to avoid circular references"""
        if context is None:
            return 'None'
        
        try:
            # Extract only the essential fields we need for quote generation
            safe_context = {}
            
            # Basic customer info
            if 'company_name' in context:
                safe_context['company_name'] = context['company_name']
            if 'contact_name' in context:
                safe_context['contact_name'] = context['contact_name']
            if 'email' in context:
                safe_context['email'] = context['email']
            if 'industry' in context:
                safe_context['industry'] = context['industry']
            
            # Business context from recommendation_context if available
            rec_context = context.get('recommendation_context', {})
            if rec_context:
                if 'extracted_requirements' in rec_context:
                    requirements = rec_context['extracted_requirements']
                    safe_context['extracted_requirements'] = {
                        'technical_requirements': requirements.get('technical_requirements', []),
                        'business_requirements': requirements.get('business_requirements', []),
                        'use_case': requirements.get('use_case', ''),
                        'industry': requirements.get('industry', ''),
                        'budget_range': requirements.get('budget_range', ''),
                        'timeline': requirements.get('timeline', '')
                    }
                
                # Add simplified product info for context
                available_products = rec_context.get('available_products', [])
                if available_products:
                    safe_context['available_products_count'] = len(available_products)
                    # Include just the names and prices of top 5 products
                    safe_context['top_products'] = []
                    for product in available_products[:5]:
                        safe_context['top_products'].append({
                            'name': product.get('name', 'Unknown'),
                            'price': product.get('price', 0),
                            'category': product.get('category', 'general')
                        })
            
            return json.dumps(safe_context, indent=2)
            
        except Exception as e:
            logger.warning(f"Failed to serialize customer context: {e}")
            # Return minimal context as fallback
            return json.dumps({
                'company_name': context.get('company_name', 'Valued Customer'),
                'industry': context.get('industry', 'Technology'),
                'note': 'Full context could not be serialized due to complexity'
            }, indent=2)

    # Remove the old complex methods - they're no longer needed with simplified workflow
    # def _extract_fallback_recommendation - REMOVED
    # async def _generate_fully_dynamic_quote - REMOVED  
    # async def _analyze_conversation_for_quote_products - REMOVED

    # Remove the problematic get_product_catalog method entirely
    # def get_product_catalog(self):
    #     """This method should now be dynamic - fetch from Elasticsearch"""
    #     # This can be removed since we're using Elasticsearch directly
    #     pass