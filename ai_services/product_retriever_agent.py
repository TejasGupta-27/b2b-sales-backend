import json
import re
from typing import List, Dict, Any, Optional
from .base import AIProvider, AIMessage, AIResponse
from services.elasticsearch_service import get_elasticsearch_service
from .function_models import RequirementExtraction, ProductAnalysis

class ProductRetrieverAgent(AIProvider):
    """Specialized agent for retrieving and analyzing products from Elasticsearch"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.elasticsearch = get_elasticsearch_service()
        
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
        """Extract technical and business requirements using Pydantic structured extraction"""
        
        try:
            conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
            
            extraction_prompt = f"""You are an expert B2B technology sales analyst. Extract detailed requirements from this conversation.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT: {customer_context or 'None provided'}

Extract the following information:
1. TECHNICAL REQUIREMENTS: Specific technical needs, specifications, features mentioned
2. BUSINESS REQUIREMENTS: Business goals, use cases, operational needs
3. PRODUCT CATEGORIES: Types of products/solutions needed (servers, storage, workstations, etc.)
4. SEARCH KEYWORDS: Key terms that should be used to search for products
5. BUDGET/TIMELINE: Any budget or timeline constraints mentioned
6. COMPANY INFO: Industry, size, specific context that affects product selection

Be comprehensive and extract ALL relevant technical terms, business needs, and search keywords that could help find the right products."""

            print("🔍 Extracting requirements using Pydantic structured response...")
            
            # Use structured extraction with Pydantic
            requirements = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=extraction_prompt)],
                RequirementExtraction
            )
            
            # Convert to dict and enhance with search terms
            requirements_dict = requirements.model_dump()
            
            # Extract additional search terms from the structured data
            search_terms = self._build_comprehensive_search_terms(requirements_dict)
            requirements_dict['search_terms'] = search_terms
            
            print(f"✅ Extracted requirements: {json.dumps(requirements_dict, indent=2)}")
            return requirements_dict
                
        except Exception as e:
            print(f"⚠️ Pydantic requirement extraction failed: {e}")
            # Fallback to heuristic extraction
            return self._fallback_requirement_extraction(conversation_text, customer_context)
    
    def _build_comprehensive_search_terms(self, requirements: Dict[str, Any]) -> List[str]:
        """Build comprehensive search terms from extracted requirements"""
        
        search_terms = []
        
        # From technical requirements
        tech_reqs = requirements.get('technical_requirements', [])
        for req in tech_reqs:
            if isinstance(req, str):
                # Extract key technical terms
                terms = self._extract_technical_terms(req)
                search_terms.extend(terms)
        
        # From business requirements  
        business_reqs = requirements.get('business_requirements', [])
        for req in business_reqs:
            if isinstance(req, str):
                # Extract business/use case terms
                terms = self._extract_business_terms(req)
                search_terms.extend(terms)
        
        # From product categories
        categories = requirements.get('product_categories', [])
        search_terms.extend(categories)
        
        # From use case
        use_case = requirements.get('use_case', '')
        if use_case:
            terms = self._extract_use_case_terms(use_case)
            search_terms.extend(terms)
        
        # From industry context
        industry = requirements.get('industry', '')
        if industry:
            search_terms.append(industry)
        
        # Remove duplicates and clean up
        unique_terms = list(set([term.lower().strip() for term in search_terms if term and len(term) > 2]))
        
        print(f"🔍 Built search terms: {unique_terms}")
        return unique_terms
    
    def _extract_technical_terms(self, text: str) -> List[str]:
        """Extract technical terms from requirement text with better gaming focus"""
        terms = []
        text_lower = text.lower()
        
        # Hardware terms with gaming focus
        hardware_terms = ['workstation', 'gaming pc', 'desktop', 'laptop', 'server', 'storage', 'monitor', 'display']
        for term in hardware_terms:
            if term in text_lower:
                terms.append(term)
        
        # Gaming-specific terms
        gaming_terms = ['gaming', 'rtx', 'gtx', 'radeon', 'geforce', 'graphics card', 'gpu', 'gaming workstation']
        for term in gaming_terms:
            if term in text_lower:
                terms.append(term)
        
        # Technical specs with gaming relevance
        tech_specs = ['gpu', 'graphics', 'rtx', 'gtx', 'cpu', 'processor', 'ram', 'memory', 'ssd', 'nvme']
        for spec in tech_specs:
            if spec in text_lower:
                terms.append(spec)
        
        # Remove generic terms that cause noise
        noise_terms = ['ray', 'current', 'sting', 'titles', 'demands', 'tracing']
        terms = [term for term in terms if term not in noise_terms]
        
        # Extract capacity/numbers but be more specific
        import re
        capacity_matches = re.findall(r'\b(?:rtx|gtx)\s*\d+|(?:\d+)\s*(?:gb|tb|ghz|cores?)\b', text_lower)
        for match in capacity_matches:
            terms.append(match.strip())
        
        return terms
    
    def _extract_business_terms(self, text: str) -> List[str]:
        """Extract business-related terms with gaming focus"""
        terms = []
        text_lower = text.lower()
        
        # Gaming business functions
        gaming_business_terms = ['game development', 'game testing', 'content creation', 'streaming', 'rendering']
        for term in gaming_business_terms:
            if term in text_lower:
                terms.append(term)
        
        # General business functions but filter noise
        business_terms = ['workstation', 'professional', 'development', 'testing', 'performance']
        for term in business_terms:
            if term in text_lower:
                terms.append(term)
        
        return terms
    
    def _extract_use_case_terms(self, use_case: str) -> List[str]:
        """Extract terms from use case description"""
        if not use_case:
            return []
        
        # Split into words and filter
        words = re.findall(r'\b\w{3,}\b', use_case.lower())
        
        # Filter out common words
        stop_words = {'the', 'and', 'for', 'with', 'that', 'this', 'are', 'was', 'will', 'have', 'has'}
        meaningful_words = [word for word in words if word not in stop_words]
        
        return meaningful_words[:10]  # Limit to top 10
    
    async def _search_relevant_products(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for products using extracted requirements with better filtering"""
        
        try:
            print(f"🔍 Searching products with requirements: {requirements}")
            
            # Clean and enhance search terms before searching
            enhanced_requirements = self._enhance_search_requirements(requirements)
            
            # Use the enhanced search method with cleaned terms
            products = await self.elasticsearch.search_products_by_requirements(enhanced_requirements)
            
            # Filter out irrelevant results
            filtered_products = self._filter_relevant_products(products, requirements)
            
            print(f"🎯 Product search returned {len(products)} products, filtered to {len(filtered_products)} relevant products")
            
            # Debug: Show which products were retrieved
            if filtered_products:
                print("📦 Retrieved relevant products:")
                for i, product in enumerate(filtered_products[:10]):
                    product_id = product.get('id', 'unknown-id')
                    product_name = product.get('name', 'Unknown Product')
                    product_category = product.get('category', 'Unknown Category')
                    product_price = product.get('price', 'No price')
                    
                    print(f"  {i+1}. ID: {product_id}")
                    print(f"     Name: {product_name}")
                    print(f"     Category: {product_category}")
                    print(f"     Price: {product_price}")
                    print()
            else:
                print("📦 No relevant products found after filtering")
                # Try a more basic search for gaming/workstation products
                fallback_products = await self._search_gaming_workstation_fallback()
                return fallback_products
            
            return filtered_products
            
        except Exception as e:
            print(f"❌ Product search failed: {e}")
            # Return gaming workstation fallback
            return await self._search_gaming_workstation_fallback()
    
    def _enhance_search_requirements(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and enhance search requirements for better relevance"""
        enhanced = requirements.copy()
        
        # Clean search terms - remove noise words
        original_terms = requirements.get('search_terms', [])
        noise_words = {'ray', 'current', 'sting', 'titles', 'demands', 'tracing', 'high', 'aaa'}
        
        # Keep important terms and add gaming-specific terms
        cleaned_terms = []
        gaming_context_detected = False
        
        for term in original_terms:
            # Skip noise words
            if term.lower() in noise_words:
                continue
            
            # Keep important technical terms
            if term.lower() in ['cpu', 'gpu', 'ram', 'workstation', 'gaming', 'rtx', 'gtx']:
                cleaned_terms.append(term)
                if term.lower() in ['gaming', 'gpu', 'rtx', 'gtx']:
                    gaming_context_detected = True
        
        # Add context-specific terms
        if gaming_context_detected:
            gaming_terms = ['gaming workstation', 'graphics card', 'high performance', 'gaming pc']
            cleaned_terms.extend(gaming_terms)
        
        # Enhance with category-specific terms
        tech_reqs = requirements.get('technical_requirements', [])
        for req in tech_reqs:
            if isinstance(req, str):
                req_lower = req.lower()
                if 'game' in req_lower and 'workstation' not in cleaned_terms:
                    cleaned_terms.append('workstation')
                if 'graphics' in req_lower or 'gpu' in req_lower:
                    cleaned_terms.extend(['graphics card', 'gpu'])
        
        enhanced['search_terms'] = cleaned_terms
        enhanced['original_search_terms'] = original_terms  # Keep for debugging
        
        print(f"🔧 Enhanced search terms: {original_terms} -> {cleaned_terms}")
        return enhanced
    
    def _filter_relevant_products(self, products: List[Dict], requirements: Dict[str, Any]) -> List[Dict]:
        """Filter products for relevance to requirements"""
        if not products:
            return []
        
        filtered = []
        gaming_context = self._detect_gaming_context(requirements)
        
        print(f"🔍 Filtering {len(products)} products (gaming_context: {gaming_context})")
        
        for product in products:
            product_name = product.get('name', '')
            product_category = product.get('category', '')
            product_price = product.get('price', 0)
            
            # Skip products with missing essential data
            if not product_name:
                print(f"  ❌ Skipping product with no name")
                continue
                
            # Allow products with price 0 for now since we're filtering them out too aggressively
            # if product_price <= 0:
            #     print(f"  ❌ Skipping {product_name} - no price")
            #     continue
            
            # Skip obvious duplicates (same name, check if already added)
            product_name_lower = product_name.lower()
            if any(existing.get('name', '').lower() == product_name_lower for existing in filtered):
                print(f"  ❌ Skipping {product_name} - duplicate")
                continue
            
            # Gaming context filtering
            if gaming_context:
                if self._is_gaming_relevant(product):
                    print(f"  ✅ Adding gaming product: {product_name}")
                    filtered.append(product)
                else:
                    print(f"  ❌ Skipping {product_name} - not gaming relevant")
            else:
                # General business context
                if self._is_business_relevant(product):
                    print(f"  ✅ Adding business product: {product_name}")
                    filtered.append(product)
                else:
                    print(f"  ❌ Skipping {product_name} - not business relevant")
        
        # Sort by relevance score if available
        filtered.sort(key=lambda x: x.get('_score', 0), reverse=True)
        
        print(f"🎯 Filtering complete: {len(filtered)} relevant products found")
        return filtered[:20]  # Limit to top 20
    
    def _detect_gaming_context(self, requirements: Dict[str, Any]) -> bool:
        """Detect if this is a gaming-related request"""
        gaming_indicators = ['gaming', 'game', 'gpu', 'graphics', 'rtx', 'gtx', 'rendering', 'ray tracing']
        
        # Check in all requirement fields
        all_text = ' '.join([
            str(requirements.get('use_case', '')),
            ' '.join(requirements.get('search_terms', [])),
            ' '.join(requirements.get('technical_requirements', [])),
            ' '.join(requirements.get('business_requirements', []))
        ]).lower()
        
        return any(indicator in all_text for indicator in gaming_indicators)
    
    def _is_gaming_relevant(self, product: Dict[str, Any]) -> bool:
        """Check if product is relevant for gaming use case"""
        name = product.get('name', '').lower()
        category = product.get('category', '').lower()
        description = product.get('description', '').lower()
        
        # Gaming-relevant indicators
        gaming_keywords = ['gaming', 'rtx', 'gtx', 'radeon', 'geforce', 'workstation', 'graphics', 'gpu', 'quadro', 'tesla']
        relevant_categories = ['workstation', 'graphics', 'gaming', 'computer', 'desktop', 'server']
        
        # Check if product has gaming indicators
        has_gaming_keywords = any(keyword in name or keyword in description for keyword in gaming_keywords)
        has_relevant_category = category in relevant_categories
        
        # Exclude obviously irrelevant products but be less strict
        irrelevant_keywords = ['sting ray', 'cable', 'mounting bracket', 'screw', 'adapter']  # More specific patterns
        is_irrelevant = any(keyword in name for keyword in irrelevant_keywords)
        
        result = (has_gaming_keywords or has_relevant_category) and not is_irrelevant
        
        # Debug logging
        print(f"    Gaming relevance check for '{name}':")
        print(f"      Category: {category}")
        print(f"      Has gaming keywords: {has_gaming_keywords}")
        print(f"      Has relevant category: {has_relevant_category}")
        print(f"      Is irrelevant: {is_irrelevant}")
        print(f"      Result: {result}")
        
        return result
    
    def _is_business_relevant(self, product: Dict[str, Any]) -> bool:
        """Check if product is relevant for general business use case"""
        category = product.get('category', '').lower()
        name = product.get('name', '').lower()
        
        # Business-relevant categories - be more inclusive
        business_categories = ['workstation', 'server', 'storage', 'networking', 'computer', 'desktop', 'laptop', 'general']
        
        # Exclude accessories and components but be less strict
        irrelevant_keywords = ['sting ray', 'cable', 'mounting bracket', 'screw kit']  # More specific patterns
        is_irrelevant = any(keyword in name for keyword in irrelevant_keywords)
        
        result = category in business_categories and not is_irrelevant
        
        # Debug logging
        print(f"    Business relevance check for '{name}':")
        print(f"      Category: {category}")
        print(f"      Has business category: {category in business_categories}")
        print(f"      Is irrelevant: {is_irrelevant}")
        print(f"      Result: {result}")
        
        return result
    
    async def _search_gaming_workstation_fallback(self) -> List[Dict]:
        """Fallback search specifically for gaming workstations"""
        try:
            print("🎮 Searching for gaming workstation fallback products...")
            
            # Search for gaming/workstation products specifically
            fallback_requirements = {
                'search_terms': ['workstation', 'gaming', 'graphics', 'gpu', 'desktop'],
                'product_categories': ['workstation', 'gaming', 'computer'],
                'technical_requirements': ['high performance', 'graphics card'],
                'business_requirements': ['gaming', 'development']
            }
            
            products = await self.elasticsearch.search_products_by_requirements(fallback_requirements)
            
            if not products:
                # Get any workstation/desktop products
                products = await self.elasticsearch._search_by_categories(['workstation', 'computer', 'desktop'], 10)
            
            if not products:
                # Last resort - get random products but filter for relevance
                all_products = await self.elasticsearch.get_random_products(50)
                products = [p for p in all_products if self._is_gaming_relevant(p) or self._is_business_relevant(p)]
            
            print(f"🎮 Gaming workstation fallback found {len(products)} products")
            return products[:10]
            
        except Exception as e:
            print(f"❌ Gaming workstation fallback failed: {e}")
            return []
    
    async def _search_relevant_solutions(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for solutions with fallback"""
        
        try:
            # Try to search solutions
            search_query = self._build_solution_search_query(requirements)
            solutions = await self.elasticsearch.search_products_with_fallback(
                search_query, index="solutions"
            )
            
            if not solutions:
                # Fallback to generic solutions
                solutions = [
                    {
                        "id": "solution-001",
                        "name": "Complete Business IT Solution",
                        "description": "Comprehensive IT infrastructure solution for businesses",
                        "components": ["Servers", "Workstations", "Networking", "Storage"],
                        "price_range": "10000-50000"
                    },
                    {
                        "id": "solution-002", 
                        "name": "Remote Work Solution",
                        "description": "Complete remote work setup for distributed teams",
                        "components": ["Laptops", "Monitors", "Collaboration Tools"],
                        "price_range": "5000-15000"
                    }
                ]
            
            print(f"🎯 Solution search returned {len(solutions)} solutions")
            return solutions
            
        except Exception as e:
            print(f"❌ Solution search failed: {e}")
            return []
    
    def _build_solution_search_query(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Build search query for solutions"""
        
        search_body = {
            "query": {
                "bool": {
                    "should": []
                }
            },
            "size": 10
        }
        
        # Add business requirement matching
        business_reqs = requirements.get('business_requirements', {})
        if business_reqs:
            for key, value in business_reqs.items():
                search_body["query"]["bool"]["should"].append({
                    "match": {
                        "description": f"{key} {value}"
                    }
                })
        
        # Add category matching
        categories = requirements.get('product_categories', [])
        for category in categories:
            search_body["query"]["bool"]["should"].append({
                "match": {
                    "components": category
                }
            })
        
        # If no criteria, match all
        if not search_body["query"]["bool"]["should"]:
            search_body["query"] = {"match_all": {}}
        
        return search_body
    
    async def _analyze_recommendations(
        self, 
        products: List[Dict], 
        solutions: List[Dict], 
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze and provide recommendations using Pydantic function calling"""
        
        analysis_prompt = f"""You are a technical solution architect. Analyze these products and solutions for the customer requirements.

CUSTOMER REQUIREMENTS:
{json.dumps(requirements, indent=2)}

AVAILABLE PRODUCTS:
{json.dumps(products[:5], indent=2)}

AVAILABLE SOLUTIONS:
{json.dumps(solutions, indent=2)}

Provide detailed analysis and recommendations for the customer."""
        
        try:
            # Use structured response with Pydantic
            analysis = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=analysis_prompt)],
                ProductAnalysis
            )
            
            return analysis.model_dump()
            
        except Exception as e:
            print(f"⚠️ Pydantic analysis failed: {e}")
            # Fallback to basic analysis
            return {
                "recommended_approach": "products",
                "top_recommendations": [],
                "missing_requirements": [],
                "alternative_options": [],
                "total_estimated_value": 0
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

    async def retrieve_products(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Retrieve relevant products using Pydantic extraction and Elasticsearch search"""
        
        try:
            print(f"🔍 Product Retriever: Starting Pydantic-based analysis...")
            
            # Extract requirements using Pydantic
            requirements = await self._extract_requirements_from_conversation(messages, customer_context)
            
            # Search for products using extracted requirements
            products = await self._search_relevant_products(requirements)
            solutions = await self._search_relevant_solutions(requirements)
            
            # Return structured response
            retrieval_result = {
                'products': products,
                'solutions': solutions,
                'requirements': requirements,
                'total_products': len(products),
                'total_solutions': len(solutions),
                'retrieval_method': 'pydantic_extraction_elasticsearch_search',
                'success': True
            }
            
            print(f"✅ Product Retriever: Found {len(products)} products, {len(solutions)} solutions using Pydantic extraction")
            return retrieval_result
            
        except Exception as e:
            print(f"❌ Product Retriever: Error - {str(e)}")
            import traceback
            print(traceback.format_exc())
            
            return {
                'products': [],
                'solutions': [],
                'requirements': {},
                'total_products': 0,
                'total_solutions': 0,
                'retrieval_method': 'error_fallback',
                'success': False,
                'error': str(e)
            }

    def _fallback_requirement_extraction(
        self, 
        conversation_text: str, 
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enhanced fallback requirement extraction"""
        
        text_lower = conversation_text.lower()
        
        # Extract technical requirements using patterns
        technical_requirements = []
        tech_patterns = [
            r'nas\s+server',
            r'centrali[sz]ed?\s+(?:data|storage)',
            r'(?:data\s+)?backup',
            r'(?:role.based\s+)?access\s+control',
            r'(?:data\s+)?encryption',
            r'(?:\d+\s+)?users?',
            r'scalable?\s+(?:system|solution)',
            r'gigabit\s+(?:network|ethernet)',
            r'ssd\s+caching',
            r'gdpr\s+compliance'
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                technical_requirements.append(match.replace('_', ' ').title())
        
        # Extract business requirements
        business_requirements = []
        business_patterns = [
            r'(?:reduce|eliminate)\s+(?:inefficiencies|data\s+loss)',
            r'support\s+collaboration',
            r'secure\s+access',
            r'reliable\s+backup',
            r'future\s+growth',
            r'accommodate\s+growth'
        ]
        
        for pattern in business_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                business_requirements.append(match.replace('_', ' ').title())
        
        # Extract search terms
        search_terms = []
        key_terms = ['nas', 'server', 'storage', 'backup', 'security', 'collaboration', 'scalable', 'enterprise']
        for term in key_terms:
            if term in text_lower:
                search_terms.append(term)
        
        return {
            'technical_requirements': technical_requirements or ['NAS server', 'Data storage', 'Backup solution'],
            'business_requirements': business_requirements or ['Centralize data', 'Support collaboration'],
            'product_categories': ['storage', 'server'],
            'search_terms': search_terms or ['nas', 'server', 'storage'],
            'use_case': 'Business data storage and collaboration solution',
            'industry': customer_context.get('industry') if customer_context else 'business',
            'extraction_method': 'fallback_pattern_based'
        } 