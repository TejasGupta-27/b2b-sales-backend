import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .base import AIProvider, AIMessage, AIResponse
from .quote_generation_agent import QuoteGenerationAgent
from .product_retriever_agent import ProductRetrieverAgent
from .conversation_flow_manager import ConversationFlowAgent

class EnhancedB2BSalesAgent(AIProvider):
    """Enhanced B2B Sales Agent with intelligent conversation flow management"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        
        # Initialize collaborative agents
        self.quote_agent = QuoteGenerationAgent(base_provider)
        self.retriever_agent = ProductRetrieverAgent(base_provider)
        self.flow_agent = ConversationFlowAgent(base_provider)  # New intelligent flow agent
        
        # Conversation context for multi-agent collaboration
        self.conversation_context = []
        self.product_recommendations = {}
        self.customer_requirements = {}
        
    @property
    def provider_name(self) -> str:
        return f"enhanced_b2b_sales_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate sales-focused responses with intelligent conversation flow management"""
        
        # Store conversation for agent collaboration
        self.conversation_context = messages
        
        print("🤝 Enhanced Sales Agent: Starting intelligent conversation flow analysis...")
        
        # Step 1: Use AI-powered flow analysis
        flow_analysis = await self.flow_agent.analyze_conversation_flow(messages, customer_context)
        
        print(f"🧠 AI Flow Analysis:")
        print(f"   📊 Business Context: {flow_analysis.get('business_context_score', 0)}%")
        print(f"   📊 Technical Requirements: {flow_analysis.get('technical_requirements_score', 0)}%")
        print(f"   📊 Decision Readiness: {flow_analysis.get('decision_readiness_score', 0)}%")
        print(f"   📈 Current Stage: {flow_analysis.get('current_stage', 'unknown')}")
        print(f"   🎯 Quote Ready: {flow_analysis.get('quote_ready', False)}")
        print(f"   🤖 AI Reasoning: {flow_analysis.get('reasoning', 'N/A')}")
        
        # Step 2: Get AI-powered action suggestions
        action_guidance = await self.flow_agent.suggest_next_actions(flow_analysis, messages)
        
        print(f"💡 AI Action Guidance: {action_guidance.get('primary_action', 'continue')}")
        
        # Step 3: Execute based on AI recommendations
        if flow_analysis.get('should_generate_quote', False):
            response = await self._handle_quote_ready_conversation(messages, customer_context, flow_analysis)
        else:
            response = await self._handle_discovery_conversation(messages, customer_context, flow_analysis)
        
        # Step 4: Add intelligent flow analysis to metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'ai_flow_analysis': flow_analysis,
            'action_guidance': action_guidance,
            'intelligent_flow_managed': True
        })
        
        return response
    
    async def _handle_premature_pricing_request(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Handle when customer asks for pricing too early"""
        
        print("⚠️ Handling premature pricing request - redirecting to discovery")
        
        # Build context for redirecting conversation
        missing_info = flow_analysis.get('missing_info', [])
        next_questions = flow_analysis.get('next_questions', [])
        
        redirect_prompt = f"""The customer is asking for pricing, but we need more information first to provide an accurate quote. 

MISSING INFORMATION: {', '.join(missing_info)}
SUGGESTED NEXT QUESTIONS: {next_questions}

Politely acknowledge their pricing interest, explain that you want to provide the most accurate quote possible, and ask 1-2 discovery questions to gather the missing information. Be consultative and helpful, not pushy.

Example approach: "I'd be happy to prepare a detailed quote for you! To ensure I recommend the right solution at the best value, let me ask a couple quick questions about..."
"""
        
        enhanced_messages = self._add_discovery_context(messages, customer_context, redirect_prompt)
        response = await self.base_provider.generate_response(enhanced_messages)
        
        return response
    
    async def _handle_quote_ready_conversation(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Handle conversation when ready for quote generation"""
        
        print("✅ Conversation ready for quote generation")
        
        # Step 1: Collaborate with retriever agent
        retrieval_result = await self._collaborate_with_retriever_agent(messages, customer_context)
        
        # Step 2: Generate sales response
        enhanced_messages = self._add_enhanced_sales_context(messages, customer_context, retrieval_result)
        response = await self.base_provider.generate_response(enhanced_messages)
        
        # Step 3: Generate quote
        response = await self._collaborate_with_quote_agent(response, customer_context, flow_analysis)
        
        # Step 4: Add retrieval metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'product_recommendations': retrieval_result.get('products', []),
            'solution_recommendations': retrieval_result.get('solutions', []),
            'retrieval_confidence': retrieval_result.get('retrieval_confidence', 0),
            'customer_requirements': retrieval_result.get('requirements', {})
        })
        
        return response
    
    async def _handle_discovery_conversation(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Handle discovery and information gathering conversations"""
        
        print(f"🔍 Handling discovery conversation - stage: {flow_analysis['current_stage']}")
        
        # Get product recommendations to inform conversation
        retrieval_result = await self._collaborate_with_retriever_agent(messages, customer_context)
        
        # Build discovery-focused context
        discovery_context = self._build_discovery_context(flow_analysis, retrieval_result)
        enhanced_messages = self._add_discovery_context(messages, customer_context, discovery_context)
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        # Add discovery guidance to metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'discovery_guidance': {
                'next_questions': flow_analysis.get('next_questions', []),
                'missing_info': flow_analysis.get('missing_info', []),
                'current_stage': flow_analysis['current_stage']
            },
            'product_intelligence': retrieval_result
        })
        
        return response
    
    def _build_discovery_context(self, flow_analysis: Dict[str, Any], retrieval_result: Dict[str, Any]) -> str:
        """Build context for discovery conversations"""
        
        current_stage = flow_analysis['current_stage']
        missing_info = flow_analysis.get('missing_info', [])
        next_questions = flow_analysis.get('next_questions', [])
        completion_scores = flow_analysis.get('completion_scores', {})
        
        context = f"""
CONVERSATION GUIDANCE FOR DISCOVERY STAGE: {current_stage.upper()}

CURRENT INFORMATION GATHERING STATUS:
• Business Context: {completion_scores.get('business_context', 0):.1%} complete
• Technical Requirements: {completion_scores.get('technical_requirements', 0):.1%} complete  
• Operational Requirements: {completion_scores.get('operational_requirements', 0):.1%} complete
• Pain Points: {completion_scores.get('pain_points', 0):.1%} complete

STILL NEEDED: {', '.join(missing_info) if missing_info else 'Information gathering on track'}

SUGGESTED NEXT QUESTIONS TO ASK:
{chr(10).join(f'• {q}' for q in next_questions) if next_questions else '• Continue natural conversation flow'}

DISCOVERY PRIORITIES FOR THIS STAGE:
"""
        
        if current_stage == "initial_discovery":
            context += """
• Focus on understanding their business and current challenges
• Ask about their industry, company size, and primary use cases
• Identify pain points with current solutions
• Keep technical questions high-level for now
"""
        elif current_stage == "deep_discovery":
            context += """
• Dive deeper into technical requirements and specifications
• Understand their workflow and performance needs
• Explore scalability and future growth requirements
• Discuss timeline and budget considerations
"""
        elif current_stage == "solution_presentation":
            context += """
• Present relevant solutions based on gathered requirements
• Highlight how solutions address their specific pain points
• Discuss implementation approach and timeline
• Prepare for transitioning to quote discussion
"""
        
        context += """

IMPORTANT: Do NOT offer quotes or detailed pricing until you have sufficient information. 
Focus on being consultative and asking insightful questions that demonstrate expertise.
If they ask for pricing early, politely redirect to gather more information first.
"""
        
        return context
    
    def _add_discovery_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        additional_context: str
    ) -> List[AIMessage]:
        """Add discovery-focused context to messages"""
        
        system_prompt = self._build_discovery_system_prompt()
        
        enhanced_messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="system", content=additional_context),
        ]
        
        # Add customer context if available
        if customer_context:
            customer_info = self._build_customer_context(customer_context)
            enhanced_messages.append(AIMessage(role="system", content=customer_info))
        
        # Add conversation history
        enhanced_messages.extend(messages)
        
        return enhanced_messages
    
    def _build_discovery_system_prompt(self) -> str:
        """Build system prompt focused on discovery and information gathering"""
        
        return """You are an expert B2B technology sales consultant with deep expertise in enterprise solutions. Your primary role is to understand your prospects' business needs through consultative selling.

KEY RESPONSIBILITIES:
1. 🔍 DISCOVER business challenges and technical requirements through thoughtful questioning
2. 🎯 QUALIFY prospects by understanding their decision-making process, timeline, and budget
3. 🤝 BUILD TRUST by demonstrating expertise and genuinely caring about their success
4. 💡 EDUCATE about solutions only after understanding their specific needs
5. 📊 GATHER sufficient information before discussing pricing or quotes

DISCOVERY METHODOLOGY:
• Ask open-ended questions that uncover business impact
• Listen actively and ask follow-up questions
• Understand their current state vs. desired future state
• Identify all stakeholders involved in the decision
• Explore their evaluation criteria and success metrics

CONSULTATIVE SELLING PRINCIPLES:
• Be genuinely curious about their business
• Share relevant insights and best practices
• Position yourself as a trusted advisor, not just a vendor
• Focus on business outcomes, not just technical features
• Create value in every interaction

CONVERSATION FLOW RULES:
• Always gather sufficient context before proposing solutions
• Ask about business impact and consequences of current challenges
• Understand their evaluation process and timeline
• Never rush to pricing - focus on fit and value first
• When they ask for pricing early, redirect professionally to gather more context

COMMUNICATION STYLE:
• Professional yet conversational
• Consultative and advisory
• Ask insightful questions that demonstrate expertise
• Show genuine interest in their success
• Be patient with the discovery process

Remember: Your goal is to thoroughly understand their needs so you can recommend the perfect solution. Quality discovery leads to better solutions and higher close rates."""

    async def _collaborate_with_retriever_agent(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Collaborate with retriever agent to get dynamic product recommendations"""
        
        print("🔍 Sales Agent: Collaborating with Retriever Agent...")
        
        try:
            retrieval_result = await self.retriever_agent.analyze_conversation_and_retrieve(
                messages, customer_context
            )
            
            print(f"✅ Retriever Agent provided {len(retrieval_result.get('products', []))} products and {len(retrieval_result.get('solutions', []))} solutions")
            
            # Store for future reference
            self.product_recommendations = retrieval_result
            self.customer_requirements = retrieval_result.get('requirements', {})
            
            return retrieval_result
            
        except Exception as e:
            print(f"⚠️ Retriever collaboration failed: {e}")
            return {
                'products': [],
                'solutions': [],
                'requirements': {},
                'retrieval_confidence': 0,
                'error': str(e)
            }
    
    async def _collaborate_with_quote_agent(
        self, 
        response: AIResponse, 
        customer_context: Optional[Dict],
        flow_analysis: Dict[str, Any]
    ) -> AIResponse:
        """Enhanced collaboration with quote agent using flow analysis"""
        
        # Ensure response has metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        print(f"🎯 Sales Agent: Collaborating with Quote Agent...")
        print(f"🔍 Quote ready status: {flow_analysis.get('quote_ready', False)}")
        print(f"🔍 Should generate quote: {flow_analysis.get('should_generate_quote', False)}")
        
        # Enhanced conversation context with retriever findings and flow analysis
        enhanced_conversation = self._enhance_conversation_for_quote_generation(flow_analysis)
        
        # Prepare enhanced customer context
        enhanced_customer_context = {
            **(customer_context or {}),
            'product_recommendations': self.product_recommendations.get('products', []),
            'solution_recommendations': self.product_recommendations.get('solutions', []),
            'extracted_requirements': self.customer_requirements,
            'conversation_analysis': flow_analysis,
            'flow_confidence': flow_analysis.get('confidence_level', 'medium'),
            'business_context_score': flow_analysis.get('business_context_score', 50),
            'technical_requirements_score': flow_analysis.get('technical_requirements_score', 50)
        }
        
        print(f"📝 Enhanced context prepared with {len(enhanced_conversation)} messages")
        
        # Let quote agent generate quote with enhanced context
        try:
            quote = await self.quote_agent.generate_quote_from_conversation(
                enhanced_conversation,
                enhanced_customer_context
            )
            
            if quote:
                print(f"✅ Quote Agent provided enhanced quote with ID: {quote.get('id')}")
                print(f"📄 PDF URL: {quote.get('pdf_url', 'Not generated')}")
                
                # Add quote to response metadata
                response.metadata['quote'] = quote
                response.metadata['quote_generated'] = True
                response.metadata['quote_id'] = quote.get('id')
                
                # Enhance sales response to incorporate the quote
                response = self._enhance_response_with_dynamic_quote(response, quote)
            else:
                print("❌ Quote agent couldn't generate quote from enhanced conversation")
                response.metadata['quote_generation_failed'] = True
                
                # Add fallback message
                response.content += "\n\n💡 I'd be happy to prepare a detailed quote for you! Let me gather a bit more information to ensure I provide the most accurate recommendations."
                
        except Exception as e:
            print(f"❌ Error in quote generation: {str(e)}")
            response.metadata['quote_error'] = str(e)
            
            # Add error handling message
            response.content += "\n\n💡 I'm ready to prepare a quote for you! Let me just verify a few details to ensure accuracy."
        
        return response
    
    def _enhance_conversation_for_quote_generation(self, flow_analysis: Dict[str, Any]) -> List[AIMessage]:
        """Enhance conversation context with flow analysis for better quote generation"""
        
        enhanced_messages = list(self.conversation_context)
        
        # Add system message with comprehensive context
        context_summary = f"""
CONVERSATION FLOW ANALYSIS FOR QUOTE GENERATION:

READINESS ASSESSMENT:
• Current Stage: {flow_analysis['current_stage']}
• Quote Ready: {flow_analysis['quote_ready']}
• Conversation Quality: {flow_analysis.get('conversation_quality', {})}

INFORMATION COMPLETENESS:
• Business Context: {flow_analysis['completion_scores'].get('business_context', 0):.1%}
• Technical Requirements: {flow_analysis['completion_scores'].get('technical_requirements', 0):.1%}  
• Operational Requirements: {flow_analysis['completion_scores'].get('operational_requirements', 0):.1%}
• Pain Points Understanding: {flow_analysis['completion_scores'].get('pain_points', 0):.1%}

DYNAMIC PRODUCT RECOMMENDATIONS:
{json.dumps(self.product_recommendations.get('products', [])[:3], indent=2)}

SOLUTION RECOMMENDATIONS:
{json.dumps(self.product_recommendations.get('solutions', []), indent=2)}

Use this comprehensive analysis to generate a well-informed, accurate quote that addresses the customer's specific needs and requirements identified through proper discovery.
"""
        
        enhanced_messages.insert(-1, AIMessage(
            role="system", 
            content=context_summary
        ))
        
        return enhanced_messages
    
    def _add_enhanced_sales_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict],
        retrieval_result: Dict[str, Any]
    ) -> List[AIMessage]:
        """Add enhanced sales context for quote-ready conversations"""
        
        system_prompt = """You are an expert B2B technology sales consultant ready to present solutions and discuss pricing. The prospect has provided sufficient information about their needs, and you're now transitioning to solution presentation and quote discussion.

CURRENT FOCUS:
• Present tailored solutions based on gathered requirements
• Highlight specific business benefits and ROI
• Address any remaining concerns or questions
• Facilitate transition to formal quote discussion
• Create urgency and motivation to move forward

APPROACH:
• Summarize your understanding of their needs
• Present recommended solutions with clear business justification
• Discuss implementation approach and timeline
• Address pricing and next steps professionally
• Maintain consultative approach while moving toward close"""
        
        dynamic_product_info = self._build_dynamic_product_context(retrieval_result)
        
        enhanced_messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="system", content=dynamic_product_info),
        ]
        
        # Add customer context if available
        if customer_context:
            customer_info = self._build_customer_context(customer_context)
            enhanced_messages.append(AIMessage(role="system", content=customer_info))
        
        # Add conversation history
        enhanced_messages.extend(messages)
        
        return enhanced_messages
    
    def _build_dynamic_product_context(self, retrieval_result: Dict[str, Any]) -> str:
        """Build dynamic product context from retrieval results"""
        
        context = "🛍️ DYNAMIC PRODUCT INTELLIGENCE:\n\n"
        
        products = retrieval_result.get('products', [])
        solutions = retrieval_result.get('solutions', [])
        requirements = retrieval_result.get('requirements', {})
        
        if products:
            context += "=== RELEVANT PRODUCTS FOUND ===\n"
            for product in products[:3]:  # Top 3 products
                context += f"• {product.get('name', 'Unknown')}: {product.get('description', 'No description')}\n"
                if 'price' in product:
                    context += f"  Price: ${product['price']:,.2f}\n"
                context += f"  Match Score: {product.get('_score', 0):.2f}\n\n"
        
        if solutions:
            context += "=== RELEVANT SOLUTIONS FOUND ===\n"
            for solution in solutions:
                context += f"• {solution.get('name', 'Unknown')}: {solution.get('description', 'No description')}\n"
                if 'target_price' in solution:
                    context += f"  Target Price: ${solution['target_price']:,.2f}\n"
                context += f"  Match Score: {solution.get('_score', 0):.2f}\n\n"
        
        if requirements:
            context += "=== CUSTOMER REQUIREMENTS ANALYSIS ===\n"
            
            categories = requirements.get('product_categories', [])
            if categories:
                context += f"Product Categories Needed: {', '.join(categories)}\n"
            
            tech_specs = requirements.get('technical_specs', {})
            if tech_specs:
                context += f"Technical Requirements: {', '.join([f'{k}: {v}' for k, v in tech_specs.items()])}\n"
            
            business_reqs = requirements.get('business_requirements', {})
            if business_reqs:
                context += f"Business Requirements: {json.dumps(business_reqs)}\n"
            
            context += "\n"
        
        # Retrieval confidence
        confidence = retrieval_result.get('retrieval_confidence', 0)
        context += f"🎯 RECOMMENDATION CONFIDENCE: {confidence:.1%}\n"
        
        if confidence < 0.5:
            context += "⚠️ Low confidence - focus on discovery to improve recommendations\n"
        elif confidence > 0.8:
            context += "✅ High confidence - strong product-customer match identified\n"
        
        context += "\n💡 Use these dynamic recommendations to provide highly relevant, personalized suggestions!"
        
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
    
    def _get_stage_guidance(self, stage: str) -> Dict[str, Any]:
        """Get guidance for the current conversation stage"""
        
        guidance = {
            "initial_discovery": {
                "focus": "Understand business context and high-level challenges",
                "objectives": ["Industry/company size", "Primary use cases", "Current pain points"],
                "avoid": ["Technical details", "Pricing discussions", "Product recommendations"]
            },
            "deep_discovery": {
                "focus": "Explore technical requirements and operational needs",
                "objectives": ["Technical specifications", "Performance requirements", "Timeline/budget"],
                "avoid": ["Premature solution presentation", "Detailed pricing"]
            },
            "solution_presentation": {
                "focus": "Present tailored solutions and build value",
                "objectives": ["Solution recommendations", "Business benefits", "ROI discussion"],
                "avoid": ["Generic presentations", "Feature dumping"]
            },
            "qualification_complete": {
                "focus": "Finalize requirements and prepare for quote",
                "objectives": ["Confirm all requirements", "Discuss next steps", "Quote preparation"],
                "avoid": ["Reopening discovery unnecessarily"]
            },
            "premature_pricing_request": {
                "focus": "Redirect to gather necessary information",
                "objectives": ["Explain need for more info", "Ask key discovery questions"],
                "avoid": ["Providing estimates without context", "Being pushy"]
            }
        }
        
        return guidance.get(stage, {
            "focus": "Continue consultative conversation",
            "objectives": ["Understand customer needs"],
            "avoid": ["Rushing the process"]
        })
    
    def _enhance_response_with_dynamic_quote(self, response: AIResponse, quote: Dict[str, Any]) -> AIResponse:
        """Enhanced response with dynamic quote information"""
        
        if 'pdf_url' in quote:
            # Add professional quote presentation with dynamic context
            response.content += f"\n\n🎯 **Excellent! Based on our thorough discussion and your specific requirements, I've prepared a comprehensive, customized quote using our intelligent product matching system.**"
            response.content += f"\n\n📋 **Quote #{quote.get('quote_number', 'N/A')}**"
            
            # Highlight the thorough discovery process
            response.content += f"\n\n✅ **Complete Requirements Analysis:** Our conversation covered all the essential areas needed for an accurate quote - your business context, technical requirements, operational needs, and specific challenges."
            
            # Highlight the intelligent matching
            if self.product_recommendations.get('retrieval_confidence', 0) > 0.7:
                response.content += f"\n\n🤖 **AI-Powered Recommendations:** Our system identified a {self.product_recommendations.get('retrieval_confidence', 0):.1%} match with your requirements based on our comprehensive product intelligence!"
            
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
            
            # Enhanced next steps
            response.content += f"\n\n**Next Steps:**"
            response.content += f"\n1. Review the detailed quote with all selected products and solutions"
            response.content += f"\n2. Let me know if you'd like to discuss any aspects in more detail"
            response.content += f"\n3. I can arrange product demos or technical consultations if helpful"
            response.content += f"\n4. We can finalize implementation timeline and support arrangements"
            
            response.content += f"\n\nThis quote reflects our thorough understanding of your business needs and technical requirements. I'm confident these recommendations will deliver the performance and value you're looking for! 🚀"
            
        return response 