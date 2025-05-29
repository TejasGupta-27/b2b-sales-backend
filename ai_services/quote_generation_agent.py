import json
import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from io import BytesIO

from .base import AIProvider, AIMessage, AIResponse
from services.pdf_generator import PDFGenerator
from services.elasticsearch_service import ElasticsearchService
from .dynamic_extraction_agent import DynamicExtractionAgent

class QuoteGenerationAgent(AIProvider):
    """Completely dynamic quote generation with zero hardcoded assumptions"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.pdf_generator = PDFGenerator()
        self.elasticsearch = ElasticsearchService()
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
        """Generate completely dynamic quote from conversation"""
        
        print(f"🔍 Quote Agent: Starting dynamic analysis...")
        
        try:
            # Extract everything dynamically
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
            
            print(f"📄 Quote Agent: Dynamic quote generated")
            return quote
            
        except Exception as e:
            print(f"❌ Quote Agent: Error - {str(e)}")
            return None
    
    async def _generate_fully_dynamic_quote(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate quote using ONLY extracted data - no assumptions"""
        
        import uuid
        from datetime import datetime, timedelta
        
        quote_id = str(uuid.uuid4())[:8]
        current_time = datetime.now()
        valid_until = current_time + timedelta(days=30)
        
        # Use extracted data directly
        customer_info = extracted_data.get('customer_info', {})
        line_items = extracted_data.get('line_items', [])
        pricing = extracted_data.get('pricing', {})
        business_context = extracted_data.get('business_context', {})
        
        # Generate dynamic company name and title based on what was extracted
        quote_title = await self._generate_dynamic_title(line_items, business_context)
        company_tagline = await self._generate_dynamic_tagline(business_context)
        
        quote = {
            "id": quote_id,
            "quote_number": f"QTE-{current_time.strftime('%Y%m%d')}-{quote_id.upper()}",
            "created_at": current_time.isoformat(),
            "valid_until": valid_until.isoformat(),
            
            # Dynamic company info
            "seller_company_name": "TechSolutions Inc.",  # This could be configurable
            "seller_tagline": company_tagline,
            
            # Dynamic quote title
            "quote_title": quote_title,
            
            # All customer info from extraction
            "customer_info": customer_info,
            
            # Dynamic section titles
            "items_section_title": await self._generate_section_title(line_items),
            "line_items": line_items,
            
            # Calculated pricing
            "pricing": pricing,
            
            # Dynamic terms
            "terms": await self._generate_dynamic_terms(line_items, business_context, pricing),
            
            # Business context
            "business_context": business_context,
            
            # Source data
            "extraction_data": extracted_data
        }
        
        return quote
    
    async def _generate_dynamic_title(self, line_items: List[Dict], business_context: Dict) -> str:
        """Generate quote title based on actual content"""
        
        title_prompt = f"""Generate a professional quote title based on these items:

Items: {[item.get('name', '') for item in line_items]}
Business context: {business_context.get('use_case', '')}

Generate a concise, professional quote title (ALL CAPS). Examples:
- GPU SERVER SOLUTION QUOTATION
- WORKSTATION UPGRADE QUOTATION  
- TECHNOLOGY INFRASTRUCTURE QUOTATION

Respond with only the title."""

        try:
            messages = [AIMessage(role="user", content=title_prompt)]
            response = await self.base_provider.generate_response(messages)
            return response.content.strip().upper()
        except:
            return "TECHNOLOGY SOLUTION QUOTATION"
    
    async def _generate_dynamic_tagline(self, business_context: Dict) -> str:
        """Generate company tagline based on customer needs"""
        
        use_case = business_context.get('use_case', '')
        if not use_case:
            return "Professional Technology Solutions"
        
        tagline_prompt = f"""Generate a short company tagline for a tech solution provider working on: {use_case}

Make it professional and relevant. Examples:
- "Specialized AI Infrastructure Solutions"
- "Enterprise Computing Excellence" 
- "Custom Technology Solutions"

Respond with only the tagline."""

        try:
            messages = [AIMessage(role="user", content=tagline_prompt)]
            response = await self.base_provider.generate_response(messages)
            return response.content.strip()
        except:
            return "Professional Technology Solutions"
    
    async def _generate_section_title(self, line_items: List[Dict]) -> str:
        """Generate section title based on items"""
        
        if not line_items:
            return "Recommended Solution"
        
        # Analyze items to create appropriate title
        item_names = [item.get('name', '') for item in line_items]
        
        title_prompt = f"""Generate a section title for these items in a quote:

Items: {item_names}

Generate a professional section title. Examples:
- "Recommended GPU Infrastructure"
- "Proposed Workstation Solution"
- "Technology Implementation Package"

Respond with only the title."""

        try:
            messages = [AIMessage(role="user", content=title_prompt)]
            response = await self.base_provider.generate_response(messages)
            return response.content.strip()
        except:
            return "Recommended Solution"
    
    async def _generate_dynamic_terms(self, line_items: List[Dict], business_context: Dict, pricing: Dict) -> List[str]:
        """Generate terms based on actual quote content"""
        
        terms_prompt = f"""Generate appropriate terms and conditions for this quote:

Items: {[item.get('name', '') for item in line_items]}
Total value: ${pricing.get('total', 0):,.2f}
Business context: {business_context}

Generate 5-7 relevant terms and conditions. Consider:
- Quote validity period
- Payment terms based on value
- Delivery/installation terms
- Warranty terms
- Support terms

Respond with a JSON array of terms."""

        try:
            messages = [AIMessage(role="user", content=terms_prompt)]
            response = await self.base_provider.generate_response(messages)
            terms = json.loads(response.content.strip())
            return terms if isinstance(terms, list) else []
        except:
            return [
                "Quote valid for 30 days from issue date",
                "Payment terms based on total value",
                "Professional installation included where applicable",
                "Warranty coverage as specified per item",
                "Technical support included"
            ]
    
    async def _generate_quote_pdf(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        """Generate PDF for the quote"""
        
        try:
            print(f"📄 Quote Agent: Generating PDF for quote {quote['id']}")
            
            pdf_filename = f"quote_{quote['id']}.pdf"
            file_path = self.pdf_generator.save_pdf_to_file(quote, pdf_filename)
            
            # Add PDF information to quote
            quote['pdf_filename'] = pdf_filename
            quote['pdf_path'] = file_path
            quote['pdf_url'] = f"/api/quotes/download-pdf/{quote['id']}"
            
            print(f"✅ Quote Agent: PDF generated successfully at {file_path}")
            
        except Exception as e:
            print(f"❌ Quote Agent: PDF generation failed - {e}")
            import traceback
            traceback.print_exc()
            quote['pdf_error'] = str(e)
        
        return quote

    # Remove the problematic get_product_catalog method entirely
    # def get_product_catalog(self):
    #     """This method should now be dynamic - fetch from Elasticsearch"""
    #     # This can be removed since we're using Elasticsearch directly
    #     pass 