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
from services.elasticsearch_vector_service import get_elasticsearch_service
from .dynamic_extraction_agent import DynamicExtractionAgent
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

class QuoteTitleGeneration(BaseModel):
    """Model for generating quote titles"""
    title: str = Field(description="Professional, specific quote title")
    tagline: str = Field(description="Company tagline relevant to the business context")

class QuoteTermsGeneration(BaseModel):
    """Model for generating terms and conditions"""
    terms_and_conditions: List[str] = Field(description="List of professional terms and conditions")
    implementation_notes: List[str] = Field(description="Implementation and deployment notes")
    next_steps: List[str] = Field(description="Next steps for the customer")

class QuoteGenerationAgent(AIProvider):
    """Completely dynamic quote generation with Pydantic function calling"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.pdf_generator = PDFGenerator()
        self.elasticsearch = get_elasticsearch_service()
        # Use the dynamic extraction agent
        self.data_extractor = DynamicExtractionAgent(base_provider)
        # Initialize metrics service
        self.metrics_service = get_metrics_service()
        
    @property
    def provider_name(self) -> str:
        return "quote_generation_agent"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """This agent only generates quotes, not conversational responses"""
        # Track token usage from base provider
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
        
        logger.info(f"🔍 Quote Agent: Starting simplified quote generation...")
        print(f"🔍 Debug - Input validation:")
        print(f"   conversation_messages type: {type(conversation_messages)}")
        print(f"   conversation_messages length: {len(conversation_messages) if conversation_messages else 0}")
        print(f"   customer_context type: {type(customer_context)}")
        print(f"   customer_context keys: {list(customer_context.keys()) if customer_context else 'None'}")
        
        try:
            # Use conversation_messages directly instead of extracting from recommendation_context
            if not conversation_messages:
                logger.error("❌ No conversation messages provided")
                print("❌ Debug - conversation_messages is empty!")
                self.metrics_service.record_quote_generation(status="failed")
                raise ValueError("No conversation messages available for quote generation")
            
            logger.info(f"✅ Found {len(conversation_messages)} conversation messages")
            print(f"🔍 Debug - Processing conversation messages...")
            
            # Prepare conversation text for AI analysis - handle both AIMessage objects and dicts
            conversation_parts = []
            for i, msg in enumerate(conversation_messages):
                print(f"🔍 Debug - Message {i+1}: type={type(msg)}")
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    # AIMessage object
                    if msg.content:
                        conversation_parts.append(f"{msg.role}: {msg.content}")
                        print(f"   AIMessage - Role: {msg.role}, Content length: {len(msg.content)}")
                elif isinstance(msg, dict):
                    # Dictionary format
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if content:
                        conversation_parts.append(f"{role}: {content}")
                        print(f"   Dict - Role: {role}, Content length: {len(content)}")
                elif isinstance(msg, str):
                    # String format - just add as user message
                    conversation_parts.append(f"user: {msg}")
                    print(f"   String - Length: {len(msg)}")
                else:
                    print(f"   Unknown message format: {msg}")
            
            conversation_text = "\n".join(conversation_parts)
            language_service = LanguageService()

            detected_language = language_service.detect_language(conversation_text)
            primary_lang = detected_language["primary_language"]
            print(f"🌐 Detected primary language: {primary_lang}")

            print(f"🔍 Debug - Final conversation text length: {len(conversation_text)}")
            
            if not conversation_text.strip():
                logger.error("❌ No valid conversation content found")
                print("❌ Debug - conversation_text is empty after processing!")
                self.metrics_service.record_quote_generation(status="failed")
                raise ValueError("No valid conversation content available")

            # Create prompt for structured quote generation - no product retrieval required
            print("🔍 Debug - Preparing quote prompt...")
            safe_context = self._safe_serialize_context(customer_context)
            print(f"🔍 Debug - Safe context length: {len(safe_context)}")
                        

            if primary_lang == "ja":
                quote_prompt = f"""この営業会話に基づいて、完全な見積書を日本語で作成してください。すべての出力を日本語で記載してください。

会話内容:
{conversation_text}

顧客情報:
{safe_context}

見積書には以下を含めてください:
1. 会話から抽出された顧客情報
2. 会話で具体的に議論された製品やサービス
3. 小計・税・合計を含むプロフェッショナルな価格情報
4. 顧客ニーズにマッチするビジネス背景
5. 利用規約
6. 導入ノートと次のステップ
7. プロフェッショナルな見積書タイトルと会社のキャッチコピー

重要事項:
- 会話で言及された製品/サービスのみに基づいてください
- 話題にされていない製品やソリューションを追加しないでください
- 現実的な価格設定を心がけてください
- 会話内容に忠実な見積書を作成してください
"""
            else:
                quote_prompt = f"""Based on this sales conversation, generate a complete structured quote.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT:
{safe_context}

Generate a complete quote with:
1. Customer information extracted from conversation
2. Products/services that match exactly what was discussed in the conversation
3. Professional pricing with subtotal, tax, and total
4. Business context explaining why these products fit their needs
5. Professional terms and conditions
6. Implementation notes and next steps
7. Professional quote title and company tagline

IMPORTANT GUIDELINES:
- Use ONLY the specific products/services mentioned in the conversation
- If the conversation is about PC components, quote PC components
- If the conversation is about software, quote software
- If the conversation is about services, quote services
- Do NOT default to generic "technology solutions" unless that's what was actually discussed
- Make sure all prices are realistic for the specific products mentioned
- The quote should directly reflect what the customer asked for

Make sure the quote accurately represents what was discussed in the conversation, not generic business solutions."""


            print(f"🔍 Debug - Quote prompt length: {len(quote_prompt)}")
            
            # Use Pydantic function calling to generate structured quote
            print("🔍 Debug - Calling base_provider.generate_structured_response...")
            response = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=quote_prompt)],
                StructuredQuote
            )
            
            print(f"🔍 Debug - Structured response type: {type(response)}")
            print(f"🔍 Debug - Response model_dump available: {hasattr(response, 'model_dump')}")
            
            # Convert to dictionary and add metadata
            quote_dict = response.model_dump()
            print(f"🔍 Debug - Quote dict type: {type(quote_dict)}")
            print(f"🔍 Debug - Quote dict keys: {list(quote_dict.keys())}")
            
            quote_id = quote_dict['quote_number'].split('-')[-1] if '-' in quote_dict['quote_number'] else str(uuid.uuid4())[:8]
            print(f"🔍 Debug - Generated quote_id: {quote_id}")

            quote_dict["language"] = primary_lang
            
            quote_dict.update({
                'quote_id': quote_id,
                'generation_method': 'pydantic_structured_simplified',
                'data_source': 'conversation_only'
            })
            
            print("🔍 Debug - Starting PDF generation...")
            # Generate PDF
            quote_dict = await self._generate_quote_pdf(quote_dict)
            print(f"🔍 Debug - PDF generation completed")
            print(f"🔍 Debug - Final quote_dict keys: {list(quote_dict.keys())}")
            
            # Extract quote value for metrics
            quote_value = None
            currency = "USD"
            try:
                financials = quote_dict.get('financials', {})
                if financials and isinstance(financials, dict):
                    quote_value = financials.get('total', 0)
                    currency = financials.get('currency', 'USD')
                    print(f"🔍 Debug - Extracted quote value: {quote_value} {currency}")
            except Exception as e:
                print(f"⚠️ Debug - Failed to extract quote value: {e}")
            
            # Record successful quote generation with value
            self.metrics_service.record_quote_generation(
                status="success", 
                quote_value=quote_value, 
                currency=currency
            )
            
            logger.info(f"✅ Quote generated successfully: {quote_dict['quote_number']}")
            return quote_dict
            
        except Exception as e:
            logger.error(f"❌ Quote generation failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            print(f"❌ Debug - Full exception details:")
            print(f"   Exception type: {type(e)}")
            print(f"   Exception message: {str(e)}")
            print(f"   Full traceback: {traceback.format_exc()}")
            
            # Record failed quote generation
            self.metrics_service.record_quote_generation(status="failed")
            return None
    
    async def _generate_quote_pdf(self, quote_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Generate PDF for the quote with comprehensive debugging"""
        try:
            print("🔍 Debug - Starting PDF generation...")
            print(f"🔍 Debug - Input quote_dict type: {type(quote_dict)}")
            print(f"🔍 Debug - Input quote_dict keys: {list(quote_dict.keys())}")
            
            from services.pdf_generator import PDFGenerator
            print("🔍 Debug - PDFGenerator imported successfully")
            
            pdf_generator = PDFGenerator()
            print("🔍 Debug - PDFGenerator initialized")
            
            # Get quote ID for file naming
            quote_id = quote_dict.get('quote_id', 'unknown')
            quote_number = quote_dict.get('quote_number', 'QUOTE-UNKNOWN')
            print(f"🔍 Debug - Quote ID: {quote_id}")
            print(f"🔍 Debug - Quote number: {quote_number}")
            
            # Create filename
            filename = f"quote_{quote_id}.pdf"
            print(f"🔍 Debug - Target filename: {filename}")
            
            # Convert the quote dict to match the PDF generator's expected format
            pdf_quote_data = self._convert_quote_for_pdf(quote_dict)
            print(f"🔍 Debug - Converted quote data keys: {list(pdf_quote_data.keys())}")
            
            # Generate and save the PDF (this is synchronous, not async)
            print("🔍 Debug - Calling pdf_generator.save_pdf_to_file...")
            pdf_path = pdf_generator.save_pdf_to_file(pdf_quote_data, filename)
            print(f"🔍 Debug - save_pdf_to_file returned: {pdf_path}")
            print(f"🔍 Debug - File path type: {type(pdf_path)}")
            
            # Check if file was actually created
            if pdf_path:
                import os
                if os.path.exists(pdf_path):
                    file_size = os.path.getsize(pdf_path)
                    print(f"🔍 Debug - PDF file exists: {pdf_path}")
                    print(f"🔍 Debug - PDF file size: {file_size} bytes")
                    
                    # Add PDF info to quote
                    quote_dict.update({
                        'pdf_generated': True,
                        'pdf_path': pdf_path,
                        'pdf_url': f'/api/quotes/download-pdf/{quote_id}',
                        'file_size': file_size
                    })
                    
                    print(f"✅ PDF generated successfully: {pdf_path}")
                else:
                    print(f"❌ Debug - PDF file does not exist: {pdf_path}")
                    quote_dict.update({
                        'pdf_generated': False,
                        'pdf_error': 'PDF file was not created',
                        'pdf_path': pdf_path
                    })
            else:
                print("❌ Debug - No PDF path returned")
                quote_dict.update({
                    'pdf_generated': False,
                    'pdf_error': 'No file path returned from PDF generator'
                })
            
            print(f"🔍 Debug - Final quote_dict after PDF generation:")
            print(f"   pdf_generated: {quote_dict.get('pdf_generated', 'Not set')}")
            print(f"   pdf_path: {quote_dict.get('pdf_path', 'Not set')}")
            print(f"   pdf_url: {quote_dict.get('pdf_url', 'Not set')}")
            print(f"   pdf_error: {quote_dict.get('pdf_error', 'Not set')}")
            
            return quote_dict
            
        except ImportError as e:
            print(f"❌ Debug - PDF Generator import failed: {str(e)}")
            quote_dict.update({
                'pdf_generated': False,
                'pdf_error': f'PDF Generator import failed: {str(e)}'
            })
            return quote_dict
            
        except Exception as e:
            print(f"❌ Debug - PDF generation exception: {str(e)}")
            import traceback
            print(f"❌ Debug - PDF generation traceback: {traceback.format_exc()}")
            quote_dict.update({
                'pdf_generated': False,
                'pdf_error': f'PDF generation failed: {str(e)}'
            })
            return quote_dict

    def _convert_quote_for_pdf(self, quote_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Convert the structured quote format to PDF generator format"""
        try:
            print("🔍 Debug - Converting quote format for PDF generator...")
            
            # Handle customer_info format conversion
            customer_info = quote_dict.get('customer_info', {})
            pdf_customer_info = {}
            
            if isinstance(customer_info, dict):
                # Map the fields correctly
                pdf_customer_info['company'] = customer_info.get('company_name', 'Valued Customer')
                pdf_customer_info['contact'] = customer_info.get('contact_name', 'Dear Customer')
                pdf_customer_info['email'] = customer_info.get('email', '')
                pdf_customer_info['phone'] = customer_info.get('phone', '')
                pdf_customer_info['address'] = customer_info.get('address', '')
            
            # Handle financials format conversion
            financials = quote_dict.get('financials', {})
            
            # Convert to the format expected by PDF generator
            pdf_quote_data = {
                'quote_number': quote_dict.get('quote_number', 'N/A'),
                'language': quote_dict.get('language', 'en'),
                'quote_id': quote_dict.get('quote_id', 'unknown'),
                'created_at': quote_dict.get('created_at', ''),
                'valid_until': quote_dict.get('valid_until', ''),
                'quote_title': quote_dict.get('title', 'Professional Quote'),
                'company_tagline': quote_dict.get('company_tagline', 'Quality Products & Services'),
                'customer_info': pdf_customer_info,
                'line_items': quote_dict.get('line_items', []),
                'subtotal': financials.get('subtotal', 0) if financials else 0,
                'tax_rate': financials.get('tax_rate', 0) if financials else 0,
                'tax_amount': financials.get('tax_amount', 0) if financials else 0,
                'total': financials.get('total', 0) if financials else 0,
                'currency': financials.get('currency', 'USD') if financials else 'USD',
                'terms_and_conditions': quote_dict.get('terms_and_conditions', []),
                'implementation_notes': quote_dict.get('implementation_notes', []),
                'next_steps': quote_dict.get('next_steps', [])
            }
            
            print(f"🔍 Debug - PDF quote data converted successfully")
            print(f"   customer_info keys: {list(pdf_quote_data['customer_info'].keys())}")
            print(f"   line_items count: {len(pdf_quote_data['line_items'])}")
            print(f"   total: {pdf_quote_data['total']}")
            
            return pdf_quote_data
            
        except Exception as e:
            print(f"❌ Debug - Quote format conversion failed: {str(e)}")
            # Return minimal safe format
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
                'currency': 'USD',
                'terms_and_conditions': [],
                'implementation_notes': [],
                'next_steps': []
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