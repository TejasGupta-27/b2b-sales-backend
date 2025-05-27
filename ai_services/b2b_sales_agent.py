import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
from io import BytesIO

from .base import AIProvider, AIMessage, AIResponse
from .quote_generation_agent import QuoteGenerationAgent
from models.catalog import Product, Quote, QuoteRequest

class B2BSalesAgent(AIProvider):
    """B2B Sales Agent focused on selling, recommendations, and customer interaction"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.product_catalog = self._load_product_catalog()
        
        # Initialize quote generation agent for collaboration
        self.quote_agent = QuoteGenerationAgent(base_provider)
        
        # Store conversation context for quote collaboration
        self.conversation_context = []
    
    @property
    def provider_name(self) -> str:
        return f"b2b_sales_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate sales-focused responses with automatic quote generation when appropriate"""
        
        # Store conversation for potential quote generation
        self.conversation_context = messages
        
        # Enhance messages with sales context and product knowledge
        enhanced_messages = self._add_sales_context(messages, customer_context)
        
        # Generate sales response
        response = await self.base_provider.generate_response(enhanced_messages, **kwargs)
        
        # Check if we should collaborate with quote agent
        enhanced_response = await self._collaborate_with_quote_agent(response, customer_context)
        
        return enhanced_response
    
    async def _collaborate_with_quote_agent(self, response: AIResponse, customer_context: Optional[Dict]) -> AIResponse:
        """Collaborate with quote agent when customer is ready for quotes"""
        
        # Ensure response has metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        # Check if customer is asking for quotes or we've discussed enough technical details
        if self._should_generate_quote(response.content, self.conversation_context):
            
            print(f"DEBUG: Sales agent collaborating with quote agent...")
            
            # Let quote agent analyze the conversation and generate quote
            quote = await self.quote_agent.generate_quote_from_conversation(
                self.conversation_context,
                customer_context
            )
            
            if quote:
                print(f"DEBUG: Quote agent provided quote with ID: {quote.get('id')}")
                
                # Add quote to response metadata
                response.metadata['quote'] = quote
                
                # Enhance sales response to incorporate the quote
                response = self._enhance_response_with_quote(response, quote)
            else:
                print("DEBUG: Quote agent couldn't generate quote from conversation")
        
        return response
    
    def _enhance_response_with_quote(self, response: AIResponse, quote: Dict[str, Any]) -> AIResponse:
        """Enhance the sales response to incorporate the generated quote"""
        
        if 'pdf_url' in quote:
            # Add professional quote presentation
            response.content += f"\n\n🎯 **Perfect! I've prepared a detailed quote for you based on our discussion.**"
            response.content += f"\n\n📋 **Quote #{quote.get('quote_number', 'N/A')}**"
            
            # Add pricing summary
            if 'pricing' in quote:
                pricing = quote['pricing']
                response.content += f"\n\n💰 **Investment Summary:**"
                response.content += f"\n• Subtotal: **${pricing['subtotal']:,.2f}**"
                response.content += f"\n• Tax: ${pricing['tax_amount']:,.2f}"
                response.content += f"\n• **Total Investment: ${pricing['total']:,.2f}**"
                response.content += f"\n• Quote valid until: {datetime.fromisoformat(quote['valid_until']).strftime('%B %d, %Y')}"
            
            # Add PDF download link
            response.content += f"\n\n📄 **[Download Complete Quote PDF]({quote['pdf_url']})**"
            
            # Add next steps as a sales professional would
            response.content += f"\n\n**Next Steps:**"
            response.content += f"\n1. Review the detailed quote and specifications"
            response.content += f"\n2. Let me know if you'd like any adjustments or have questions"
            response.content += f"\n3. I can arrange a demo or site visit if helpful"
            response.content += f"\n4. We can discuss implementation timeline and support options"
            
            response.content += f"\n\nI'm here to answer any questions and help customize this solution for your specific needs! 🚀"
            
        elif 'pdf_error' in quote:
            response.content += f"\n\nI've analyzed your requirements and prepared a quote, but encountered a technical issue with the PDF generation. Let me get this resolved for you right away."
            
        return response
    
    def _should_generate_quote(self, content: str, conversation: List[AIMessage]) -> bool:
        """Determine when sales conversation is ready for quote generation"""
        if not content:
            return False
        
        content_lower = content.lower()
        
        # Direct quote requests
        quote_keywords = [
            "quote", "quotation", "pricing", "price", "cost", "how much",
            "proposal", "estimate", "budget", "investment", "total"
        ]
        
        # Check if customer is explicitly asking for pricing
        explicit_request = any(keyword in content_lower for keyword in quote_keywords)
        
        # Check if we've discussed technical requirements in depth
        tech_discussion_indicators = [
            "workstation", "server", "storage", "tb", "raid", "networking",
            "10gbe", "gigabit", "monitor", "display", "specs", "requirements",
            "setup", "implementation", "delivery"
        ]
        
        # Look at recent conversation for technical depth
        recent_messages = conversation[-8:] if len(conversation) > 8 else conversation
        recent_text = " ".join([msg.content.lower() for msg in recent_messages if msg.content])
        
        tech_discussion_depth = sum(1 for indicator in tech_discussion_indicators if indicator in recent_text)
        has_substantial_tech_discussion = tech_discussion_depth >= 3
        
        # Generate quote if:
        # 1. Customer explicitly asks for pricing/quote, OR
        # 2. We've had substantial technical discussion AND there's any pricing mention
        should_generate = explicit_request or (
            has_substantial_tech_discussion and 
            any(word in content_lower for word in ["price", "cost", "budget", "afford"])
        )
        
        print(f"DEBUG: Quote decision - explicit_request: {explicit_request}, tech_depth: {tech_discussion_depth}, should_generate: {should_generate}")
        
        return should_generate
    
    def _add_sales_context(self, messages: List[AIMessage], customer_context: Optional[Dict]) -> List[AIMessage]:
        """Add comprehensive B2B sales context"""
        
        system_prompt = self._build_sales_system_prompt()
        product_info = self._build_product_context()
        
        enhanced_messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="system", content=product_info),
        ]
        
        # Add customer context if available
        if customer_context:
            customer_info = self._build_customer_context(customer_context)
            enhanced_messages.append(AIMessage(role="system", content=customer_info))
        
        # Add conversation history
        enhanced_messages.extend(messages)
        
        return enhanced_messages
    
    def _build_sales_system_prompt(self) -> str:
        """Build comprehensive sales system prompt focused on selling and relationship building"""
        return """You are an elite B2B sales consultant specializing in business technology solutions. Your primary mission is to understand customer needs and guide them toward the perfect technology solution.

🎯 YOUR CORE OBJECTIVES:
1. BUILD RAPPORT and understand the customer's business challenges
2. DISCOVER specific technical requirements through strategic questioning
3. RECOMMEND optimal hardware solutions that solve real business problems
4. CREATE VALUE by explaining ROI, efficiency gains, and competitive advantages
5. GUIDE customers toward purchase decisions with confidence and urgency

💼 SALES METHODOLOGY:
- Use consultative selling approach - be a trusted advisor, not just a vendor
- Ask open-ended questions to uncover pain points and requirements
- Listen actively and probe deeper into technical specifications
- Present solutions as investments in business growth and efficiency
- Create urgency through limited-time offers and implementation timelines
- Always advance the conversation toward a purchase decision

🔧 TECHNICAL EXPERTISE AREAS:
- Business workstations and high-performance computing
- Enterprise storage solutions (NAS, RAID, backup systems)
- Networking infrastructure (switches, routers, 10GbE solutions)
- Professional displays and productivity peripherals
- Server solutions and virtualization platforms
- Implementation, support, and managed services

💡 QUESTIONING STRATEGY:
- "What business challenges are you trying to solve?"
- "How many users will need access to this system?"
- "What's your current setup, and where are the bottlenecks?"
- "What's driving the urgency for this upgrade?"
- "What would success look like for your organization?"
- "What's your timeline for implementation?"
- "Have you allocated budget for this initiative?"

🏆 VALUE PROPOSITION FOCUS:
- Productivity improvements and time savings
- Reliability and reduced downtime costs
- Scalability for future business growth
- Security and data protection benefits
- Professional support and warranty coverage
- Total cost of ownership advantages

📈 SALES TECHNIQUES:
- Use pain-agitation-solution methodology
- Present multiple options (good, better, best)
- Leverage social proof and success stories
- Create comparison with current limitations
- Emphasize competitive advantages
- Build urgency with availability and pricing
- Always ask for the next commitment

🎨 COMMUNICATION STYLE:
- Professional yet personable and enthusiastic
- Confident in product knowledge and recommendations
- Empathetic to business challenges and constraints
- Results-oriented and solution-focused
- Clear about value propositions and next steps

Remember: You're not just selling hardware - you're selling business transformation, competitive advantage, and peace of mind. Every interaction should move closer to a purchase decision while building long-term customer relationships."""

    def _build_product_context(self) -> str:
        """Build context about available products for sales conversations"""
        context = "🛍️ YOUR PRODUCT PORTFOLIO:\n\n"
        
        # Focus on business value and sales positioning
        context += "=== WORKSTATION SOLUTIONS ===\n"
        context += "• Professional Tier ($1,299): Perfect for growing businesses, handles demanding applications\n"
        context += "• Enterprise Tier ($1,999): For mission-critical work, maximum performance and reliability\n"
        context += "• Benefits: Productivity gains, reduced downtime, professional warranty support\n\n"
        
        context += "=== STORAGE & NETWORKING ===\n"
        context += "• Enterprise NAS Solutions: Scalable storage with RAID protection\n"
        context += "• 10 Gigabit Networking: Future-proof speed for demanding workflows\n"
        context += "• Professional Displays: 4K clarity for detailed work and presentations\n\n"
        
        context += "=== SERVICE & SUPPORT ===\n"
        context += "• Professional Installation & Setup (Included)\n"
        context += "• 3-Year On-site Warranty & Support\n"
        context += "• Training and Knowledge Transfer\n"
        context += "• Ongoing Technical Support\n\n"
        
        context += "💰 PRICING ADVANTAGES:\n"
        context += "• Volume discounts for multi-unit purchases\n"
        context += "• Bundle savings on complete solutions\n"
        context += "• Trade-in programs for existing equipment\n"
        context += "• Flexible payment terms for enterprise customers\n"
        
        return context
    
    def _build_customer_context(self, customer_context: Dict[str, Any]) -> str:
        """Build customer context for personalized sales approach"""
        context = f"👤 CUSTOMER PROFILE:\n"
        
        if customer_context.get('company_name'):
            context += f"Company: {customer_context['company_name']}\n"
        if customer_context.get('industry'):
            context += f"Industry: {customer_context['industry']}\n"
        if customer_context.get('company_size'):
            context += f"Size: {customer_context['company_size']}\n"
        if customer_context.get('budget_range'):
            context += f"Budget Range: {customer_context['budget_range']}\n"
        if customer_context.get('timeline'):
            context += f"Timeline: {customer_context['timeline']}\n"
        if customer_context.get('pain_points'):
            context += f"Pain Points: {', '.join(customer_context['pain_points'])}\n"
        
        context += "\nUse this information to personalize your approach and recommendations."
        
        return context
    
    def _load_product_catalog(self) -> List[Dict[str, Any]]:
        """Load product catalog optimized for sales conversations"""
        return [
            {
                "id": "workstation-pro",
                "name": "Workstation Pro",
                "category": "desktop",
                "description": "High-performance business workstation",
                "sales_points": [
                    "Boost productivity with professional-grade performance",
                    "Reduce downtime with enterprise reliability",
                    "Future-proof with latest Intel processors",
                    "Professional warranty and support included"
                ],
                "ideal_for": ["Design firms", "Engineering", "Financial services", "Healthcare"],
                "pricing_tiers": [
                    {
                        "name": "Professional",
                        "price": 1299,
                        "value_props": ["Cost-effective performance", "3-year warranty"],
                        "best_for": "Growing businesses"
                    },
                    {
                        "name": "Enterprise", 
                        "price": 1999,
                        "value_props": ["Maximum performance", "Premium support"],
                        "best_for": "Mission-critical applications"
                    }
                ]
            }
            # Add more products as needed
        ]
    
    # Legacy API compatibility - delegate to quote agent
    async def generate_quote(self, quote_request: Dict[str, Any]) -> Dict[str, Any]:
        """Generate quote via quote agent (for API compatibility)"""
        return await self.quote_agent.generate_quote_from_conversation(
            [],
            quote_request.get('customer_info', {})
        ) 