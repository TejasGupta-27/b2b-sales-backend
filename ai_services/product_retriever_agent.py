import json
import re
from typing import List, Dict, Any, Optional
from .base import AIProvider, AIMessage, AIResponse
from services.elasticsearch_service import elasticsearch_service

class ProductRetrieverAgent(AIProvider):
    """Specialized agent for retrieving and analyzing products from Elasticsearch"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.elasticsearch = elasticsearch_service
        
    @property
    def provider_name(self) -> str:
        return f"product_retriever_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """This agent doesn't generate conversational responses directly"""
        return AIResponse(
            content="Product Retriever Agent - use retrieve_products method",
            model="retriever-agent",
            provider=self.provider_name,
            usage={}
        )
    
    async def analyze_conversation_and_retrieve(
        self, 
        conversation_messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze conversation to understand needs and retrieve relevant products/solutions"""
        
        print("🔍 Retriever Agent: Analyzing conversation for product needs...")
        
        # Extract requirements from conversation
        requirements = await self._extract_requirements_from_conversation(
            conversation_messages, customer_context
        )
        
        # Search for relevant products
        products = await self._search_relevant_products(requirements)
        
        # Search for relevant solutions
        solutions = await self._search_relevant_solutions(requirements)
        
        # Analyze and rank results
        analysis = await self._analyze_recommendations(products, solutions, requirements)
        
        return {
            "requirements": requirements,
            "products": products,
            "solutions": solutions,
            "analysis": analysis,
            "retrieval_confidence": self._calculate_confidence(products, solutions, requirements)
        }
    
    async def _extract_requirements_from_conversation(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract technical and business requirements using AI"""
        
        conversation_text = "\n".join([
            f"{msg.role}: {msg.content}" for msg in messages[-10:]
        ])
        
        extraction_prompt = """You are a technical requirements analyst. Extract specific product and solution requirements from this B2B sales conversation.

ANALYZE FOR:
1. Product categories needed (workstation, server, storage, networking, monitor, software)
2. Technical specifications mentioned
3. Business requirements (users, performance, reliability)
4. Industry context and use cases
5. Budget constraints or ranges
6. Timeline requirements

RETURN ONLY valid JSON in this exact format:
{
    "product_categories": ["workstation", "storage"],
    "technical_specs": {
        "ram": "64GB",
        "storage": "10TB",
        "networking": "10GbE"
    },
    "business_requirements": {
        "user_count": 10,
        "use_case": "video editing",
        "performance_needs": "high",
        "reliability_level": "enterprise"
    },
    "industry": "media",
    "company_size": "small",
    "budget_range": "15000-25000",
    "timeline": "immediate",
    "search_keywords": ["high performance", "video editing", "storage"],
    "priority_areas": ["performance", "storage", "reliability"]
}"""
        
        messages_for_ai = [
            AIMessage(role="system", content=extraction_prompt),
            AIMessage(role="user", content=f"""CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT:
{json.dumps(customer_context or {}, indent=2)}

Extract requirements as JSON:""")
        ]
        
        try:
            response = await self.base_provider.generate_response(messages_for_ai)
            
            # Parse JSON from response
            json_start = response.content.find('{')
            json_end = response.content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                requirements_json = response.content[json_start:json_end]
                requirements = json.loads(requirements_json)
                
                # Add customer context
                requirements['customer_context'] = customer_context or {}
                requirements['extraction_method'] = 'ai_powered'
                
                return requirements
        except Exception as e:
            print(f"⚠️ AI requirements extraction failed: {e}")
        
        # Fallback to pattern-based extraction
        return self._pattern_based_requirements_extraction(conversation_text, customer_context)
    
    def _pattern_based_requirements_extraction(
        self, 
        conversation_text: str, 
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback pattern-based requirements extraction"""
        
        conversation_lower = conversation_text.lower()
        
        # Extract product categories
        categories = []
        category_patterns = {
            'workstation': ['workstation', 'desktop', 'computer', 'pc'],
            'storage': ['storage', 'nas', 'raid', 'backup', 'data'],
            'networking': ['network', '10gbe', 'switch', 'router'],
            'monitor': ['monitor', 'display', 'screen', '4k'],
            'server': ['server', 'virtualization', 'vm']
        }
        
        for category, patterns in category_patterns.items():
            if any(pattern in conversation_lower for pattern in patterns):
                categories.append(category)
        
        # Extract technical specs
        tech_specs = {}
        
        # RAM
        ram_match = re.search(r'(\d+)\s*gb.*(?:ram|memory)', conversation_lower)
        if ram_match:
            tech_specs['ram'] = f"{ram_match.group(1)}GB"
        
        # Storage
        storage_match = re.search(r'(\d+)\s*tb', conversation_lower)
        if storage_match:
            tech_specs['storage'] = f"{storage_match.group(1)}TB"
        
        # Search keywords
        keywords = []
        if 'performance' in conversation_lower or 'fast' in conversation_lower:
            keywords.append('high performance')
        if 'professional' in conversation_lower or 'business' in conversation_lower:
            keywords.append('professional')
        if 'enterprise' in conversation_lower:
            keywords.append('enterprise')
        
        return {
            "product_categories": categories,
            "technical_specs": tech_specs,
            "search_keywords": keywords,
            "customer_context": customer_context or {},
            "extraction_method": "pattern_based"
        }
    
    async def _search_relevant_products(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for products using enhanced requirements-based search"""
        
        print(f"🔍 Searching products with requirements: {requirements}")
        
        # First, check if Elasticsearch has data
        try:
            stats = await self.elasticsearch.get_product_stats()
            total_products = stats.get('total_products', 0)
            print(f"📊 Elasticsearch has {total_products} products available")
            
            if total_products == 0:
                print("⚠️ No products found in Elasticsearch, loading sample data...")
                await self.elasticsearch.load_initial_data()
                # Recheck after loading
                stats = await self.elasticsearch.get_product_stats()
                total_products = stats.get('total_products', 0)
                print(f"📊 After loading: {total_products} products available")
        except Exception as e:
            print(f"❌ Error checking Elasticsearch stats: {e}")
            return []
        
        # Use the requirements-based search
        products = await self.elasticsearch.search_products_by_requirements(requirements, size=20)
        print(f"🎯 Requirements search returned {len(products)} products")
        
        # If no results with requirements, try broader keyword search
        if not products and requirements.get('search_keywords'):
            print("🔍 Trying keyword search as fallback...")
            for keyword in requirements['search_keywords']:
                keyword_results = await self.elasticsearch.search_products(keyword, size=10)
                products.extend(keyword_results)
                print(f"🔍 Keyword '{keyword}' returned {len(keyword_results)} products")
        
        # If still no results, try category-based search
        if not products and requirements.get('product_categories'):
            print("🔍 Trying category-based search...")
            for category in requirements['product_categories']:
                category_results = await self.elasticsearch.search_products(category, size=10)
                products.extend(category_results)
                print(f"🔍 Category '{category}' returned {len(category_results)} products")
        
        # If still no results, do a general search
        if not products:
            print("🔍 Trying general search...")
            general_results = await self.elasticsearch.search_products("", size=10)
            products.extend(general_results)
            print(f"🔍 General search returned {len(general_results)} products")
        
        # Remove duplicates and limit results
        seen_ids = set()
        unique_products = []
        for product in products:
            product_id = product.get('id')
            if product_id and product_id not in seen_ids:
                seen_ids.add(product_id)
                unique_products.append(product)
                if len(unique_products) >= 10:  # Limit to top 10
                    break
        
        print(f"✅ Final result: {len(unique_products)} unique products")
        return unique_products
    
    async def _search_relevant_solutions(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for relevant pre-built solutions"""
        
        search_requirements = {}
        
        customer_context = requirements.get('customer_context', {})
        
        if customer_context.get('industry'):
            search_requirements['industry'] = customer_context['industry']
        
        if customer_context.get('company_size'):
            search_requirements['company_size'] = customer_context['company_size']
        
        if customer_context.get('budget_range'):
            search_requirements['budget_range'] = customer_context['budget_range']
        
        # Add use case from business requirements
        business_reqs = requirements.get('business_requirements', {})
        if business_reqs.get('use_case'):
            search_requirements['use_case'] = business_reqs['use_case']
        
        return await self.elasticsearch.search_solutions(search_requirements)
    
    async def _analyze_recommendations(
        self, 
        products: List[Dict], 
        solutions: List[Dict], 
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze and provide recommendations"""
        
        analysis_prompt = f"""You are a technical solution architect. Analyze these products and solutions for the customer requirements.

CUSTOMER REQUIREMENTS:
{json.dumps(requirements, indent=2)}

AVAILABLE PRODUCTS:
{json.dumps(products[:5], indent=2)}

AVAILABLE SOLUTIONS:
{json.dumps(solutions, indent=2)}

Provide analysis in JSON format:
{{
    "recommended_approach": "products|solutions|hybrid",
    "top_recommendations": [
        {{
            "type": "product|solution",
            "id": "item_id",
            "name": "item_name",
            "match_score": 0.95,
            "why_recommended": "Clear explanation",
            "considerations": ["Important notes"]
        }}
    ],
    "missing_requirements": ["What we couldn't address"],
    "alternative_options": ["Other considerations"],
    "total_estimated_value": 15000
}}"""
        
        messages_for_ai = [
            AIMessage(role="system", content=analysis_prompt),
            AIMessage(role="user", content="Analyze and recommend:")
        ]
        
        try:
            response = await self.base_provider.generate_response(messages_for_ai)
            
            json_start = response.content.find('{')
            json_end = response.content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                analysis_json = response.content[json_start:json_end]
                return json.loads(analysis_json)
        except Exception as e:
            print(f"⚠️ Analysis failed: {e}")
        
        # Fallback simple analysis
        return {
            "recommended_approach": "products" if len(products) > len(solutions) else "solutions",
            "top_recommendations": [
                {
                    "type": "product",
                    "id": products[0].get('id') if products else None,
                    "name": products[0].get('name') if products else "No products found",
                    "match_score": 0.8,
                    "why_recommended": "Best match based on requirements",
                    "considerations": []
                }
            ] if products else [],
            "missing_requirements": [],
            "alternative_options": []
        }
    
    def _calculate_confidence(
        self, 
        products: List[Dict], 
        solutions: List[Dict], 
        requirements: Dict[str, Any]
    ) -> float:
        """Calculate confidence in retrieval results"""
        
        score = 0.0
        
        # Base score for finding results
        if products:
            score += 0.3
        if solutions:
            score += 0.2
        
        # Bonus for matching categories
        required_categories = requirements.get('product_categories', [])
        found_categories = set()
        for product in products:
            if product.get('category') in required_categories:
                found_categories.add(product.get('category'))
        
        if required_categories:
            category_match_ratio = len(found_categories) / len(required_categories)
            score += 0.3 * category_match_ratio
        
        # Bonus for technical spec matches
        if requirements.get('technical_specs'):
            score += 0.2
        
        return min(score, 1.0) 