import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
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
        """Generate a response with product recommendations"""
        try:
            # Extract requirements and get recommendations
            result = await self.retrieve_products(messages)
            
            # Format response content
            content = self._format_recommendation_response(result)
            
            # Track token usage from base provider
            if hasattr(self.base_provider, 'usage_tracker'):
                self.usage_tracker = self.base_provider.usage_tracker
            
            return AIResponse(
                content=content,
                model=self.provider_name,
                provider=self.provider_name,
                usage=result.get('usage', {}),
                metadata={
                    'recommendations': result.get('products', []),
                    'solutions': result.get('solutions', []),
                    'requirements': result.get('requirements', {}),
                    'confidence': result.get('retrieval_confidence', 0)
                }
            )
        except Exception as e:
            print(f"❌ Error generating response: {str(e)}")
            return AIResponse(
                content="I apologize, but I encountered an error while retrieving product recommendations.",
                model=self.provider_name,
                provider=self.provider_name,
                usage={},
                metadata={'error': str(e)}
            )
    
    def _format_recommendation_response(self, result: Dict[str, Any]) -> str:
        """Format recommendation results into a readable response with RRF scores"""
        products = result.get('products', [])
        solutions = result.get('solutions', [])
        requirements = result.get('requirements', {})
        
        response = "Based on your requirements, here are my recommendations:\n\n"
        
        # Check if this is a custom NAS build
        if requirements.get('build_type') == 'custom':
            response += "🔧 **Custom NAS Build Components:**\n\n"
            
            # Group components by category
            for category_group in products:
                category = category_group.get('category', 'Other')
                components = category_group.get('components', [])
                
                if components:
                    response += f"📦 **{category.title()} Components:**\n"
                    for i, component in enumerate(components[:3], 1):
                        response += f"{i}. **{component.get('name', 'Unknown Component')}**\n"
                        response += f"   • Description: {component.get('description', 'No description available')}\n"
                        if component.get('price'):
                            response += f"   • Price: ${component.get('price'):,.2f}\n"
                        if component.get('compatibility_notes'):
                            response += "   • Compatibility Notes:\n"
                            for note in component['compatibility_notes']:
                                response += f"     - {note}\n"
                        response += "\n"
            
            response += "\n💡 **Build Considerations:**\n"
            response += "1. Ensure all components are compatible with each other\n"
            response += "2. Consider power supply requirements\n"
            response += "3. Plan for proper cooling and ventilation\n"
            response += "4. Consider future expansion needs\n"
            response += "5. Plan for backup and redundancy\n\n"
            
            response += "Would you like me to:\n"
            response += "1. Provide more detailed specifications for any component\n"
            response += "2. Suggest alternative components\n"
            response += "3. Help with compatibility checking\n"
            response += "4. Provide a total cost estimate\n"
            
        else:
            # Original pre-built system recommendations
            if products:
                response += "📦 **Recommended Products:**\n"
                for i, product in enumerate(products, 1):
                    response += f"{i}. **{product.get('name', 'Unknown Product')}**\n"
                    response += f"   • Description: {product.get('description', 'No description available')}\n"
                    if product.get('price'):
                        response += f"   • Price: ${product.get('price'):,.2f}\n"
                    if 'rrf_score' in product:
                        response += f"   • Match Score: {product['rrf_score']:.1%}\n"
                    response += "\n"
            
            if solutions:
                response += "\n🎯 **Recommended Solutions:**\n"
                for i, solution in enumerate(solutions[:3], 1):
                    response += f"{i}. **{solution.get('name', 'Unknown Solution')}**\n"
                    response += f"   • Description: {solution.get('description', 'No description available')}\n"
                    if solution.get('price_range'):
                        response += f"   • Price Range: {solution.get('price_range')}\n"
                    response += "\n"
            
            response += "\n💡 **Next Steps:**\n"
            response += "1. Review these recommendations\n"
            response += "2. Let me know if you'd like more details about any specific product or solution\n"
            response += "3. I can help you compare options or discuss implementation\n"
        
        return response

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
            
            # Check if we have cached results for these requirements
            if hasattr(self, '_cached_requirements') and self._cached_requirements == requirements:
                print("🔄 Using cached product recommendations")
                return self._cached_retrieval_result
            
            # Search for products using extracted requirements
            products = await self._search_relevant_products(requirements)
            solutions = await self._search_relevant_solutions(requirements)
            
            # Analyze recommendations
            analysis = await self._analyze_recommendations(products, solutions, requirements)
            
            # Calculate confidence
            confidence = self._calculate_confidence(products, solutions, requirements)
            
            # Create retrieval result
            retrieval_result = {
                'products': products,
                'solutions': solutions,
                'requirements': requirements,
                'analysis': analysis,
                'total_products': len(products),
                'total_solutions': len(solutions),
                'retrieval_method': 'pydantic_extraction_elasticsearch_search',
                'retrieval_confidence': confidence,
                'success': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Cache the results
            self._cached_requirements = requirements
            self._cached_retrieval_result = retrieval_result
            
            print(f"✅ Product Retriever: Found {len(products)} products, {len(solutions)} solutions")
            return retrieval_result
            
        except Exception as e:
            print(f"❌ Product Retriever: Error - {str(e)}")
            import traceback
            print(traceback.format_exc())
            
            return {
                'products': [],
                'solutions': [],
                'requirements': {},
                'analysis': {},
                'total_products': 0,
                'total_solutions': 0,
                'retrieval_method': 'error_fallback',
                'retrieval_confidence': 0.0,
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
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
3. PRODUCT CATEGORIES: Types of products/solutions needed (computers, servers, storage, peripherals, etc.)
4. BUILD TYPE: Whether the customer wants a pre-built commercial device or custom-built components
5. CUSTOM BUILD REQUIREMENTS (if applicable):
   - Device type (computer, server, peripheral, etc.)
   - Performance requirements (CPU, GPU, RAM, etc.)
   - Storage requirements (if applicable)
   - Display requirements (if applicable)
   - Connectivity requirements
   - Form factor preferences
   - Operating system preferences
   - Additional features or specifications

Analyze the conversation carefully to determine if the customer wants to purchase a pre-built commercial device or build a custom configuration."""

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
        """Search for relevant products based on requirements"""
        try:
            # Check if this is a custom build request
            if requirements.get('build_type') == 'custom':
                return await self._search_custom_components(requirements)
            
            # Check if we have cached results
            if hasattr(self, '_cached_results') and self._cached_results:
                print("🔄 Using cached product results")
                return self._cached_results
            
            # Original product search logic for pre-built devices
            search_terms = self._build_comprehensive_search_terms(requirements)
            search_body = self._build_product_search_query(search_terms, requirements)
            
            # Perform the search
            products = await self.elasticsearch.search_products_by_requirements(search_body)
            
            # Cache the results
            self._cached_results = products
            
            print(f"✅ Product search returned {len(products)} products")
            return products
            
        except Exception as e:
            print(f"❌ Product search failed: {e}")
            return []

    async def _search_custom_components(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for individual components needed for a custom build"""
        try:
            components = []
            custom_reqs = requirements.get('custom_build_requirements', {})
            device_type = custom_reqs.get('device_type', '').lower()
            
            # Search based on device type
            if device_type in ['computer', 'pc', 'desktop', 'laptop']:
                # Search for computer components
                if custom_reqs.get('performance_requirements'):
                    perf_components = await self._search_performance_components(
                        requirements=custom_reqs.get('performance_requirements')
                    )
                    components.extend(perf_components)
                
                if custom_reqs.get('storage_requirements'):
                    storage_components = await self._search_storage_components(
                        requirements=custom_reqs.get('storage_requirements')
                    )
                    components.extend(storage_components)
                
                if custom_reqs.get('display_requirements'):
                    display_components = await self._search_display_components(
                        requirements=custom_reqs.get('display_requirements')
                    )
                    components.extend(display_components)
            
            elif device_type in ['server', 'workstation']:
                # Search for server/workstation components
                if custom_reqs.get('performance_requirements'):
                    server_components = await self._search_server_components(
                        requirements=custom_reqs.get('performance_requirements')
                    )
                    components.extend(server_components)
            
            elif device_type in ['peripheral', 'accessory']:
                # Search for peripherals
                peripheral_components = await self._search_peripheral_components(
                    requirements=custom_reqs
                )
                components.extend(peripheral_components)
            
            # Add connectivity components if needed
            if custom_reqs.get('connectivity_requirements'):
                connectivity_components = await self._search_connectivity_components(
                    requirements=custom_reqs.get('connectivity_requirements')
                )
                components.extend(connectivity_components)
            
            # Add form factor and OS recommendations if applicable
            if custom_reqs.get('form_factor'):
                form_factor_components = await self._search_form_factor_components(
                    form_factor=custom_reqs.get('form_factor')
                )
                components.extend(form_factor_components)
            
            if custom_reqs.get('operating_system'):
                os_components = await self._search_os_components(
                    os_type=custom_reqs.get('operating_system')
                )
                components.extend(os_components)
            
            # Add additional features
            if custom_reqs.get('additional_features'):
                feature_components = await self._search_additional_features(
                    features=custom_reqs.get('additional_features')
                )
                components.extend(feature_components)
            
            # Group components by category
            grouped_components = self._group_components_by_category(components)
            
            # Add compatibility information
            grouped_components = self._add_compatibility_info(grouped_components)
            
            return grouped_components
            
        except Exception as e:
            print(f"❌ Error searching custom components: {e}")
            return []

    async def _search_performance_components(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for performance-related components (CPU, GPU, RAM)"""
        try:
            must_conditions = []
            
            if requirements.get('cpu'):
                must_conditions.append({"match": {"cpu_specs": requirements['cpu']}})
            
            if requirements.get('gpu'):
                must_conditions.append({"match": {"gpu_specs": requirements['gpu']}})
            
            if requirements.get('ram'):
                must_conditions.append({"match": {"ram_specs": requirements['ram']}})
            
            search_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                }
            }
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching performance components: {e}")
            return []

    async def _search_display_components(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for display components"""
        try:
            must_conditions = [{"match": {"category": "display"}}]
            
            if requirements.get('size'):
                must_conditions.append({"match": {"size": requirements['size']}})
            
            if requirements.get('resolution'):
                must_conditions.append({"match": {"resolution": requirements['resolution']}})
            
            if requirements.get('panel_type'):
                must_conditions.append({"match": {"panel_type": requirements['panel_type']}})
            
            search_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                }
            }
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching display components: {e}")
            return []

    async def _search_peripheral_components(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for peripheral components"""
        try:
            must_conditions = [{"match": {"category": "peripheral"}}]
            
            if requirements.get('type'):
                must_conditions.append({"match": {"peripheral_type": requirements['type']}})
            
            if requirements.get('connectivity'):
                must_conditions.append({"match": {"connectivity": requirements['connectivity']}})
            
            search_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                }
            }
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching peripheral components: {e}")
            return []

    async def _search_connectivity_components(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for connectivity components"""
        try:
            must_conditions = [{"match": {"category": "connectivity"}}]
            
            if requirements.get('type'):
                must_conditions.append({"match": {"connectivity_type": requirements['type']}})
            
            if requirements.get('speed'):
                must_conditions.append({"match": {"speed": requirements['speed']}})
            
            search_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                }
            }
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching connectivity components: {e}")
            return []

    async def _search_server_components(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for server-specific components"""
        try:
            must_conditions = [{"match": {"category": "server"}}]
            
            if requirements.get('cpu'):
                must_conditions.append({"match": {"cpu_specs": requirements['cpu']}})
            
            if requirements.get('ram'):
                must_conditions.append({"match": {"ram_specs": requirements['ram']}})
            
            if requirements.get('storage'):
                must_conditions.append({"match": {"storage_specs": requirements['storage']}})
            
            search_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                }
            }
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching server components: {e}")
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
{json.dumps(products, indent=2)}

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
            r'(?:high|mid|low)\s+performance',
            r'(?:\d+)\s*(?:gb|tb|ghz|cores?)',
            r'(?:gaming|workstation|server|desktop|laptop)',
            r'(?:display|monitor|screen)',
            r'(?:keyboard|mouse|printer|scanner)',
            r'(?:wireless|bluetooth|wifi)',
            r'(?:usb|thunderbolt|hdmi|displayport)',
            r'(?:storage|ssd|hdd|nvme)',
            r'(?:graphics|gpu|video)',
            r'(?:processor|cpu)',
            r'(?:memory|ram)'
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                technical_requirements.append(match.replace('_', ' ').title())
        
        # Extract business requirements
        business_requirements = []
        business_patterns = [
            r'(?:business|enterprise|professional)',
            r'(?:productivity|efficiency)',
            r'(?:collaboration|team)',
            r'(?:remote|work from home)',
            r'(?:budget|cost)',
            r'(?:scalable|expandable)',
            r'(?:reliable|durable)',
            r'(?:support|warranty)'
        ]
        
        for pattern in business_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                business_requirements.append(match.replace('_', ' ').title())
        
        # Extract product categories
        categories = []
        category_patterns = [
            r'(?:computer|pc|desktop|laptop)',
            r'(?:server|workstation)',
            r'(?:monitor|display)',
            r'(?:keyboard|mouse|printer|scanner)',
            r'(?:storage|nas)',
            r'(?:network|router|switch)',
            r'(?:accessory|peripheral)'
        ]
        
        for pattern in category_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                categories.append(match.replace('_', ' ').title())
        
        # Extract search terms
        search_terms = []
        key_terms = ['computer', 'server', 'workstation', 'peripheral', 'accessory', 'monitor', 'printer', 'storage']
        for term in key_terms:
            if term in text_lower:
                search_terms.append(term)
        
        return {
            'technical_requirements': technical_requirements or ['Standard performance', 'Basic specifications'],
            'business_requirements': business_requirements or ['Business use', 'Professional environment'],
            'product_categories': categories or ['Computer', 'Peripheral'],
            'search_terms': search_terms or ['computer', 'peripheral'],
            'use_case': 'Business technology solution',
            'industry': customer_context.get('industry') if customer_context else 'business',
            'extraction_method': 'fallback_pattern_based'
        }

    async def _search_storage_components(self, requirements: Dict[str, Any]) -> List[Dict]:
        """Search for storage components based on requirements"""
        try:
            search_body = {
                "query": {
                    "bool": {
                        "must": []
                    }
                }
            }
            
            # Add requirements to search body
            for key, value in requirements.items():
                if key in ['capacity', 'raid_support']:
                    search_body["query"]["bool"]["must"].append({"match": {key: value}})
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching storage components: {e}")
            return []

    async def _search_form_factor_components(self, form_factor: str) -> List[Dict]:
        """Search for components based on form factor requirements"""
        try:
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"form_factor": form_factor}}
                        ]
                    }
                }
            }
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching form factor components: {e}")
            return []

    async def _search_os_components(self, os_type: str) -> List[Dict]:
        """Search for operating system components"""
        try:
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"category": "operating_system"}},
                            {"match": {"os_type": os_type}}
                        ]
                    }
                }
            }
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching OS components: {e}")
            return []

    async def _search_additional_features(self, features: List[str]) -> List[Dict]:
        """Search for components with additional features"""
        try:
            must_conditions = []
            for feature in features:
                must_conditions.append({"match": {"features": feature}})
            
            search_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                }
            }
            
            results = await self.elasticsearch.client.search(
                index=self.elasticsearch.products_index,
                body=search_body
            )
            
            return [hit["_source"] for hit in results["hits"]["hits"]]
        except Exception as e:
            print(f"❌ Error searching additional features: {e}")
            return []

    def _group_components_by_category(self, components: List[Dict]) -> List[Dict]:
        """Group components by their category"""
        categories = {
            'storage': [],
            'network': [],
            'system': [],
            'form_factor': [],
            'operating_system': [],
            'additional_features': []
        }
        
        for component in components:
            category = component.get('category', 'other')
            if category in categories:
                categories[category].append(component)
        
        return [
            {'category': cat, 'components': comps}
            for cat, comps in categories.items()
            if comps
        ]
    
    def _add_compatibility_info(self, grouped_components: List[Dict]) -> List[Dict]:
        """Add compatibility information between components"""
        for group in grouped_components:
            if group['category'] == 'system':
                # Add compatibility notes for system components
                for component in group['components']:
                    component['compatibility_notes'] = self._generate_compatibility_notes(
                        component, grouped_components
                    )
        return grouped_components
    
    def _generate_compatibility_notes(self, component: Dict, all_components: List[Dict]) -> List[str]:
        """Generate compatibility notes for a component"""
        notes = []
        
        # Add compatibility checks based on component type
        if component.get('category') == 'system':
            # Check CPU socket compatibility with motherboard
            # Check RAM compatibility
            # Check storage interface compatibility
            pass
        
        return notes
    
    def _build_product_search_query(self, search_terms: List[str], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Build search query for products"""
        search_body = {
            "query": {
                "bool": {
                    "should": []
                }
            },
            "size": 10
        }
        
        # Add search terms
        for term in search_terms:
            search_body["query"]["bool"]["should"].append({
                "match": {
                    "name": term
                }
            })
        
        # Add category matching
        categories = requirements.get('product_categories', [])
        for category in categories:
            search_body["query"]["bool"]["should"].append({
                "match": {
                    "category": category
                }
            })
        
        # If no criteria, match all
        if not search_body["query"]["bool"]["should"]:
            search_body["query"] = {"match_all": {}}
        
        return search_body 