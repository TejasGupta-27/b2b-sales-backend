import json
import re
from typing import List, Dict, Any, Optional
from .base import AIProvider, AIMessage, AIResponse
from .function_models import QuoteData, CustomerInfo, QuoteLineItem

class DynamicExtractionAgent(AIProvider):
    """Completely dynamic data extraction using Pydantic function calling"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        
    @property
    def provider_name(self) -> str:
        return f"dynamic_extraction_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        return AIResponse(
            content="Dynamic Extraction Agent - use extract_data method",
            model="dynamic-extraction-agent",
            provider=self.provider_name,
            usage={}
        )
    
    async def extract_data(
        self,
        conversation_messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Extract quote data using Pydantic function calling"""
        
        conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in conversation_messages])
        
        extraction_prompt = f"""Extract all information needed to generate a business quote from this conversation.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT: {customer_context or 'None'}

Extract:
- Customer information (company, contact, email, phone, industry)
- All products/services mentioned with descriptions, quantities, and pricing
- Business requirements and context
- Calculate pricing where needed

IMPORTANT REQUIREMENTS:
1. Each line item MUST include:
   - name: descriptive product/service name
   - description: what this item provides
   - quantity: number of units (minimum 1)
   - unit_price: price per unit in USD
   - total_price: unit_price × quantity
   - specifications: technical details (can be empty dict {{}})

2. Business context should include:
   - use_case: primary purpose/application
   - requirements: key business needs
   - timeline: project timeline if mentioned
   - industry_context: relevant industry information

3. All monetary amounts should be realistic and in USD
4. If specific pricing isn't mentioned, provide reasonable estimates based on the products discussed

Only extract information that was explicitly mentioned or can be reasonably inferred from the conversation.
Ensure ALL required fields are provided with appropriate values."""

        try:
            # Use structured response with Pydantic
            quote_data = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=extraction_prompt)],
                QuoteData
            )
            
            return quote_data.model_dump()
            
        except Exception as e:
            print(f"⚠️ Pydantic quote extraction failed: {e}")
            # Enhanced fallback with proper field structure
            return self._enhanced_fallback_extraction(conversation_text, customer_context)
    
    def _enhanced_fallback_extraction(self, conversation_text: str, customer_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhanced fallback extraction with proper Pydantic structure"""
        
        # Extract basic information using patterns
        import re
        
        # Extract quantities and products
        quantities = re.findall(r'\b(\d+)\s*(?:x\s*|units?\s*|pieces?\s*|servers?\s*)', conversation_text, re.IGNORECASE)
        prices = re.findall(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', conversation_text)
        
        # Extract product mentions
        product_keywords = ['server', 'gpu', 'workstation', 'storage', 'network', 'nas', 'drive', 'ssd', 'hdd']
        mentioned_products = [kw for kw in product_keywords if kw in conversation_text.lower()]
        
        # Build line items with all required fields
        line_items = []
        for i, product in enumerate(mentioned_products):
            quantity = int(quantities[i]) if i < len(quantities) else 1
            unit_price = float(prices[i].replace(',', '')) if i < len(prices) else 1000.0
            
            line_items.append({
                "name": f"{product.title()} Solution",
                "description": f"Professional {product} solution based on customer requirements",
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": unit_price * quantity,
                "specifications": {}  # Empty dict as default
            })
        
        # If no products found, create a generic item
        if not line_items:
            line_items.append({
                "name": "Technology Solution",
                "description": "Custom technology solution based on discussion",
                "quantity": 1,
                "unit_price": 5000.0,
                "total_price": 5000.0,
                "specifications": {}
            })
        
        # Calculate totals
        subtotal = sum(item["total_price"] for item in line_items)
        tax_rate = 0.08
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        # Build customer info
        customer_info = {
            "company": None,
            "contact": None,
            "email": None,
            "phone": None,
            "industry": None
        }
        
        # Merge customer context if available
        if customer_context:
            for key in customer_info.keys():
                if key in customer_context:
                    customer_info[key] = customer_context[key]
        
        # Build business context
        business_context = {
            "use_case": "Technology solution",
            "requirements": ["Technology upgrade", "Business improvement"],
            "timeline": "Standard delivery",
            "industry_context": customer_info.get("industry", "General business")
        }
        
        return {
            "customer_info": customer_info,
            "line_items": line_items,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total": total,
            "currency": "USD",
            "business_context": business_context
        }
    
    async def _analyze_discussion_content(self, conversation_text: str) -> Dict[str, Any]:
        """First pass: Understand what is being discussed"""
        
        analysis_prompt = f"""Analyze this business conversation and tell me exactly what is being discussed.

CONVERSATION:
{conversation_text}

Please analyze and respond with:

1. WHAT PRODUCTS/SERVICES are being discussed? (be specific about what was mentioned)
2. WHAT QUANTITIES or numbers were mentioned?
3. WHAT PRICES or budget amounts were discussed?
4. WHO is the customer? (name, company, contact info mentioned)
5. WHAT TECHNICAL SPECIFICATIONS were mentioned?
6. WHAT TIMELINE or urgency was discussed?
7. WHAT USE CASE or purpose was mentioned?

Be very specific and only mention things that were actually said in the conversation. If something wasn't mentioned, say "Not mentioned"."""

        try:
            messages = [AIMessage(role="user", content=analysis_prompt)]
            response = await self.base_provider.generate_response(messages)
            
            # Parse the analysis
            return self._parse_discussion_analysis(response.content)
            
        except Exception as e:
            print(f"⚠️ Discussion analysis failed: {e}")
            return {}
    
    def _parse_discussion_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse the discussion analysis into structured data"""
        
        analysis = {
            "products_services": [],
            "quantities": [],
            "prices": [],
            "customer_info": {},
            "technical_specs": {},
            "timeline": None,
            "use_case": None
        }
        
        # Extract products/services mentioned
        if "products/services" in analysis_text.lower():
            # Look for bullet points or lists after this section
            products_section = re.search(r'products/services.*?(?=\d\.|$)', analysis_text, re.IGNORECASE | re.DOTALL)
            if products_section:
                analysis["products_services"] = self._extract_list_items(products_section.group())
        
        # Extract quantities
        quantity_matches = re.findall(r'(\d+)\s*(?:x\s*|times\s*|units?\s*|pieces?\s*)', analysis_text, re.IGNORECASE)
        analysis["quantities"] = [int(q) for q in quantity_matches]
        
        # Extract prices
        price_matches = re.findall(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', analysis_text)
        analysis["prices"] = [float(p.replace(',', '')) for p in price_matches]
        
        return analysis
    
    def _extract_list_items(self, text: str) -> List[str]:
        """Extract list items from text"""
        
        items = []
        # Look for bullet points, dashes, or numbered items
        patterns = [
            r'[-•*]\s*(.+)',
            r'\d+\.\s*(.+)',
            r'["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            items.extend([match.strip() for match in matches if match.strip()])
        
        return list(set(items))  # Remove duplicates
    
    async def _extract_mentioned_data(self, conversation_text: str, discussion_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Second pass: Extract specific data points that were mentioned"""
        
        extraction_prompt = f"""Extract specific data points from this conversation. Only extract information that was explicitly mentioned.

CONVERSATION:
{conversation_text}

INITIAL ANALYSIS:
{json.dumps(discussion_analysis, indent=2)}

...(about 64 lines omitted)...
        }}
    ],
    "customer": {{
        "company": "company name or null",
        "contact": "contact name or null",
        "email": "email or null",
        "phone": "phone or null",
        "industry": "industry or null"
    }},
    "business_needs": {{
        "use_case": "primary use case mentioned",
        "timeline": "timeline mentioned",
        "budget_mentioned": "budget amount or null",
        "special_requirements": ["list of special requirements"]
    }}
}}

IMPORTANT: Only include information that was actually mentioned in the conversation. Use null for anything not mentioned."""

        try:
            messages = [AIMessage(role="user", content=extraction_prompt)]
            response = await self.base_provider.generate_response(messages)
            
            # Parse JSON response
            return json.loads(response.content.strip())
            
        except Exception as e:
            print(f"⚠️ Data extraction failed: {e}")
            # Fallback to pattern extraction
            return self._pattern_extract_data(conversation_text)
    
    def _pattern_extract_data(self, conversation_text: str) -> Dict[str, Any]:
        """Fallback pattern-based extraction"""
        
        # Extract any numbers that might be quantities
        quantities = re.findall(r'\b(\d+)\s*(?:x\s*|units?\s*|pieces?\s*|servers?\s*)', conversation_text, re.IGNORECASE)
        
        # Extract any prices
        prices = re.findall(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', conversation_text)
        
        # Extract any product mentions
        product_keywords = ['server', 'gpu', 'workstation', 'storage', 'network', 'hardware']
        mentioned_products = [kw for kw in product_keywords if kw in conversation_text.lower()]
        
        return {
            "items": [
                {
                    "mentioned_name": f"{prod.title()} mentioned in conversation",
                    "description": f"Customer discussed {prod} requirements",
                    "quantity_mentioned": int(quantities[0]) if quantities else None,
                    "price_mentioned": float(prices[0].replace(',', '')) if prices else None,
                    "specs_mentioned": {},
                    "context": "Extracted from conversation"
                }
                for prod in mentioned_products
            ],
            "customer": {},
            "business_needs": {
                "use_case": "Technology solution",
                "timeline": None,
                "budget_mentioned": float(prices[0].replace(',', '')) if prices else None,
                "special_requirements": []
            }
        }
    
    async def _structure_extracted_data(self, extracted_data: Dict[str, Any], customer_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Structure the extracted data for quote generation"""
        
        # Merge customer context with extracted customer info
        customer_info = extracted_data.get("customer", {})
        if customer_context:
            for key, value in customer_context.items():
                if not customer_info.get(key) and value:
                    customer_info[key] = value
        
        # Convert extracted items to line items
        line_items = []
        for item in extracted_data.get("items", []):
            # Use mentioned price or estimate if needed
            unit_price = item.get("price_mentioned")
            if not unit_price:
                # Ask AI to estimate price based on item description
                unit_price = await self._estimate_price(item)
            
            quantity = item.get("quantity_mentioned", 1)
            
            line_items.append({
                "name": item.get("mentioned_name", "Technology Solution"),
                "description": item.get("description", "Professional technology solution"),
                "quantity": quantity,
                "unit_price": float(unit_price or 0),
                "total_price": float(unit_price or 0) * quantity,
                "specifications": item.get("specs_mentioned", {}),
                "context": item.get("context", "")
            })
        
        # Calculate pricing
        subtotal = sum(item["total_price"] for item in line_items)
        tax_rate = 0.08  # Could be extracted from conversation too
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        return {
            "customer_info": customer_info,
            "line_items": line_items,
            "pricing": {
                "subtotal": subtotal,
                "tax_rate": tax_rate,
                "tax_amount": tax_amount,
                "total": total,
                "currency": "USD"
            },
            "business_context": extracted_data.get("business_needs", {}),
            "extraction_source": "dynamic_conversation_analysis"
        }
    
    async def _estimate_price(self, item: Dict[str, Any]) -> float:
        """Use AI to estimate price for items without mentioned prices"""
        
        estimation_prompt = f"""Based on this item description, provide a reasonable price estimate for a business quote:

Item: {item.get('mentioned_name', 'Unknown')}
Description: {item.get('description', 'No description')}
Context: {item.get('context', 'No context')}
Specifications: {item.get('specs_mentioned', {})}

Provide only a number (the price in USD) - no text, no explanation, just the estimated price."""

        try:
            messages = [AIMessage(role="user", content=estimation_prompt)]
            response = await self.base_provider.generate_response(messages)
            
            # Extract number from response
            price_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d{2})?)', response.content)
            if price_match:
                return float(price_match.group(1).replace(',', ''))
            
        except Exception:
            pass
        
        # Fallback to basic estimation
        return 5000.0  # Default estimate