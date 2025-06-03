import json
import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from io import BytesIO

from .base import AIProvider, AIMessage, AIResponse
from .function_models import QuoteData, CustomerInfo, QuoteLineItem
from services.pdf_generator import PDFGenerator
from services.elasticsearch_service import get_elasticsearch_service
from .dynamic_extraction_agent import DynamicExtractionAgent

# Additional Pydantic models for quote generation functions
from pydantic import BaseModel, Field

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
        
    @property
    def provider_name(self) -> str:
        return f"quote_generation_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """This agent only generates quotes, not conversational responses"""
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
        """Generate completely dynamic quote from conversation using Pydantic"""
        
        print(f"🔍 Quote Agent: Starting Pydantic-based dynamic analysis...")
        
        try:
            # Extract everything dynamically using Pydantic
            extracted_data = await self.data_extractor.extract_data(
                conversation_messages, 
                customer_context
            )
            
            if not extracted_data or not extracted_data.get('line_items'):
                print("❌ Quote Agent: No data could be extracted")
                return None
            
            # Generate quote using only extracted data
            quote = await self._generate_fully_dynamic_quote(extracted_data)
            
            # Generate PDF
            quote = await self._generate_quote_pdf(quote)
            
            print(f"📄 Quote Agent: Dynamic quote generated with PDF")
            return quote
            
        except Exception as e:
            print(f"❌ Quote Agent: Error - {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None
    
    async def _generate_fully_dynamic_quote(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate quote using ONLY extracted data - no assumptions"""
        
        quote_id = str(uuid.uuid4())[:8]
        current_time = datetime.now()
        valid_until = current_time + timedelta(days=30)
        
        # Use extracted data directly
        customer_info = extracted_data.get('customer_info', {})
        line_items = extracted_data.get('line_items', [])
        subtotal = extracted_data.get('subtotal', 0)
        tax_rate = extracted_data.get('tax_rate', 0.08)
        tax_amount = extracted_data.get('tax_amount', subtotal * tax_rate)
        total = extracted_data.get('total', subtotal + tax_amount)
        currency = extracted_data.get('currency', 'USD')
        business_context = extracted_data.get('business_context', {})
        
        # Generate dynamic title and tagline using Pydantic function calling
        title_data = await self._generate_title_and_tagline(line_items, business_context)
        
        # Generate terms and conditions using Pydantic function calling
        terms_data = await self._generate_terms_and_conditions(line_items, business_context)
        
        # Build the complete quote structure
        quote = {
            "quote_number": f"Q-{quote_id}",
            "quote_id": quote_id,
            "created_at": current_time.isoformat(),
            "valid_until": valid_until.isoformat(),
            "quote_title": title_data.get('title', 'Professional Technology Solution'),
            "company_tagline": title_data.get('tagline', 'Your Technology Partner'),
            
            # Customer information
            "customer_info": customer_info,
            
            # Line items with full details
            "line_items": line_items,
            
            # Pricing breakdown
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total": total,
            "currency": currency,
            
            # Business context and terms
            "business_context": business_context,
            "terms_and_conditions": terms_data.get('terms_and_conditions', []),
            "implementation_notes": terms_data.get('implementation_notes', []),
            "next_steps": terms_data.get('next_steps', []),
            
            # Metadata
            "generation_method": "pydantic_function_calling",
            "data_source": "conversation_analysis",
            "extraction_confidence": extracted_data.get('extraction_confidence', 'medium')
        }
        
        print(f"✅ Quote Agent: Generated quote #{quote_id} with {len(line_items)} line items totaling ${total:,.2f}")
        return quote
    
    async def _generate_title_and_tagline(self, line_items: List[Dict], business_context: Dict[str, Any]) -> Dict[str, str]:
        """Generate dynamic quote title and tagline using Pydantic function calling"""
        
        try:
            # Create context for title generation
            items_summary = ", ".join([item.get('name', 'Product') for item in line_items[:3]])
            use_case = business_context.get('use_case', 'Technology Solution')
            
            title_prompt = f"""Generate a professional quote title and company tagline based on these products and business context.

PRODUCTS: {items_summary}
USE CASE: {use_case}
BUSINESS CONTEXT: {json.dumps(business_context, indent=2)}

Generate:
1. A concise, professional quote title that reflects what the customer is buying and why
2. A professional company tagline that reflects our expertise in their industry/use case

Examples of good titles:
- "Enterprise Workstation Solution for Video Production"
- "High-Performance Storage Infrastructure for Data Analytics"
- "Complete Networking Solution for Office Expansion"

Examples of good taglines:
- "Powering Innovation Through Technology"
- "Your Trusted Technology Partner"  
- "Excellence in Enterprise Solutions"
"""

            response = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=title_prompt)],
                QuoteTitleGeneration
            )
            
            return {
                'title': response.title,
                'tagline': response.tagline
            }
            
        except Exception as e:
            print(f"⚠️ Title generation failed: {e}")
            return {
                'title': 'Professional Technology Solution',
                'tagline': 'Your Technology Partner'
            }
    
    async def _generate_terms_and_conditions(self, line_items: List[Dict], business_context: Dict[str, Any]) -> Dict[str, List[str]]:
        """Generate terms, implementation notes, and next steps using Pydantic function calling"""
        
        try:
            items_summary = [f"{item.get('name', '')}: {item.get('description', '')}" for item in line_items]
            timeline = business_context.get('timeline', 'standard')
            
            terms_prompt = f"""Generate comprehensive quote terms for this technology solution.

PRODUCTS:
{chr(10).join(items_summary)}

BUSINESS CONTEXT: {json.dumps(business_context, indent=2)}
TIMELINE: {timeline}

Generate:
1. Professional terms and conditions (4-6 items covering payment, delivery, warranties, support)
2. Implementation notes (3-5 items covering deployment, setup, training, integration)
3. Next steps for the customer (3-5 action items)

Consider the timeline urgency when generating next steps.
"""

            response = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=terms_prompt)],
                QuoteTermsGeneration
            )
            
            return {
                'terms_and_conditions': response.terms_and_conditions,
                'implementation_notes': response.implementation_notes,
                'next_steps': response.next_steps
            }
            
        except Exception as e:
            print(f"⚠️ Terms generation failed: {e}")
            return {
                'terms_and_conditions': [
                    "Payment terms: Net 30 days from invoice date",
                    "Delivery: 5-10 business days after order confirmation",
                    "Warranty: Standard manufacturer warranty applies",
                    "Installation support included for first 30 days",
                    "Prices valid for 30 days from quote date"
                ],
                'implementation_notes': [
                    "Professional installation and configuration included",
                    "Complete testing and validation before handover",
                    "User training and documentation provided",
                    "30-day post-implementation support included"
                ],
                'next_steps': [
                    "Review quote details and specifications",
                    "Contact us with any questions or modifications",
                    "Submit purchase order to begin processing",
                    "Schedule implementation planning meeting"
                ]
            }
    
    async def _generate_quote_pdf(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        """Generate PDF for the quote using the PDF generator service"""
        
        try:
            print("📄 Generating PDF for quote...")
            
            # Generate PDF using the PDF generator service
            pdf_data = self.pdf_generator.generate_quote_pdf(quote)
            
            if pdf_data:
                # Save PDF to file
                quote_id = quote.get('quote_id', 'unknown')
                pdf_filename = f"quote_{quote_id}.pdf"
                pdf_path = f"Data/quotes/{pdf_filename}"
                
                # Ensure directory exists
                import os
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                
                # Write PDF data
                if isinstance(pdf_data, bytes):
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_data)
                elif isinstance(pdf_data, BytesIO):
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_data.getvalue())
                else:
                    print(f"⚠️ Unexpected PDF data type: {type(pdf_data)}")
                    return quote
                
                # Add PDF information to quote
                quote['pdf_filename'] = pdf_filename
                quote['pdf_path'] = pdf_path
                quote['pdf_url'] = f"/api/quotes/download-pdf/{quote_id}"
                quote['pdf_generated'] = True
                quote['pdf_generated_at'] = datetime.now().isoformat()
                
                print(f"✅ PDF generated successfully: {pdf_path}")
                
            else:
                print("⚠️ PDF generation returned no data")
                quote['pdf_error'] = "PDF generation failed - no data returned"
                
        except Exception as e:
            print(f"❌ PDF generation failed: {str(e)}")
            quote['pdf_error'] = f"PDF generation error: {str(e)}"
            quote['pdf_generated'] = False
            
        return quote

    # Remove the problematic get_product_catalog method entirely
    # def get_product_catalog(self):
    #     """This method should now be dynamic - fetch from Elasticsearch"""
    #     # This can be removed since we're using Elasticsearch directly
    #     pass 