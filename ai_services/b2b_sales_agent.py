import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

from .base import AIProvider, AIMessage, AIResponse
from models.catalog import Product, Quote, QuoteRequest

class B2BSalesAgent(AIProvider):
    """B2B Sales Agent specialized in product recommendations and quotations"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.product_catalog = self._load_product_catalog()
        self.pricing_rules = self._load_pricing_rules()
    
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
        # Enhance messages with sales context and product knowledge
        enhanced_messages = self._add_sales_context(messages, customer_context)
        
        # Generate response using base provider
        response = await self.base_provider.generate_response(enhanced_messages, **kwargs)
        
        # Post-process for sales-specific enhancements
        enhanced_response = self._enhance_sales_response(response, customer_context)
        
        return enhanced_response
    
    def _add_sales_context(self, messages: List[AIMessage], customer_context: Optional[Dict]) -> List[AIMessage]:
        """Add B2B sales context and product knowledge"""
        
        # Build comprehensive sales system prompt
        system_prompt = self._build_sales_system_prompt()
        
        # Add product catalog information
        product_info = self._build_product_context()
        
        # Add customer context if available
        customer_info = ""
        if customer_context:
            customer_info = self._build_customer_context(customer_context)
        
        enhanced_messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="system", content=product_info),
        ]
        
        if customer_info:
            enhanced_messages.append(AIMessage(role="system", content=customer_info))
        
        # Add original conversation
        enhanced_messages.extend(messages)
        
        return enhanced_messages
    
    def _build_sales_system_prompt(self) -> str:
        """Build the main system prompt for B2B sales"""
        return """You are an expert B2B sales consultant specializing in commercial computers and peripherals. Your expertise includes:

CORE RESPONSIBILITIES:
1. DISCOVER customer hardware needs, specifications, and deployment requirements
2. RECOMMEND the most suitable computers and peripherals based on requirements
3. PROVIDE accurate pricing and create detailed quotations
4. EXPLAIN value propositions and total cost of ownership
5. GUIDE customers through the decision-making process

SALES APPROACH:
- Ask targeted questions to understand hardware requirements
- Listen for performance needs, quantity requirements, and deployment timeline
- Present solutions that directly address stated needs
- Provide specific pricing and delivery details
- Create urgency through limited-time offers when appropriate
- Always suggest clear next steps

PRODUCT RECOMMENDATION STRATEGY:
- Match hardware to business size and usage patterns
- Consider current infrastructure and compatibility needs
- Recommend packages that provide best value
- Suggest scalable solutions for growing companies
- Highlight performance advantages and reliability features

QUOTATION GUIDELINES:
- Provide transparent, itemized pricing
- Include delivery and setup costs
- Offer multiple options (good, better, best)
- Apply appropriate volume discounts
- Set clear validity periods for quotes
- Include warranty terms and next steps

COMMUNICATION STYLE:
- Professional yet conversational
- Focus on performance and reliability
- Use technical language appropriately
- Be consultative, not pushy
- Acknowledge objections and provide solutions
- Create excitement about productivity improvements

Remember: Your goal is to help customers make the best decision for their business while driving revenue growth."""

    def _build_product_context(self) -> str:
        """Build context about available products and services"""
        context = "AVAILABLE PRODUCTS & SERVICES:\n\n"
        
        for product in self.product_catalog:
            context += f"=== {product['name']} ===\n"
            context += f"Category: {product['category']}\n"
            context += f"Description: {product['description']}\n"
            context += f"Key Features: {', '.join(product['features'])}\n"
            context += f"Ideal For: {', '.join(product['ideal_for'])}\n"
            context += f"Implementation Time: {product['implementation_time']}\n"
            
            context += "Pricing Tiers:\n"
            for tier in product['pricing_tiers']:
                context += f"  • {tier['name']}: ${tier['price']}/{tier['billing_cycle']}"
                if tier.get('user_limit'):
                    context += f" (up to {tier['user_limit']} users)"
                context += f" - {', '.join(tier['features_included'])}\n"
            context += "\n"
        
        return context
    
    def _build_customer_context(self, customer_context: Dict[str, Any]) -> str:
        """Build context about the customer"""
        context = "CUSTOMER CONTEXT:\n"
        
        if customer_context.get('company_size'):
            context += f"Company Size: {customer_context['company_size']}\n"
        
        if customer_context.get('industry'):
            context += f"Industry: {customer_context['industry']}\n"
        
        if customer_context.get('budget_range'):
            context += f"Budget Range: {customer_context['budget_range']}\n"
        
        if customer_context.get('timeline'):
            context += f"Timeline: {customer_context['timeline']}\n"
        
        if customer_context.get('current_solution'):
            context += f"Current Solution: {customer_context['current_solution']}\n"
        
        if customer_context.get('pain_points'):
            context += f"Pain Points: {', '.join(customer_context['pain_points'])}\n"
        
        return context
    
    def _enhance_sales_response(self, response: AIResponse, customer_context: Optional[Dict]) -> AIResponse:
        """Enhance response with sales-specific features"""
        
        # Check if response contains quotation request
        if self._contains_quotation_request(response.content):
            quote_data = self._extract_quote_requirements(response.content, customer_context)
            if quote_data:
                quote = self._generate_quote(quote_data)
                response.metadata = response.metadata or {}
                response.metadata['quote'] = quote
        
        return response
    
    def _contains_quotation_request(self, content: str) -> bool:
        """Check if the response suggests creating a quotation"""
        quote_indicators = [
            "quote", "pricing", "proposal", "cost breakdown",
            "investment", "total cost", "price estimate"
        ]
        return any(indicator in content.lower() for indicator in quote_indicators)
    
    def _generate_quote(self, quote_request: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a detailed quotation based on requirements"""
        
        # Recommend products based on requirements
        recommended_products = self._recommend_products(quote_request)
        
        # Calculate pricing
        pricing = self._calculate_pricing(recommended_products, quote_request)
        
        # Generate quote
        quote = {
            "id": str(uuid.uuid4()),
            "customer_info": quote_request,
            "recommended_products": recommended_products,
            "pricing": pricing,
            "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
            "created_at": datetime.now().isoformat(),
            "terms": [
                "Prices valid for 30 days",
                "Implementation included in pricing",
                "30-day money-back guarantee",
                "Annual billing receives 20% discount",
                "24/7 support included"
            ]
        }
        
        return quote
    
    def _recommend_products(self, requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recommend products based on customer requirements"""
        recommendations = []
        
        company_size = requirements.get('company_size', '').lower()
        industry = requirements.get('industry', '').lower()
        budget = requirements.get('budget_range', '').lower()
        
        for product in self.product_catalog:
            # Check if product is suitable for company size
            if self._is_suitable_for_company_size(product, company_size):
                # Check if product matches industry needs
                if self._matches_industry_needs(product, industry):
                    # Calculate recommended tier
                    recommended_tier = self._select_pricing_tier(product, requirements)
                    
                    recommendations.append({
                        "product": product,
                        "recommended_tier": recommended_tier,
                        "justification": self._get_recommendation_justification(product, requirements)
                    })
        
        return recommendations[:3]  # Top 3 recommendations
    
    def _calculate_pricing(self, recommendations: List[Dict], requirements: Dict) -> Dict[str, Any]:
        """Calculate total pricing for recommended products"""
        
        monthly_total = 0
        annual_total = 0
        items = []
        
        for rec in recommendations:
            product = rec['product']
            tier = rec['recommended_tier']
            
            monthly_price = tier['price'] if tier['billing_cycle'] == 'monthly' else tier['price'] / 12
            annual_price = tier['price'] if tier['billing_cycle'] == 'annual' else tier['price'] * 12
            
            # Apply discounts for annual billing
            if tier['billing_cycle'] == 'annual':
                annual_price *= 0.8  # 20% discount
            
            monthly_total += monthly_price
            annual_total += annual_price
            
            items.append({
                "product_name": product['name'],
                "tier_name": tier['name'],
                "monthly_price": monthly_price,
                "annual_price": annual_price,
                "features": tier['features_included']
            })
        
        return {
            "items": items,
            "monthly_total": round(monthly_total, 2),
            "annual_total": round(annual_total, 2),
            "annual_savings": round(monthly_total * 12 - annual_total, 2),
            "discount_percentage": 20 if annual_total < monthly_total * 12 else 0
        }
    
    def _load_product_catalog(self) -> List[Dict[str, Any]]:
        """Load product catalog (would typically come from database)"""
        return [
            {
                "id": "workstation-pro",
                "name": "Workstation Pro",
                "category": "desktop",
                "description": "High-performance workstation for demanding business applications",
                "features": [
                    "Intel Core i7/i9 Processor",
                    "32GB DDR4 RAM",
                    "1TB NVMe SSD",
                    "NVIDIA RTX Graphics",
                    "Windows 11 Pro",
                    "3-Year Warranty",
                    "On-site Support"
                ],
                "ideal_for": ["Design Studios", "Engineering Firms", "Financial Services"],
                "implementation_time": "1-2 weeks",
                "pricing_tiers": [
                    {
                        "name": "Standard",
                        "price": 1299,
                        "billing_cycle": "one-time",
                        "features_included": ["Core i7", "32GB RAM", "512GB SSD"],
                        "user_limit": None
                    },
                    {
                        "name": "Professional",
                        "price": 1999,
                        "billing_cycle": "one-time",
                        "features_included": ["Core i9", "64GB RAM", "1TB SSD"],
                        "user_limit": None
                    }
                ]
            },
            {
                "id": "business-laptop",
                "name": "Business Laptop",
                "category": "laptop",
                "description": "Reliable business laptop for everyday productivity",
                "features": [
                    "Intel Core i5/i7 Processor",
                    "16GB DDR4 RAM",
                    "512GB SSD",
                    "14\" FHD Display",
                    "Windows 11 Pro",
                    "2-Year Warranty",
                    "Backlit Keyboard"
                ],
                "ideal_for": ["Office Workers", "Sales Teams", "Remote Workers"],
                "implementation_time": "1 week",
                "pricing_tiers": [
                    {
                        "name": "Essential",
                        "price": 899,
                        "billing_cycle": "one-time",
                        "features_included": ["Core i5", "16GB RAM", "256GB SSD"],
                        "user_limit": None
                    },
                    {
                        "name": "Premium",
                        "price": 1299,
                        "billing_cycle": "one-time",
                        "features_included": ["Core i7", "16GB RAM", "512GB SSD"],
                        "user_limit": None
                    }
                ]
            },
            {
                "id": "monitor-pro",
                "name": "Professional Monitor",
                "category": "peripheral",
                "description": "High-quality display for professional work",
                "features": [
                    "27\" 4K UHD Display",
                    "HDR Support",
                    "USB-C Connectivity",
                    "Adjustable Stand",
                    "3-Year Warranty",
                    "Anti-glare Coating"
                ],
                "ideal_for": ["Designers", "Developers", "Office Workers"],
                "implementation_time": "1 week",
                "pricing_tiers": [
                    {
                        "name": "Standard",
                        "price": 399,
                        "billing_cycle": "one-time",
                        "features_included": ["27\" 4K", "HDR", "USB-C"],
                        "user_limit": None
                    },
                    {
                        "name": "Premium",
                        "price": 599,
                        "billing_cycle": "one-time",
                        "features_included": ["27\" 4K", "HDR1000", "Thunderbolt"],
                        "user_limit": None
                    }
                ]
            }
        ]
    
    def _load_pricing_rules(self) -> Dict[str, Any]:
        """Load pricing rules and discount structures"""
        return {
            "volume_discounts": {
                "10_units": 0.05,  # 5% for 10+ units
                "25_units": 0.10,  # 10% for 25+ units
                "50_units": 0.15,  # 15% for 50+ units
                "100_units": 0.20  # 20% for 100+ units
            },
            "bundle_discount": 0.10,  # 10% for computer + monitor bundles
            "enterprise_discount": 0.15,  # 15% for enterprise deals
            "trade_in_discount": 0.05  # 5% for trade-in program
        }
    
    def _is_suitable_for_company_size(self, product: Dict, company_size: str) -> bool:
        """Check if product is suitable for company size"""
        size_mapping = {
            "startup": ["Sales Teams", "SMB"],
            "small": ["Sales Teams", "SMB", "Marketing Teams"],
            "medium": ["SMB", "Enterprise", "Sales Teams", "Marketing Teams"],
            "large": ["Enterprise", "SaaS Companies"],
            "enterprise": ["Enterprise", "SaaS Companies"]
        }
        
        suitable_for = size_mapping.get(company_size, ["SMB"])
        return any(category in product['ideal_for'] for category in suitable_for)
    
    def _matches_industry_needs(self, product: Dict, industry: str) -> bool:
        """Check if product matches industry needs"""
        if not industry:
            return True
        
        # Simple industry matching - could be more sophisticated
        industry_matches = {
            "saas": ["SaaS Companies", "Sales Teams"],
            "technology": ["Sales Teams", "Marketing Teams"],
            "e-commerce": ["Marketing Teams", "Customer Success Teams"],
            "services": ["Sales Teams", "Customer Success Teams"]
        }
        
        relevant_categories = industry_matches.get(industry.lower(), [])
        if not relevant_categories:
            return True
        
        return any(category in product['ideal_for'] for category in relevant_categories)
    
    def _select_pricing_tier(self, product: Dict, requirements: Dict) -> Dict[str, Any]:
        """Select the most appropriate pricing tier"""
        company_size = requirements.get('company_size', 'small').lower()
        budget = requirements.get('budget_range', '').lower()
        
        tiers = product['pricing_tiers']
        
        # Default to middle tier
        if len(tiers) >= 2:
            selected_tier = tiers[1]
        else:
            selected_tier = tiers[0]
        
        # Adjust based on company size
        if company_size in ['startup', 'small'] and len(tiers) > 0:
            selected_tier = tiers[0]  # Starter tier
        elif company_size in ['large', 'enterprise'] and len(tiers) > 2:
            selected_tier = tiers[-1]  # Enterprise tier
        
        return selected_tier
    
    def _get_recommendation_justification(self, product: Dict, requirements: Dict) -> str:
        """Generate justification for product recommendation"""
        justifications = []
        
        company_size = requirements.get('company_size', '')
        if company_size:
            justifications.append(f"Ideal for {company_size} companies")
        
        if requirements.get('pain_points'):
            relevant_features = []
            for pain in requirements['pain_points']:
                if 'lead' in pain.lower():
                    relevant_features.append("AI Lead Scoring")
                if 'sales' in pain.lower():
                    relevant_features.append("Sales Automation")
                if 'customer' in pain.lower():
                    relevant_features.append("Customer Analytics")
            
            if relevant_features:
                justifications.append(f"Addresses your needs with: {', '.join(relevant_features)}")
        
        return "; ".join(justifications) if justifications else "Recommended based on your requirements"
    
    def _extract_quote_requirements(self, content: str, customer_context: Optional[Dict]) -> Optional[Dict]:
        """Extract quote requirements from conversation"""
        if not customer_context:
            return None
        
        return {
            "company_size": customer_context.get('company_size'),
            "industry": customer_context.get('industry'),
            "budget_range": customer_context.get('budget_range'),
            "timeline": customer_context.get('timeline'),
            "requirements": customer_context.get('requirements', []),
            "pain_points": customer_context.get('pain_points', [])
        } 