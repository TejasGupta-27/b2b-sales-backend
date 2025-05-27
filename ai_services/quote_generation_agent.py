import json
import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from io import BytesIO

from .base import AIProvider, AIMessage, AIResponse
from services.pdf_generator import PDFGenerator

class QuoteGenerationAgent(AIProvider):
    """Specialized agent purely for quote generation and PDF handling"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.pdf_generator = PDFGenerator()
        self.hardware_catalog = self._load_hardware_catalog()
        
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
        """Analyze conversation and generate comprehensive quote with PDF"""
        
        print(f"🔍 Quote Agent: Analyzing conversation for quote requirements...")
        print(f"📝 Messages to analyze: {len(conversation_messages)}")
        
        # Extract technical requirements from sales conversation
        requirements = await self._extract_requirements_from_conversation(
            conversation_messages, 
            customer_context
        )
        
        if not requirements:
            print("❌ Quote Agent: No extractable requirements found")
            return None
            
        print(f"✅ Quote Agent: Extracted {len(requirements.get('hardware_items', []))} hardware items")
        
        # Generate comprehensive quote
        quote = self._generate_comprehensive_quote(requirements)
        
        # Generate PDF automatically
        quote = await self._generate_quote_pdf(quote)
        
        print(f"📄 Quote Agent: Complete quote generated with ID {quote['id']}")
        return quote
    
    async def _extract_requirements_from_conversation(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Extract technical requirements using AI analysis + fallback logic"""
        
        # Build conversation context
        conversation_text = "\n".join([
            f"{msg.role}: {msg.content}" for msg in messages[-12:]  # More context for better extraction
        ])
        
        print(f"🤖 Quote Agent: Using AI to extract requirements...")
        
        try:
            # Try AI-powered extraction first
            requirements = await self._ai_powered_extraction(conversation_text, customer_context)
            if requirements and requirements.get('hardware_items'):
                print(f"✅ AI extraction successful")
                return requirements
        except Exception as e:
            print(f"⚠️ AI extraction failed: {e}")
        
        print(f"🔄 Quote Agent: Falling back to pattern matching...")
        # Fallback to pattern matching
        return self._pattern_based_extraction(conversation_text, customer_context)
    
    async def _ai_powered_extraction(
        self, 
        conversation_text: str, 
        customer_context: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Use AI to intelligently extract requirements"""
        
        extraction_prompt = """You are a technical requirements analyst. Extract hardware requirements from this sales conversation.

ANALYZE FOR:
1. Workstation needs (specifications, quantity)
2. Storage requirements (capacity, RAID level, type)
3. Networking needs (speed, switches, infrastructure)
4. Display requirements (size, resolution, quantity)
5. Services needed (installation, support, training)

RETURN ONLY valid JSON in this exact format:
{
    "hardware_items": [
        {
            "category": "workstation|storage|networking|monitor|service",
            "name": "Specific product name",
            "description": "Detailed description with key specs",
            "specifications": {"key": "value"},
            "quantity": 1,
            "estimated_price": 1999,
            "justification": "Business reason for this item"
        }
    ],
    "total_estimated_budget": 5000,
    "confidence_level": 0.8,
    "extraction_notes": "Key requirements identified"
}

Be specific about quantities, specifications, and pricing. Only include items clearly discussed in the conversation."""
        
        messages = [
            AIMessage(role="system", content=extraction_prompt),
            AIMessage(role="user", content=f"""CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT:
{json.dumps(customer_context or {}, indent=2)}

Extract technical requirements as JSON:""")
        ]
        
        response = await self.base_provider.generate_response(messages)
        
        # Parse JSON from response
        json_start = response.content.find('{')
        json_end = response.content.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            requirements_json = response.content[json_start:json_end]
            requirements = json.loads(requirements_json)
            
            # Validate and enhance
            if requirements.get('hardware_items'):
                requirements['customer_info'] = customer_context or {}
                requirements['extraction_method'] = 'ai_powered'
                return requirements
        
        return None
    
    def _pattern_based_extraction(
        self, 
        conversation_text: str, 
        customer_context: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Fallback pattern-based extraction with improved detection"""
        
        conversation_lower = conversation_text.lower()
        hardware_items = []
        
        print(f"🔍 Pattern matching analysis...")
        
        # Enhanced workstation detection
        workstation_patterns = ['workstation', 'desktop', 'computer', 'pc', 'machine']
        if any(pattern in conversation_lower for pattern in workstation_patterns):
            
            # Extract RAM requirements
            ram_match = re.search(r'(\d+)\s*gb.*(?:ram|memory)', conversation_lower)
            ram_size = f"{ram_match.group(1)}GB" if ram_match else "64GB"
            
            # Determine tier based on conversation context
            if any(term in conversation_lower for term in ['professional', 'enterprise', 'high-performance', 'demanding']):
                workstation = {
                    "category": "workstation",
                    "name": "Workstation Pro - Enterprise",
                    "description": f"High-performance enterprise workstation with {ram_size} RAM, 1TB NVMe SSD",
                    "specifications": {"processor": "Intel Core i9", "ram": ram_size, "storage": "1TB NVMe SSD"},
                    "quantity": 1,
                    "estimated_price": 1999,
                    "justification": "Enterprise-grade performance for demanding business applications"
                }
            else:
                workstation = {
                    "category": "workstation",
                    "name": "Workstation Pro - Professional",
                    "description": f"Professional workstation with {ram_size} RAM, 512GB SSD",
                    "specifications": {"processor": "Intel Core i7", "ram": ram_size, "storage": "512GB SSD"},
                    "quantity": 1,
                    "estimated_price": 1299,
                    "justification": "Professional workstation for business productivity"
                }
            
            hardware_items.append(workstation)
            print(f"✅ Found workstation requirement")
        
        # Enhanced storage detection
        storage_patterns = ['storage', 'nas', 'raid', 'backup', 'data']
        tb_match = re.search(r'(\d+)\s*tb', conversation_lower)
        
        if any(pattern in conversation_lower for pattern in storage_patterns) or tb_match:
            capacity = f"{tb_match.group(1)}TB" if tb_match else "10TB"
            
            if 'raid' in conversation_lower:
                # RAID storage solution
                hardware_items.append({
                    "category": "storage",
                    "name": f"Enterprise NAS RAID 5 Array - {capacity}",
                    "description": f"Professional NAS with {capacity} usable capacity, RAID 5 protection",
                    "specifications": {"capacity": capacity, "raid_level": "RAID 5", "drives": "4x 8TB Enterprise HDDs"},
                    "quantity": 1,
                    "estimated_price": 1000,
                    "justification": "Redundant storage for business data protection"
                })
                print(f"✅ Found RAID storage requirement")
            else:
                # Standard storage
                hardware_items.append({
                    "category": "storage",
                    "name": f"Business Storage Solution - {capacity}",
                    "description": f"Professional storage solution with {capacity} capacity",
                    "specifications": {"capacity": capacity, "type": "Enterprise"},
                    "quantity": 1,
                    "estimated_price": 600,
                    "justification": "Reliable storage for business data"
                })
                print(f"✅ Found storage requirement")
        
        # Enhanced networking detection
        network_patterns = ['10gbe', '10 gigabit', '10gb', 'networking', 'switch', 'network']
        if any(pattern in conversation_lower for pattern in network_patterns):
            
            # 10GbE NIC
            hardware_items.append({
                "category": "networking",
                "name": "10 Gigabit Ethernet Network Card",
                "description": "PCIe 10GbE network interface card for high-speed connectivity",
                "specifications": {"speed": "10 Gbps", "interface": "PCIe x8"},
                "quantity": 1,
                "estimated_price": 300,
                "justification": "High-speed network connectivity for demanding applications"
            })
            
            # 10GbE Switch
            hardware_items.append({
                "category": "networking", 
                "name": "8-Port 10 Gigabit Ethernet Switch",
                "description": "Managed 8-port 10GbE switch for enterprise networking",
                "specifications": {"ports": 8, "speed": "10 Gbps", "management": "Web-managed"},
                "quantity": 1,
                "estimated_price": 800,
                "justification": "Network infrastructure for high-performance connectivity"
            })
            print(f"✅ Found networking requirements")
        
        # Monitor detection
        monitor_patterns = ['monitor', 'display', 'screen', '4k', 'professional display']
        if any(pattern in conversation_lower for pattern in monitor_patterns):
            hardware_items.append({
                "category": "monitor",
                "name": "Professional 4K Monitor - 27\"",
                "description": "27-inch 4K UHD professional display with color accuracy",
                "specifications": {"size": "27 inches", "resolution": "4K UHD (3840x2160)", "features": "USB-C, HDR"},
                "quantity": 1,
                "estimated_price": 399,
                "justification": "Professional display for detailed work and presentations"
            })
            print(f"✅ Found monitor requirement")
        
        if not hardware_items:
            print(f"❌ No hardware requirements detected in patterns")
            return None
        
        # Always add professional services
        hardware_items.append({
            "category": "service",
            "name": "Professional Installation & Setup",
            "description": "Complete installation, configuration, and testing of all hardware",
            "specifications": {"timeline": "1-2 weeks", "includes": "Configuration, testing, training"},
            "quantity": 1,
            "estimated_price": 300,
            "justification": "Professional setup ensures optimal performance and reliability"
        })
        
        total_budget = sum(item['estimated_price'] * item['quantity'] for item in hardware_items)
        
        return {
            "hardware_items": hardware_items,
            "total_estimated_budget": total_budget,
            "timeline": "1-2 weeks",
            "special_requirements": ["Professional installation", "Warranty support", "Performance optimization"],
            "confidence_level": 0.8,
            "extraction_method": "pattern_based",
            "customer_info": customer_context or {}
        }
    
    def _generate_comprehensive_quote(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a comprehensive, professional quote"""
        
        hardware_items = requirements.get('hardware_items', [])
        customer_info = requirements.get('customer_info', {})
        
        # Calculate pricing with professional structure
        subtotal = sum(item['estimated_price'] * item['quantity'] for item in hardware_items)
        
        # Apply volume discounts if applicable
        if len(hardware_items) >= 5:
            volume_discount = subtotal * 0.05  # 5% for complex solutions
            subtotal -= volume_discount
        
        tax_rate = 0.08
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        # Build professional line items
        line_items = []
        for item in hardware_items:
            line_items.append({
                "name": item['name'],
                "description": item['description'],
                "specifications": item.get('specifications', {}),
                "quantity": item['quantity'],
                "unit_price": item['estimated_price'],
                "total_price": item['estimated_price'] * item['quantity'],
                "category": item['category'],
                "justification": item.get('justification', '')
            })
        
        # Generate comprehensive quote
        quote = {
            "id": str(uuid.uuid4()),
            "quote_number": f"QUO-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
            "created_at": datetime.now().isoformat(),
            "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
            
            "customer_info": {
                "company_name": customer_info.get("company_name", "Valued Customer"),
                "contact_name": customer_info.get("contact_name", ""),
                "email": customer_info.get("email", ""),
                "company_size": customer_info.get("company_size", ""),
                "industry": customer_info.get("industry", ""),
                "budget_range": customer_info.get("budget_range", ""),
                "timeline": customer_info.get("timeline", "")
            },
            
            "line_items": line_items,
            
            "pricing": {
                "subtotal": subtotal,
                "tax_rate": tax_rate,
                "tax_amount": tax_amount,
                "total": total,
                "currency": "USD"
            },
            
            "solution_summary": {
                "total_items": len(line_items),
                "categories": list(set([item['category'] for item in line_items])),
                "key_benefits": [
                    "Enterprise-grade reliability and performance",
                    "Professional installation and configuration", 
                    "Comprehensive warranty and support",
                    "Scalable for future business growth"
                ]
            },
            
            "terms": [
                "Quote valid for 30 days from issue date",
                "Professional installation and setup included",
                "3-year comprehensive warranty on all hardware",
                "Payment terms: Net 30 days for approved accounts",
                "24/7 technical support included for first year",
                "Training and documentation provided"
            ],
            
            "next_steps": [
                "Review quote details and specifications",
                "Schedule implementation planning meeting",
                "Finalize delivery and installation timeline",
                "Process purchase order and initiate delivery"
            ],
            
            "requirements": requirements
        }
        
        return quote
    
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
    
    def _load_hardware_catalog(self) -> List[Dict[str, Any]]:
        """Load hardware catalog for quote generation"""
        return [
            {
                "category": "workstation",
                "models": [
                    {"name": "Workstation Pro Professional", "base_price": 1299, "specs": {"ram": "32GB", "storage": "512GB SSD"}},
                    {"name": "Workstation Pro Enterprise", "base_price": 1999, "specs": {"ram": "64GB", "storage": "1TB SSD"}}
                ]
            },
            {
                "category": "storage", 
                "models": [
                    {"name": "Enterprise HDD 8TB", "base_price": 250, "specs": {"capacity": "8TB", "type": "Enterprise"}},
                    {"name": "NAS RAID Array", "base_price": 1000, "specs": {"raid": "RAID 5", "capacity": "Variable"}}
                ]
            },
            {
                "category": "networking",
                "models": [
                    {"name": "10GbE Network Card", "base_price": 300, "specs": {"speed": "10 Gbps"}},
                    {"name": "10GbE Switch 8-port", "base_price": 800, "specs": {"ports": 8, "speed": "10 Gbps"}}
                ]
            }
        ] 