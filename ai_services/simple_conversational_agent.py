import json
import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from io import BytesIO
import logging
import langdetect
from pydantic import BaseModel, Field
import time

from .base import AIProvider, AIMessage, AIResponse
from services.prompt_manager import get_prompt_manager
from .hybrid_product_retriever_agent import HybridProductRetrieverAgent, get_product_name
from .quote_generation_agent import QuoteGenerationAgent
from config import settings
from services.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)

class ConversationIntent(BaseModel):
    """Pydantic model for analyzing conversation intent"""
    intent_type: str = Field(description="Type of intent: 'product_inquiry', 'quote_request', 'general_chat', 'technical_question', 'pricing_inquiry'")
    should_retrieve_products: bool = Field(description="Whether product retrieval is needed")
    should_generate_quote: bool = Field(description="Whether quote generation is needed")
    confidence: float = Field(description="Confidence in the intent analysis (0.0 to 1.0)")
    reasoning: str = Field(description="Reasoning for the decision")
    missing_info: List[str] = Field(description="Missing information needed for product retrieval or quote generation")
    suggested_questions: List[str] = Field(description="Suggested follow-up questions")

class SimpleConversationalAgent(AIProvider):
    """Simple, conversational B2B sales agent with intelligent product retrieval and quote generation"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.conversation_memory = {}
        self.prompt_manager = get_prompt_manager()
        
        # Inherit token tracking from base provider
        if hasattr(self.base_provider, 'usage_tracker'):
            self.usage_tracker = self.base_provider.usage_tracker
        
        # Initialize hybrid product retriever if configured
        self.hybrid_retriever = None
        if settings.use_hybrid_retriever and settings.azure_embedding_endpoint and settings.azure_embedding_api_key:
            try:
                self.hybrid_retriever = HybridProductRetrieverAgent(
                    base_provider=base_provider,
                    azure_embedding_endpoint=settings.azure_embedding_endpoint,
                    azure_embedding_key=settings.azure_embedding_api_key
                )
                print("✅ Hybrid Product Retriever initialized for SimpleConversationalAgent")
            except Exception as e:
                print(f"⚠️ Failed to initialize hybrid retriever: {e}")
        
        # Initialize quote generation agent
        self.quote_agent = QuoteGenerationAgent(base_provider)
        print("✅ Quote Generation Agent initialized for SimpleConversationalAgent")
        
        # Initialize metrics service
        self.metrics_service = get_metrics_service()
        
    @property
    def provider_name(self) -> str:
        return f"simple_conversational_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def initialize(self):
        """Initialize the agent and its components"""
        try:
            if self.hybrid_retriever:
                await self.hybrid_retriever.initialize()
                # Ensure the vector service has the LLM provider for category detection
                if hasattr(self.hybrid_retriever, 'vector_service') and self.hybrid_retriever.vector_service:
                    self.hybrid_retriever.vector_service.set_llm_provider(self.base_provider)
                    print("✅ LLM provider configured for intelligent category detection")
            print("✅ SimpleConversationalAgent initialized successfully")
        except Exception as e:
            print(f"⚠️ SimpleConversationalAgent initialization warning: {e}")
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate intelligent responses with product retrieval and quote generation capabilities"""
        
        # Extract current_user from kwargs if provided
        current_user = kwargs.get('current_user', None)
        
        print(f"🤖 SimpleConversationalAgent: Processing {len(messages)} messages...")
        
        # Step 1: Analyze conversation intent
        intent_analysis = await self._analyze_conversation_intent(messages, customer_context)
        print(f"   Intent: {intent_analysis.intent_type}, Confidence: {intent_analysis.confidence:.2f}")
        
        # Step 2: Retrieve products/solutions only if needed
        product_data = None
        if intent_analysis.should_retrieve_products:
            try:
                retrieval_start_time = time.time()
                product_data = await self._retrieve_relevant_products(messages, customer_context, intent_analysis)
                retrieval_duration = time.time() - retrieval_start_time
                
                print(f"✅ Retrieved {len(product_data.get('products', []))} products, {len(product_data.get('solutions', []))} solutions")
                print(f"   LLM Context: {product_data.get('requirements', {}).get('llm_context', {}).get('primary_need', 'Unknown')}")
                print(f"   Similar Products Analysis: {product_data.get('similar_products_analysis', False)}")
                
                # Log AI enhancement status if available
                if product_data.get('ai_enhanced'):
                    print(f"   🧠 AI-Enhanced Search: Enabled")
                    print(f"   Search Methods: {product_data.get('search_methods', {}).get('methods', [])}")
                else:
                    print(f"   🔄 Standard Search: No AI enhancement")
                
                # --- METRICS: Record product recommendations ---
                for p in product_data.get('products', []):
                    category = p.get('category', 'unknown')
                    product_id = p.get('id', p.get('product_id', 'unknown'))
                    product_name = p.get('name', p.get('title', 'Unknown Product'))
                    self.metrics_service.record_product_recommendation(category, product_id, product_name)
                # --- END METRICS ---
                
            except Exception as e:
                print(f"⚠️ Product retrieval failed: {e}")
                product_data = {'products': [], 'solutions': [], 'error': str(e)}
        
        # Step 3: Generate appropriate response based on intent
        if intent_analysis.should_generate_quote:
            response = await self._generate_quote_response(messages, customer_context, product_data, intent_analysis, current_user)
        elif intent_analysis.should_retrieve_products and product_data:
            response = await self._generate_product_response(messages, customer_context, product_data, intent_analysis)
        else:
            response = await self._generate_general_response(messages, customer_context, intent_analysis)
        
        # Step 4: Add metadata
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'agent_type': 'simple_conversational',
            'conversation_style': 'natural',
            'response_time': datetime.now().isoformat(),
            'config_source': 'prompt_manager',
            'intent_analysis': intent_analysis.model_dump(),
            'product_retrieved': intent_analysis.should_retrieve_products,
            'quote_generated': intent_analysis.should_generate_quote,
            'hybrid_retriever_used': self.hybrid_retriever is not None
        })
        
        if product_data:
            response.metadata['product_data'] = {
                'total_products': len(product_data.get('products', [])),
                'total_solutions': len(product_data.get('solutions', [])),
                'retrieval_method': product_data.get('retrieval_method', 'none'),
                'fusion_method': product_data.get('fusion_method', 'none'),
                'retrieval_confidence': product_data.get('retrieval_confidence', 0.0)
            }
        
        return response
    
    async def _retrieve_relevant_products(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]], 
        intent_analysis: ConversationIntent
    ) -> Dict[str, Any]:
        """Retrieve relevant products using the hybrid retriever"""
        if self.hybrid_retriever:
            return await self.hybrid_retriever.retrieve_products(messages, customer_context)
        else:
            return {'products': [], 'solutions': [], 'error': 'Hybrid retriever not available'}

    async def _analyze_conversation_intent(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> ConversationIntent:
        """Analyze conversation intent using Pydantic function calling - focus on discovery first"""
        
        conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages[-3:]])  # Last 3 messages
        
        analysis_prompt = f"""Analyze this conversation to understand the customer's needs and the natural flow of the discussion.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT: {customer_context or 'None provided'}

CONVERSATION ANALYSIS:
1. What is the customer talking about or asking for?
2. What stage of the conversation are we in? (greeting, discovery, solution discussion, etc.)
3. What would be the most helpful next step in the conversation?
4. Do they seem ready for product recommendations or still exploring their needs?
5. What information would help me provide better assistance?

GUIDELINES:
- Focus on being helpful and natural, not following rigid rules
- **Be very conservative about product retrieval** - only retrieve products if they have provided substantial requirements AND explicitly ask for recommendations
- If they're asking about products or solutions but haven't provided enough context, focus on gathering more information first
- If they're still exploring or haven't shared much, focus on learning about their needs
- Trust your judgment about what would be most helpful to them
- Don't overthink it - just be genuinely helpful

EXAMPLES OF WHEN NOT TO RETRIEVE PRODUCTS:
- Customer mentions a product category but no specific requirements
- Customer asks general questions about technology
- Customer hasn't provided budget, timeline, or specific use cases
- Customer is still in early discovery phase
- Customer just mentioned what they're looking for but hasn't provided enough context

EXAMPLES OF WHEN TO RETRIEVE PRODUCTS:
- Customer has provided detailed requirements (budget, timeline, specific needs) AND explicitly asks for recommendations
- Customer has described their use case in detail AND asks for product suggestions
- Customer is ready for solution presentation phase

Remember: This is a natural conversation, not a sales process checklist. Do what feels right to help the customer, but err on the side of gathering more information first."""

        try:
            intent_analysis = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=analysis_prompt)],
                ConversationIntent
            )
            return intent_analysis
        except Exception as e:
            print(f"⚠️ Intent analysis failed: {e}")
            # Fallback to conservative analysis
            return ConversationIntent(
                intent_type="discovery",
                should_retrieve_products=False,
                should_generate_quote=False,
                confidence=0.5,
                reasoning="Fallback analysis - focusing on discovery",
                missing_info=["specific requirements", "budget", "timeline", "use case details"],
                suggested_questions=["What specific problem are you trying to solve?", "What's your budget range?", "When do you need this solution?"]
            )
    
    async def _generate_quote_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        product_data: Optional[Dict[str, Any]],
        intent_analysis: ConversationIntent,
        current_user: Optional[Any]
    ) -> AIResponse:
        """Generate quote response with focus on gathering missing information first"""
        
        print("💰 Generating quote response...")
        
        # Get quote-specific guidance from prompt manager
        quote_guidance = self.prompt_manager.get_prompt("conversational_agent", "quote_guidance", "")
        
        if not quote_guidance:
            quote_guidance = """The customer is asking for a quote. Help them get what they need in a natural, conversational way.

APPROACH:
- Acknowledge their quote request warmly
- Check if you have all the information needed for an accurate quote
- If you need more details, ask for them naturally
- If you have enough information, provide a summary and next steps
- Be helpful and professional, not pushy

EXAMPLES:
- "Perfect! I've put together a quote for the PC build we discussed..."
- "Great! Here's what I've come up with for your setup..."
- "Awesome! I've got the pricing ready for you..."

Remember: You're having a conversation, not sending a formal business document. Be natural and helpful."""
        
        # Build enhanced context
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Add missing information context - prioritize this
        if intent_analysis.missing_info:
            missing_info_context = f"""
Note: You might want to learn more about their needs as the conversation progresses, but don't make this feel like an interrogation. Just be naturally curious and helpful.
"""
            enhanced_messages.append(AIMessage(role="system", content=missing_info_context))
        
        # Add product context if available (but don't prioritize it)
        if product_data and product_data.get('products'):
            product_context = self._build_product_context(product_data)
            enhanced_messages.append(AIMessage(role="system", content=product_context))
        
        # Add quote guidance
        enhanced_messages.append(AIMessage(role="system", content=quote_guidance))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'quote_request': True,
            'missing_info': intent_analysis.missing_info,
            'suggested_questions': intent_analysis.suggested_questions,
            'requirements_complete': len(intent_analysis.missing_info) == 0
        })
        
        # If we have enough information, generate the actual quote
        # Be more lenient - if customer explicitly asks for quote, generate it even with some missing info
        should_generate_quote = (
            len(intent_analysis.missing_info) == 0 or  # Complete requirements
            intent_analysis.confidence > 0.8 or  # High confidence in intent
            any(keyword in messages[-1].content.lower() for keyword in ['quote', 'price', 'cost', 'total'])  # Explicit quote request
        )
        
        if should_generate_quote:
            try:
                print("✅ Generating quote (requirements complete or explicit request)...")
                if len(intent_analysis.missing_info) > 0:
                    print(f"   Note: Some missing info: {intent_analysis.missing_info}")
                
                quote = await self.generate_quote({
                    'conversation_messages': messages,
                    'customer_context': customer_context,
                    'current_user': current_user
                })
                
                if quote and not quote.get('error'):
                    # Enhance response with quote information
                    response = self._enhance_response_with_quote_info(response, quote)
                    
                    # Update metadata with quote information
                    if not hasattr(response, 'metadata') or response.metadata is None:
                        response.metadata = {}
                    response.metadata.update({
                        'quote_generated': True,
                        'quote_id': quote.get('quote_id'),
                        'quote_number': quote.get('quote_number'),
                        'pdf_generated': quote.get('pdf_generated', False),
                        'pdf_url': quote.get('pdf_url'),
                        'pitch_deck_generated': quote.get('pitch_deck_generated', False),
                        'pitch_deck_url': quote.get('pitch_deck_url'),
                        'quote_total': quote.get('financials', {}).get('total') if 'financials' in quote else quote.get('total'),
                        'requirements_complete': len(intent_analysis.missing_info) == 0
                    })
                else:
                    response.metadata['quote_generation_error'] = quote.get('error', 'Unknown error') if quote else 'No quote returned'
                    
            except Exception as e:
                print(f"❌ Quote generation failed: {e}")
                if not hasattr(response, 'metadata') or response.metadata is None:
                    response.metadata = {}
                response.metadata['quote_generation_error'] = str(e)
        else:
            print(f"⚠️ Not generating quote yet - missing info: {intent_analysis.missing_info}")
            response.metadata['requirements_complete'] = False
        
        return response
    
    def _enhance_response_with_quote_info(self, response: AIResponse, quote: dict) -> AIResponse:
        """Enhance response with quote information including PDF and pitch deck,
        switching language based on detected language of the initial response."""

        original_content = response.content.strip()
        try:
            detected_lang = langdetect.detect(original_content)
        except:
            detected_lang = "en"  # fallback to English

        is_japanese = detected_lang.startswith("ja")

        # Localization dictionary for Japanese / English
        localized = {
            "quote_details": "📋 **見積もり詳細:**" if is_japanese else "📋 **Quote Details:**",
            "quote_number": "見積番号" if is_japanese else "Quote Number",
            "subtotal": "小計" if is_japanese else "Subtotal",
            "tax": "税金" if is_japanese else "Tax",
            "total": "合計" if is_japanese else "Total",
            "valid_until": "有効期限" if is_japanese else "Valid until",
            "download_pdf": "📄 **[見積書PDFをダウンロード]({url})**" if is_japanese else "📄 **[Download Complete Quote PDF]({url})**",
            "download_pitch_deck": "📊 **[ピッチデッキをダウンロード]({url})**" if is_japanese else "📊 **[Download Pitch Deck]({url})**",
            "whats_next": "次のステップ" if is_japanese else "What's next?",
            "review_quote": "見積もり内容をご確認いただき、ご質問があればお知らせください" if is_japanese else "Review the detailed quote and let me know if you have any questions",
            "check_pitch_deck": "ピッチデッキでビジュアル概要をご覧ください" if is_japanese else "Check out the pitch deck for a visual overview",
            "here_to_help": "ご不明な点や調整がありましたらお手伝いいたします" if is_japanese else "I'm here to help with any clarifications or adjustments",
            "perfect_intro": "完璧です！ご相談に基づいて詳細な見積もりを作成しました。" if is_japanese else "Perfect! I've put together a detailed quote based on our discussion.",
            "quote_valid_until": "見積有効期限" if is_japanese else "Quote valid until",
            "pdf_generating": "見積書PDF：現在生成中..." if is_japanese else "Quote PDF: Currently being generated...",
            "pdf_error_note": "（注：PDF生成に問題が発生しました。必要に応じてサポートにお問い合わせください）" if is_japanese else "(Note: PDF generation encountered an issue - please contact support if needed)",
            "what_happens_next": "次に何が起こるか" if is_japanese else "What happens next?",
            "take_look": "詳細な見積もりをご確認いただき、調整が必要な場合はお知らせください" if is_japanese else "Take a look at the detailed quote and let me know if anything needs adjusting",
            "feel_free_questions": "ご質問や変更のリクエストはお気軽にどうぞ" if is_japanese else "Feel free to ask any questions or request changes",
            "move_forward": "ご満足いただけましたら、次のステップに進みましょう" if is_japanese else "Once you're happy with it, we can move forward with the next steps",
        }

        # Helper to format money with comma and 2 decimals
        def fmt_money(val):
            return f"${val:,.2f}"

        # Check if the response already mentions quote
        keywords = ['quote', 'price', 'cost', 'total', 'pricing']
        has_quote_mention = any(kw in original_content.lower() for kw in keywords)

        if has_quote_mention:
            # Add details naturally
            response.content += f"\n\n{localized['quote_details']}"
            response.content += f"\n• {localized['quote_number']}: {quote.get('quote_number', 'N/A')}"

            if 'financials' in quote:
                fin = quote['financials']
                response.content += f"\n• {localized['subtotal']}: {fmt_money(fin['subtotal'])}"
                response.content += f"\n• {localized['tax']}: {fmt_money(fin['tax_amount'])}"
                response.content += f"\n• **{localized['total']}: {fmt_money(fin['total'])}**"
            elif 'pricing' in quote:
                pricing = quote['pricing']
                response.content += f"\n• {localized['subtotal']}: {fmt_money(pricing['subtotal'])}"
                response.content += f"\n• {localized['tax']}: {fmt_money(pricing['tax_amount'])}"
                response.content += f"\n• **{localized['total']}: {fmt_money(pricing['total'])}**"

            if quote.get('valid_until'):
                try:
                    dt_str = datetime.fromisoformat(quote['valid_until']).strftime('%B %d, %Y')
                except:
                    dt_str = quote['valid_until']
                response.content += f"\n• {localized['valid_until']}: {dt_str}"

            if quote.get('pdf_generated', False) and quote.get('pdf_url'):
                response.content += "\n\n" + localized['download_pdf'].format(url=quote['pdf_url'])
            if quote.get('pitch_deck_generated', False) and quote.get('pitch_deck_url'):
                response.content += "\n\n" + localized['download_pitch_deck'].format(url=quote['pitch_deck_url'])

            response.content += f"\n\n**{localized['whats_next']}**"
            response.content += f"\n• {localized['review_quote']}"
            if quote.get('pitch_deck_generated', False):
                response.content += f"\n• {localized['check_pitch_deck']}"
            response.content += f"\n• {localized['here_to_help']}"

        else:
            # LLM did not mention quote, add full conversational intro & details
            response.content += f"\n\n{localized['perfect_intro']}"
            response.content += f"\n\n📋 **{localized['quote_number']} #{quote.get('quote_number', 'N/A')}**"

            if 'financials' in quote:
                fin = quote['financials']
                response.content += f"\n\n💰 **{localized['subtotal']}・{localized['tax']}・{localized['total']} の内訳はこちら：**" if is_japanese else f"\n\n💰 Here's the breakdown:"
                response.content += f"\n• {localized['subtotal']}: {fmt_money(fin['subtotal'])}"
                response.content += f"\n• {localized['tax']}: {fmt_money(fin['tax_amount'])}"
                response.content += f"\n• **{localized['total']}: {fmt_money(fin['total'])}**"
            elif 'pricing' in quote:
                pricing = quote['pricing']
                response.content += f"\n\n💰 **{localized['subtotal']}・{localized['tax']}・{localized['total']} の内訳はこちら：**" if is_japanese else f"\n\n💰 Here's the breakdown:"
                response.content += f"\n• {localized['subtotal']}: {fmt_money(pricing['subtotal'])}"
                response.content += f"\n• {localized['tax']}: {fmt_money(pricing['tax_amount'])}"
                response.content += f"\n• **{localized['total']}: {fmt_money(pricing['total'])}**"

            if quote.get('valid_until'):
                try:
                    dt_str = datetime.fromisoformat(quote['valid_until']).strftime('%B %d, %Y')
                except:
                    dt_str = quote['valid_until']
                response.content += f"\n• {localized['quote_valid_until']}: {dt_str}"

            if quote.get('pdf_generated', False) and quote.get('pdf_url'):
                response.content += "\n\n" + localized['download_pdf'].format(url=quote['pdf_url'])
            else:
                response.content += f"\n\n{localized['pdf_generating']}"
                if quote.get('pdf_error'):
                    response.content += f" {localized['pdf_error_note']}"

            if quote.get('pitch_deck_generated', False) and quote.get('pitch_deck_url'):
                response.content += "\n\n" + localized['download_pitch_deck'].format(url=quote['pitch_deck_url'])

            response.content += f"\n\n**{localized['what_happens_next']}**"
            response.content += f"\n• {localized['take_look']}"
            if quote.get('pitch_deck_generated', False):
                response.content += f"\n• {localized['check_pitch_deck']}"
            response.content += f"\n• {localized['feel_free_questions']}"
            response.content += f"\n• {localized['move_forward']}"

        return response
    
    async def _generate_product_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        product_data: Dict[str, Any],
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate response with product recommendations - only if requirements are complete"""
        
        print("📦 Generating product response...")
        
        # Get product-specific guidance from prompt manager
        product_guidance = self.prompt_manager.get_prompt("conversational_agent", "product_guidance", "")
        
        if not product_guidance:
            product_guidance = """The customer is asking about products and you have relevant recommendations to share.

APPROACH:
- Acknowledge their inquiry naturally
- Share relevant product recommendations with clear reasoning
- Explain why these products would be a good fit for their needs
- Be informative and helpful
- Ask if they'd like more details about any specific product
- Suggest next steps naturally (demo, quote, etc.)

Be helpful and knowledgeable, not pushy or salesy.



For the list of products provided, recommend a full build by selecting the best product(s) from each category (CPU, GPU, Memory, Storage, Power Supply, etc.). If a category is missing, mention that. Explain your choices for each category and how they fit the customer's needs."""
        
        # Build enhanced context
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Add product context (now grouped by category)
        product_context = self._build_product_context(product_data)
        enhanced_messages.append(AIMessage(role="system", content=product_context))
        
        # Add product guidance (explicit build prompt)
        enhanced_messages.append(AIMessage(role="system", content=product_guidance))
        
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'product_inquiry': True,
            'products_recommended': len(product_data.get('products', [])),
            'solutions_recommended': len(product_data.get('solutions', [])),
            'requirements_complete': len(intent_analysis.missing_info) == 0
        })
        
        return response
    
    async def _generate_general_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]],
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate general conversational response with focus on discovery"""
        
        print("💬 Generating general response with discovery focus...")
        
        # Build conversational context using prompt manager
        enhanced_messages = self._build_conversational_context(messages, customer_context)
        
        # Add discovery-focused guidance
        discovery_guidance = """You're having a natural conversation with a potential customer. Be helpful, informative, and genuinely interested in their needs.

APPROACH:
- Be conversational and warm
- Share relevant insights and information as you learn about them
- Ask follow-up questions that flow naturally from the conversation
- Be helpful and informative - don't just gather information
- Show that you understand their business and challenges
- Build rapport through knowledgeable, helpful responses

Remember: You're a knowledgeable consultant having a conversation, not a sales robot. Be human and helpful."""
        
        enhanced_messages.append(AIMessage(role="system", content=discovery_guidance))
        
        # Add suggested questions if available
        if intent_analysis.suggested_questions:
            questions_context = f"""
You might find these topics interesting to explore as the conversation flows naturally:
{chr(10).join([f"- {question}" for question in intent_analysis.suggested_questions])}

But don't feel obligated to ask them all - just let the conversation flow naturally.
"""
            enhanced_messages.append(AIMessage(role="system", content=questions_context))
        
        # Generate response
        response = await self.base_provider.generate_response(enhanced_messages)
        
        if not hasattr(response, 'metadata') or response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            'general_chat': True,
            'discovery_mode': True,
            'suggested_questions': intent_analysis.suggested_questions,
            'missing_info': intent_analysis.missing_info
        })
        
        return response
    
    def _build_product_context(self, product_data: Dict[str, Any]) -> str:
        """Build context from product data with LLM-powered insights, grouped by category for full build recommendations"""
        products = product_data.get('products', [])
        solutions = product_data.get('solutions', [])
        requirements = product_data.get('requirements', {})
        llm_context = requirements.get('llm_context', {})

        # Group products by category
        from collections import defaultdict
        cat_map = defaultdict(list)
        for p in products:
            cat_map[p.get('category', 'Other')].append(p)

        context = f"""
Here are the top recommended products by category for your needs:
"""
        for cat, plist in cat_map.items():
            context += f"\n{cat.title()}:\n"
            for i, p in enumerate(plist):  # ✅ All products in category (removed [:2] limit)
                context += f"  {i+1}. {get_product_name(p)} (${p.get('price', 'N/A')})\n"
                context += f"     Description: {p.get('description', 'No description')[:100]}...\n"
        context += "\nPlease recommend a full build using the best available products from each category above. If a category is missing, note that as well."

        # Add LLM context summary
        context += f"\n\nLLM Context Analysis:\n"
        context += f"Primary Need: {llm_context.get('primary_need', 'Not analyzed')}\n"
        context += f"Business Context: {llm_context.get('business_context', 'Not analyzed')}\n"
        context += f"Budget Level: {llm_context.get('budget_indicator', 'Not specified')}\n"
        context += f"Timeline: {llm_context.get('timeline', 'Not specified')}\n"
        context += f"Analysis Confidence: {llm_context.get('confidence', 0):.1%}\n"

        return context
    
    def _build_conversational_context(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> List[AIMessage]:
        """Build context for natural conversation using dynamic configuration from prompt manager"""
        
        # Get main system prompt from prompt manager
        system_prompt = self.prompt_manager.get_system_prompt("conversational_agent")
        
        # Add discovery-focused system guidance
        discovery_system_guidance = """

IMPORTANT SALES APPROACH:
You are a friendly, knowledgeable B2B sales consultant having a natural conversation with a potential customer. Be human, conversational, and genuinely helpful.

CONVERSATION STYLE:
- Be warm and approachable, not robotic or scripted
- Use natural language and conversational tone
- Show genuine interest in their business and challenges
- Ask questions naturally as part of the conversation, not as a checklist
- Be helpful and informative while gathering information
- Use humor and personality when appropriate

DISCOVERY APPROACH (NATURAL):
- Learn about their business and challenges through natural conversation
- Ask follow-up questions that flow naturally from what they share
- Don't interrogate them with a list of questions
- Share relevant insights and information as you learn about their needs
- Build rapport and trust through helpful, knowledgeable responses

WHEN TO RECOMMEND PRODUCTS:
- When you have a good understanding of their needs and they ask for suggestions
- When you can provide genuinely helpful recommendations based on what they've shared
- When the conversation naturally leads to solution discussion

Remember: You're having a conversation with a real person, not following a sales script. Be helpful, be human, and let the conversation flow naturally."""

        system_prompt = discovery_system_guidance + system_prompt
        
        # Get conversational configuration
        config = self.prompt_manager.get_conversational_config()
        
        # Add personality context if available
        if config.get("personality"):
            personality = config["personality"]
            name = personality.get("name", "Alex")
            role = personality.get("role", "B2B Sales Consultant")
            traits = ", ".join(personality.get("personality_traits", []))
            communication_style = personality.get("communication_style", "conversational")
            tone = personality.get("tone", "warm_and_professional")
            
            personality_context = f"""
Agent Identity:
- Name: {name}
- Role: {role}
- Personality: {traits}
- Communication Style: {communication_style}
- Tone: {tone}

"""
            system_prompt = personality_context + system_prompt
        
        # Add industry-specific context if available
        if customer_context and customer_context.get('industry'):
            industry_context = self._get_industry_context(customer_context['industry'], config)
            if industry_context:
                system_prompt += industry_context
        
        # Add customer context if available
        if customer_context:
            customer_info = f"""
Customer Context:
- Company: {customer_context.get('company_name', 'Unknown')}
- Industry: {customer_context.get('industry', 'Business')}
- Contact: {customer_context.get('contact_name', 'Customer')}
- Company Size: {customer_context.get('company_size', 'Unknown')}
- Budget Range: {customer_context.get('budget_range', 'Unknown')}
- Timeline: {customer_context.get('timeline', 'Unknown')}
"""
            system_prompt += customer_info
        
        # Add response guidelines if available
        if config.get("response_guidelines"):
            guidelines_context = self._get_response_guidelines_context(config["response_guidelines"])
            system_prompt += guidelines_context
        
        # Create system message
        system_message = AIMessage(role="system", content=system_prompt)
        
        # Return enhanced messages
        return [system_message] + messages
    
    def _get_industry_context(self, industry: str, config: Dict[str, Any]) -> str:
        """Get industry-specific context from configuration"""
        industry_responses = config.get("industry_responses", {})
        
        if industry and industry.lower() in industry_responses:
            industry_config = industry_responses[industry.lower()]
            focus_areas = ", ".join(industry_config.get("focus_areas", []))
            concerns = ", ".join(industry_config.get("common_concerns", []))
            
            return f"""
Industry Context ({industry}):
- Focus areas: {focus_areas}
- Common concerns: {concerns}
- Tailor your responses to address these industry-specific needs and concerns.
"""
        return ""
    
    def _get_response_guidelines_context(self, response_guidelines: Dict[str, Any]) -> str:
        """Get response guidelines context"""
        guidelines_text = """

How to handle different types of requests:

"""
        
        for request_type, guidance in response_guidelines.items():
            approach = guidance.get("approach", "natural_help")
            elements = guidance.get("key_elements", [])
            
            guidelines_text += f"""
{request_type.replace('_', ' ').title()}:
- Approach: {approach.replace('_', ' ').title()}
- Key elements: {', '.join(elements)}
"""
        
        guidelines_text += """
Remember: You're having a conversation with a real person, not following a rigid sales script. Be human, be helpful, and let the conversation flow naturally. Adapt your response style based on the customer's tone and the type of question they're asking."""
        
        return guidelines_text
    
    async def generate_quote(self, quote_request: Dict[str, Any], current_user: Optional[Any] = None) -> Dict[str, Any]:
        """Generate a detailed quote using the QuoteGenerationAgent with PDF and pitch deck"""
        
        print("💰 SimpleConversationalAgent: Generating quote using QuoteGenerationAgent...")
        
        try:
            # Extract conversation messages and customer context
            conversation_messages = quote_request.get('conversation_messages', [])
            customer_context = quote_request.get('customer_context', {})
            
            # If no conversation messages provided, create a basic one from the request
            if not conversation_messages:
                requirements = quote_request.get('requirements', {})
                customer_info = quote_request.get('customer_info', {})
                
                # Create a basic conversation message from the requirements
                basic_message = f"Customer needs: {requirements.get('description', 'Business technology solution')}"
                if customer_info.get('company_name'):
                    basic_message += f" for {customer_info['company_name']}"
                if customer_info.get('industry'):
                    basic_message += f" in {customer_info['industry']} industry"
                
                conversation_messages = [AIMessage(role="user", content=basic_message)]
            
            # Use the QuoteGenerationAgent to generate the quote
            quote = await self.quote_agent.generate_quote_from_conversation(
                conversation_messages=conversation_messages,
                customer_context=customer_context,
                current_user=current_user  # Pass the current user
            )
            
            if quote:
                # Generate pitch deck for the quote
                await self._generate_pitch_deck_for_quote(quote)
                
                # Add metadata to indicate it was generated through SimpleConversationalAgent
                quote['generated_by'] = 'SimpleConversationalAgent_with_QuoteGenerationAgent'
                quote['hybrid_retriever_available'] = self.hybrid_retriever is not None
                print(f"✅ Quote generated successfully: {quote.get('quote_number', 'Unknown')}")
                print(f"   PDF generated: {quote.get('pdf_generated', False)}")
                print(f"   Pitch deck generated: {quote.get('pitch_deck_generated', False)}")
                
                # Record successful quote generation
                self.metrics_service.record_quote_generation(status="success")
                
                return quote
            else:
                print("❌ Quote generation failed - no quote returned")
                
                # Record failed quote generation
                self.metrics_service.record_quote_generation(status="failed")
                
                return {
                    'error': 'Quote generation failed - no quote returned',
                    'quote_id': f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'generated_at': datetime.now().isoformat(),
                    'quote_text': 'Quote generation failed - no quote returned'
                }
            
        except Exception as e:
            print(f"❌ Quote generation failed: {e}")
            
            # Record failed quote generation
            self.metrics_service.record_quote_generation(status="failed")
            
            return {
                'error': str(e),
                'quote_id': f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'generated_at': datetime.now().isoformat(),
                'quote_text': f"Quote generation failed: {str(e)}"
            }
    
    async def _generate_pitch_deck_for_quote(self, quote: Dict[str, Any]) -> None:
        """Generate pitch deck for the quote"""
        try:
            print("📊 Generating pitch deck for quote...")
            print(f"🔍 Debug - Input quote type: {type(quote)}")
            print(f"🔍 Debug - Input quote keys: {list(quote.keys()) if quote else 'None'}")
            
            # Import pitch deck service
            from services.pitch_deck_service import PitchDeckService
            print("🔍 Debug - PitchDeckService imported successfully")
            
            # Initialize pitch deck service
            pitch_deck_service = PitchDeckService()
            print("🔍 Debug - PitchDeckService initialized")
            
            # Get quote ID
            quote_id = quote.get('quote_id', 'unknown')
            print(f"🔍 Debug - Quote ID: {quote_id}")
            
            # Convert quote to string for processing
            quote_str = str(quote)
            print(f"🔍 Debug - Quote string length: {len(quote_str)}")
            print(f"🔍 Debug - Quote string preview: {quote_str[:200]}...")
            
            # Generate the pitch deck structure
            print("🔍 Debug - Calling extract_ppt_structure...")
            deck_structure = await pitch_deck_service.extract_ppt_structure(quote_str)
            print(f"🔍 Debug - Deck structure type: {type(deck_structure)}")
            print(f"🔍 Debug - Deck structure keys: {list(deck_structure.keys()) if isinstance(deck_structure, dict) else 'Not a dict'}")
            
            # Generate the pitch deck file
            deck_path = f"Data/pitch_decks/pitch_deck_{quote_id}.pptx"
            print(f"🔍 Debug - Target deck path: {deck_path}")
            
            # Ensure the directory exists
            import os
            pitch_deck_dir = "Data/pitch_decks"
            if not os.path.exists(pitch_deck_dir):
                print(f"🔍 Debug - Creating directory: {pitch_deck_dir}")
                os.makedirs(pitch_deck_dir, exist_ok=True)
            else:
                print(f"🔍 Debug - Directory already exists: {pitch_deck_dir}")
            
            print("🔍 Debug - Calling generate_ppt...")
            file_path = await pitch_deck_service.generate_ppt(deck_structure, deck_path)
            print(f"🔍 Debug - generate_ppt returned: {file_path}")
            print(f"🔍 Debug - File path type: {type(file_path)}")
            
            # Check if file was actually created
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"🔍 Debug - File created successfully: {file_path}")
                print(f"🔍 Debug - File size: {file_size} bytes")
                
                # Add pitch deck information to quote
                quote['pitch_deck_generated'] = True
                quote['pitch_deck_path'] = file_path
                quote['pitch_deck_url'] = f"/api/quotes/download-pitch-deck/{quote_id}"
                quote['pitch_deck_id'] = quote_id
                print(f"✅ Pitch deck generated successfully: {file_path}")
                print(f"🔍 Debug - Updated quote with pitch deck info")
            else:
                print("⚠️ Pitch deck generation returned no path or file doesn't exist")
                if file_path:
                    print(f"🔍 Debug - Returned path: {file_path}")
                    print(f"🔍 Debug - File exists: {os.path.exists(file_path)}")
                quote['pitch_deck_error'] = "Pitch deck generation failed - no path returned or file not created"
                quote['pitch_deck_generated'] = False
                
        except ImportError as e:
            print(f"❌ Debug - Import error: {str(e)}")
            quote['pitch_deck_error'] = f"Import error: {str(e)}"
            quote['pitch_deck_generated'] = False
            
        except Exception as e:
            print(f"❌ Pitch deck generation failed: {str(e)}")
            import traceback
            print(f"❌ Debug - Full traceback: {traceback.format_exc()}")
            quote['pitch_deck_error'] = f"Pitch deck generation error: {str(e)}"
            quote['pitch_deck_generated'] = False 