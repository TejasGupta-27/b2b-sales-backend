import json
import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from io import BytesIO
import logging
import langdetect
from pydantic import BaseModel, Field

from .base import AIProvider, AIMessage, AIResponse
from services.prompt_manager import get_prompt_manager
from .hybrid_product_retriever_agent import HybridProductRetrieverAgent
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

    def __init__(self, base_provider: AIProvider, language: str = "en", **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.language = language
        self.conversation_memory = {}
        self.prompt_manager = get_prompt_manager()
        print(f"🌐 SimpleConversationalAgent initialized with language: {self.language}")
        
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
                    azure_embedding_key=settings.azure_embedding_api_key,
                    language="en"  # Always English for search
                )
                print("✅ Hybrid Product Retriever initialized for SimpleConversationalAgent")
            except Exception as e:
                print(f"⚠️ Failed to initialize hybrid retriever: {e}")

        # Quote generation agent uses user language
        self.quote_agent = QuoteGenerationAgent(base_provider, language)
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
    
    async def detect_and_switch_language(self, messages: List[AIMessage]) -> None:
        """Detect the language of the latest user message and switch response language dynamically."""
        try:
            # Extract the latest user message
            latest_message = next((msg.content for msg in reversed(messages) if msg.role == "user"), None)
            if not latest_message:
                return

            # Use centralized language_service for detection
            from services.language_service import LanguageService
            language_service = LanguageService()
            detection_result = language_service.detect_language(latest_message)

            # Determine the detected language
            detected_language = detection_result.get("primary_language", self.language)
            if not detected_language or detected_language == self.language:
                return  # No change needed

            # Log language switching
            print(f"🌐 Switching language from {self.language} to {detected_language}")
            self.language = detected_language

            # Update dependent components efficiently
            for component in [self.quote_agent, self.hybrid_retriever]:
                if component:
                    component.language = detected_language

        except Exception as e:
            print(f"⚠️ Language detection failed: {e}")

    async def generate_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate intelligent responses with product retrieval and quote generation capabilities"""

        print("🤖 SimpleConversationalAgent: Analyzing conversation intent...")

        # Step 1: Detect and switch language dynamically
        await self.detect_and_switch_language(messages)

        # Step 2: Analyze conversation intent using Pydantic function calling
        intent_analysis = await self._analyze_conversation_intent(messages, customer_context)

        print(f"🎯 Intent Analysis:")
        print(f"   Intent: {intent_analysis.intent_type}")
        print(f"   Retrieve Products: {intent_analysis.should_retrieve_products}")
        print(f"   Generate Quote: {intent_analysis.should_generate_quote}")
        print(f"   Confidence: {intent_analysis.confidence:.1%}")
        print(f"   Reasoning: {intent_analysis.reasoning}")

        # Step 3: Retrieve products if needed
        product_data = None
        similar_products = []
        if intent_analysis.should_retrieve_products and self.hybrid_retriever:
            print("🔍 Retrieving products using LLM-enhanced hybrid search...")
            try:
                # Use the enhanced LLM-powered context analysis
                product_data = await self.hybrid_retriever.retrieve_products(messages, customer_context)
                print(f"✅ Retrieved {len(product_data.get('products', []))} products, {len(product_data.get('solutions', []))} solutions")
                print(f"   LLM Context: {product_data.get('requirements', {}).get('llm_context', {}).get('primary_need', 'Unknown')}")
                print(f"   Similar Products Analysis: {product_data.get('similar_products_analysis', False)}")
                if product_data and 'requirements' in product_data:
                    similar_products = product_data['requirements'].get('similar_products', [])
                similar_products = similar_products[:5]

                # Add fallback similar products if none found
                if not similar_products:
                    print("⚠️  No similar products found, using fallback products...")
                    if self.language == "ja":
                        similar_products = [
                            {
                                'name': 'Dell OptiPlex 7000',
                                'description': 'Intel Core i7プロセッサーとエンタープライズセキュリティ機能を搭載したビジネスデスクトップコンピュータ',
                                'price': 180000,
                                'vendor': 'Dell',
                                'brand': 'Dell'
                            },
                            {
                                'name': 'HP EliteDesk 800 G9',
                                'description': '高性能と省エネルギーを兼ね備えたコンパクトビジネスPC',
                                'price': 202500,
                                'vendor': 'HP',
                                'brand': 'HP'
                            },
                            {
                                'name': 'Lenovo ThinkCentre M90n',
                                'description': '信頼性の高いパフォーマンスを提供する超小型ビジネスコンピュータ',
                                'price': 165000,
                                'vendor': 'Lenovo',
                                'brand': 'Lenovo'
                            }
                        ]
                    else:
                        similar_products = [
                            {
                                'name': 'Dell OptiPlex 7000',
                                'description': 'Business desktop computer with Intel Core i7 processor and enterprise security features',
                                'price': 1200,
                                'vendor': 'Dell',
                                'brand': 'Dell'
                            },
                            {
                                'name': 'HP EliteDesk 800 G9',
                                'description': 'Compact business PC with high performance and energy efficiency',
                                'price': 1350,
                                'vendor': 'HP',
                                'brand': 'HP'
                            },
                            {
                                'name': 'Lenovo ThinkCentre M90n',
                                'description': 'Ultra-small form factor business computer with reliable performance',
                                'price': 1100,
                                'vendor': 'Lenovo',
                                'brand': 'Lenovo'
                            }
                        ]
                    print(f"✅ Added {len(similar_products)} fallback similar products")

            except Exception as e:
                print(f"❌ Product retrieval failed: {e}")
                # Even on failure, provide some fallback products
                if self.language == "ja":
                    similar_products = [
                        {
                            'name': 'ビジネスワークステーションPro',
                            'description': 'プロフェッショナル機能を搭載した高性能ビジネスワークステーション',
                            'price': 375000,
                            'vendor': 'ジェネリック',
                            'brand': 'プロフェッショナル'
                        },
                        {
                            'name': 'エンタープライズサーバーソリューション',
                            'description': 'エンタープライズ環境向けのスケーラブルサーバーソリューション',
                            'price': 525000,
                            'vendor': 'ジェネリック',
                            'brand': 'エンタープライズ'
                        }
                    ]
                else:
                    similar_products = [
                        {
                            'name': 'Business Workstation Pro',
                            'description': 'High-performance business workstation with professional features',
                            'price': 2500,
                            'vendor': 'Generic',
                            'brand': 'Professional'
                        },
                        {
                            'name': 'Enterprise Server Solution',
                            'description': 'Scalable server solution for enterprise environments',
                            'price': 3500,
                            'vendor': 'Generic',
                            'brand': 'Enterprise'
                        }
                    ]
                print(f"✅ Added {len(similar_products)} emergency fallback products")
            except Exception as e:
                print(f"⚠️ Product retrieval failed: {e}")
                product_data = {'products': [], 'solutions': [], 'error': str(e)}
        
        # Step 4: Generate appropriate response based on intent
        if intent_analysis.should_generate_quote:
            response = await self._generate_quote_response(messages, customer_context, product_data, intent_analysis)
        elif intent_analysis.should_retrieve_products and product_data:
            response = await self._generate_product_response(messages, customer_context, product_data, intent_analysis)
        else:
            response = await self._generate_general_response(messages, customer_context, intent_analysis)
        
        # Step 5: Add metadata
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
        intent_analysis: ConversationIntent
    ) -> AIResponse:
        """Generate quote response with focus on gathering missing information first"""
        
        print("💰 Generating quote response...")
        
        # Get quote-specific guidance from prompt manager
        quote_guidance = self.prompt_manager.get_prompt("conversational_agent", "quote_guidance", self.language)
        
        if not quote_guidance:
            if self.language == "ja":
                quote_guidance = """お客様が見積もりを求めていらっしゃいます。自然で会話的な方法で、お客様が必要なものを得られるよう支援してください。

アプローチ：
- 見積もりの依頼を温かく承認する
- 正確な見積もりに必要な情報がすべて揃っているか確認する
- 詳細が必要な場合は、自然にお尋ねする
- 十分な情報がある場合は、要約と次のステップを提供する
- 押しつけがましくなく、役立つ専門的な対応

例：
- "完璧です！私たちが話し合ったPCビルドの見積もりを作成いたしました..."
- "素晴らしいです！あなたのセットアップに対して作成したものをこちらです..."
- "すばらしいです！価格の準備ができました..."

忘れないでください：あなたは正式なビジネス文書を送付しているのではなく、会話をしているのです。自然で役立つ対応を心がけてください。"""
            else:
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
            if self.language == "ja":
                missing_info_context = """
注意：会話が進む中でお客様のニーズについてさらに詳しく伺うことをご検討いただいても構いませんが、尋問のように感じさせないでください。自然に興味を持ち、役立つ対応を心がけてください。
"""
            else:
                missing_info_context = """
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
                    'product_data': product_data  # Pass product_data to quote generation
                })
                
                if quote and not quote.get('error'):
                    # Enhance response with quote information
                    response = self._enhance_response_with_quote_info(response, quote)
                    
                    # Update metadata with quote information
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
                response.metadata['quote_generation_error'] = str(e)
        else:
            print(f"⚠️ Not generating quote yet - missing info: {intent_analysis.missing_info}")
            response.metadata['requirements_complete'] = False
        
        return response
    
    def _enhance_response_with_quote_info(self, response: AIResponse, quote: Dict[str, Any]) -> AIResponse:
        """Enhance response with quote information including PDF and pitch deck - using hybrid language detection."""
        original_content = response.content.strip()
        quote_language = quote.get('language', self.language)

        if hasattr(self, 'quote_agent') and self.quote_agent:
            if self.quote_agent.language != quote_language:
                self.quote_agent.language = quote_language

            quote_formatted_response = self.quote_agent.format_quote_response(quote, quote_language)
            if any(keyword in original_content.lower() for keyword in ['quote', 'price', 'cost', 'total', 'pricing', '見積', '価格', '金額']):
                response.content += f"\n\n{quote_formatted_response}"
            else:
                intro_text = {
                    'ja': "完璧です！ディスカッションに基づいて詳細な見積もりを作成いたしました。",
                    'en': "Perfect! I've put together a detailed quote based on our discussion.",
                    'es': "¡Perfecto! He preparado una cotización detallada basada en nuestra discusión.",
                    'fr': "Parfait! J'ai préparé un devis détaillé basé sur notre discussion.",
                    'de': "Perfekt! Ich habe ein detailliertes Angebot basierend auf unserer Diskussion erstellt."
                }.get(quote_language, "Perfect! I've put together a detailed quote based on our discussion.")
                self.quote_agent.language = quote_language
            
            quote_formatted_response = self.quote_agent.format_quote_response(quote, quote_language)
            
            # If the response is already conversational and mentions the quote, enhance it naturally
            quote_keywords = ['quote', 'price', 'cost', 'total', 'pricing'] + (['見積', '価格', '金額'] if quote_language == 'ja' else [])
            
            if any(keyword in original_content.lower() for keyword in quote_keywords):
                # The LLM already handled the quote conversation naturally, just add the technical details
                response.content += "\n\n" + quote_formatted_response
            else:
                # The LLM didn't mention the quote, so provide a more conversational introduction
                intro_text = {
                    'ja': "完璧です！ディスカッションに基づいて詳細な見積もりを作成いたしました。",
                    'en': "Perfect! I've put together a detailed quote based on our discussion.",
                    'es': "¡Perfecto! He preparado una cotización detallada basada en nuestra discusión.",
                    'fr': "Parfait! J'ai préparé un devis détaillé basé sur notre discussion.",
                    'de': "Perfekt! Ich habe ein detailliertes Angebot basierend auf unserer Diskussion erstellt."
                }.get(quote_language, "Perfect! I've put together a detailed quote based on our discussion.")
                
                response.content += f"\n\n{intro_text}"
                response.content += "\n\n" + quote_formatted_response
        else:
            # Fallback logic with proper language support
            logger.warning("⚠️ Quote agent not available for formatting, using fallback with hybrid language support")
            
            # Use localized labels based on resolved language
            from services.localisation import get_translation
            t = get_translation("quote_prompt", quote_language)
            labels = t["pdf_labels"]
            
            # Build response in resolved language
            if any(keyword in original_content.lower() for keyword in ['quote', 'price', 'cost', 'total', 'pricing', '見積', '価格', '金額']):
                response.content += f"\n\n📋 **{labels['quote_details']}**"
                response.content += f"\n• {labels['quote_number']}: {quote.get('quote_number', 'N/A')}"
                
                # Add pricing summary with proper currency handling
                if 'financials' in quote:
                    financials = quote['financials']
                    currency_symbol = "¥" if quote_language == "ja" else "$"
                    response.content += f"\n• {labels['subtotal']}: {currency_symbol}{financials['subtotal']:,.2f}"
                    response.content += f"\n• {labels['tax']}: {currency_symbol}{financials['tax_amount']:,.2f}"
                    response.content += f"\n• **{labels['total_amount']}: {currency_symbol}{financials['total']:,.2f}**"
                
                # Add download links with localized text
                if quote.get('pdf_generated', False) and quote.get('pdf_url'):
                    pdf_text = {
                        'ja': "📄 **[見積もりPDFをダウンロード]({url})**",
                        'en': "📄 **[Download Complete Quote PDF]({url})**",
                        'es': "📄 **[Descargar PDF de Cotización Completa]({url})**",
                        'fr': "📄 **[Télécharger le PDF du Devis Complet]({url})**",
                        'de': "📄 **[Vollständiges Angebot PDF herunterladen]({url})**"
                    }.get(quote_language, "📄 **[Download Complete Quote PDF]({url})**")
                    
                    response.content += f"\n\n{pdf_text.format(url=quote['pdf_url'])}"
        
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
        if self.language == "ja":
            discovery_guidance = """お客様との自然な会話を行っています。役立ち、情報を提供し、お客様のニーズに真の関心を示してください。

アプローチ：
- 会話的で温かく
- お客様について学ぶ過程で関連する洞察や情報を共有する
- 会話から自然に派生するフォローアップ質問をする
- 情報を収集するだけでなく、役立つ情報提供者になる
- お客様のビジネスや課題を理解していることを示す
- 知識のある役立つ対応で信頼関係を構築する

忘れないでください：あなたは会話をしている知識のあるコンサルタントであり、営業ロボットではありません。人間らしく、役立つ存在になってください。"""
        else:
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
            if self.language == "ja":
                questions_context = f"""
会話が自然に流れる中で、これらのトピックを探求することに興味を持たれるかもしれません：
{chr(10).join([f"- {question}" for question in intent_analysis.suggested_questions])}

ただし、これらすべてを質問する義務を感じる必要はありません - 会話を自然に流れさせてください。
"""
            else:
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
        
        if products:
            context += "Top Products:\n"
            for i, product in enumerate(products[:5]):  # Top 5 products
                price = product.get('price', 0)
                price_str = f"${price:,.2f}" if price is not None else "Price on request"
                context += f"{i+1}. {product.get('name', 'Unknown')} - {price_str}\n"
                context += f"   Category: {product.get('category', 'Unknown')}\n"
                context += f"   Description: {product.get('description', 'No description')[:100]}...\n"
                # Add LLM insights if available
                if product.get('search_source') == 'both':
                    context += f"   Match Quality: High (found in both keyword and semantic search)\n"
                elif product.get('rrf_score', 0) > 0.02:
                    context += f"   Match Quality: Strong (RRF score: {product.get('rrf_score', 0):.3f})\n"
                context += "\n"
        
        if solutions:
            context += "Available Solutions:\n"
            for i, solution in enumerate(solutions[:3]):  # Top 3 solutions
                context += f"{i+1}. {solution.get('name', 'Unknown')}\n"
                context += f"   Use Case: {solution.get('use_case', 'No use case')}\n"
                context += f"   Total Price: ${solution.get('total_price', 0):,.2f}\n\n"
        
        # Add similar products analysis if available
        similar_products = requirements.get('similar_products', [])
        if similar_products:
            context += f"Similar Products Analysis:\n"
            for product in similar_products[:3]:
                context += f"- {product}\n"
            context += "\n"
        
        for cat, plist in cat_map.items():
            context += f"\n{cat.title()}:\n"
            for i, p in enumerate(plist[:2]):  # Top 2 per category
                context += f"  {i+1}. {p.get('name', 'Unknown')} (${p.get('price', 'N/A')})\n"
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

        # Use language for system prompt
        system_prompt = self.prompt_manager.get_system_prompt("conversational_agent", language=self.language)

        # Add language-specific instruction FIRST and make it prominent
        if self.language == "ja":
            language_instruction = "\n\n【重要】必ず日本語で回答してください。お客様とのコミュニケーションは常に日本語で自然に行い、親しみやすく丁寧な対応を心がけてください。すべての返答は日本語で行う必要があります。"
        else:
            language_instruction = "\n\nIMPORTANT: Always respond in English. Maintain a natural, friendly, and professional tone in all communications."
        
        system_prompt = system_prompt + language_instruction

        # Add discovery-focused system guidance (localized)
        if self.language == "ja":
            discovery_system_guidance = """

重要な営業アプローチ：
あなたは親しみやすく知識豊富なB2B営業コンサルタントとして、お客様と自然な会話を行ってください。人間らしく、会話的で、本当に役に立つ存在になってください。

会話スタイル：
- 温かく親しみやすく、ロボット的でなく型にはまらない対応
- 自然な言葉遣いと会話的なトーン
- お客様のビジネスや課題に真の関心を示す
- チェックリストではなく、会話の流れで自然に質問する
- 情報を収集しながら役立つ情報提供
- 適切な場面でユーモアと個性を発揮

ディスカバリーアプローチ（自然な方法）：
- 自然な会話を通じてお客様のビジネスや課題について学ぶ
- お客様が共有してくださった内容から自然に派生するフォローアップ質問
- 質問の羅列で尋問しない
- お客様のニーズを理解する過程で関連する洞察や情報を共有
- 役立つ知識のある対応で信頼関係とつながりを構築

製品を推奨するタイミング：
- お客様のニーズをよく理解し、お客様が提案を求めてくださった時
- お客様が共有してくださった内容に基づいて、本当に役立つ推奨ができる時
- 会話が自然にソリューションの議論へと向かった時

忘れないでください：あなたは実在の人との会話をしているのであり、営業台本に従っているのではありません。役に立ち、人間らしく、会話を自然に流れさせてください。"""
        else:
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
    
    async def generate_quote(self, quote_request: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a detailed quote using the QuoteGenerationAgent with PDF and pitch deck"""
        
        print("💰 SimpleConversationalAgent: Generating quote using QuoteGenerationAgent...")
        
        try:
            # Extract conversation messages and customer context
            conversation_messages = quote_request.get('conversation_messages', [])
            customer_context = quote_request.get('customer_context', {})
            product_data = quote_request.get('product_data')  # Extract product_data
            
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
                customer_context=customer_context
            )
            
            if quote:
                # Generate pitch deck for the quote with product data
                await self._generate_pitch_deck_for_quote(quote, product_data)
                
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
    
    async def _generate_pitch_deck_for_quote(self, quote: Dict[str, Any], product_data: Optional[Dict[str, Any]] = None) -> None:
        """Generate pitch deck for the quote, using similar products from hybrid retriever for comparison table"""
        try:
            from services.pitch_deck_service import PitchDeckService
            pitch_deck_service = PitchDeckService()
            quote_id = quote.get('quote_id', 'unknown')
            quote_str = str(quote)

            # Extract similar products from product_data with robust fallback
            similar_products = []
            
            # First, try to get products from product_data
            if product_data and 'requirements' in product_data:
                similar_names = product_data['requirements'].get('similar_products', [])[:3]  # Limit to 3
                all_products = product_data.get('products', [])
                
                print(f"🔍 Debug - Looking for similar products: {similar_names}")
                print(f"🔍 Debug - Available products count: {len(all_products)}")
                
                # Match similar product names to full product objects
                for name in similar_names:
                    # Try exact name match first
                    match = next((p for p in all_products if p.get('name', '').lower() == name.lower()), None)
                    if not match:
                        # Try ID match
                        match = next((p for p in all_products if str(p.get('id', '')).lower() == str(name).lower()), None)
                    if not match:
                        # Try partial name match
                        match = next((p for p in all_products if name.lower() in p.get('name', '').lower()), None)
                    
                    if match:
                        similar_products.append(match)
                        print(f"✅ Found match for '{name}': {match.get('name', 'Unknown')}")
                    else:
                        # Create a minimal product entry if no match found
                        similar_products.append({
                            'name': name,
                            'description': 'Product details available upon request',
                            'price': 'Quote on request',
                            'vendor': 'Various'
                        })
                        print(f"⚠️ No match found for '{name}', created placeholder")

            # Debug information about product_data
            print(f"🔍 Debug - product_data type: {type(product_data)}")
            print(f"🔍 Debug - product_data is None: {product_data is None}")
            if product_data:
                print(f"🔍 Debug - product_data keys: {list(product_data.keys())}")
                if 'requirements' in product_data:
                    print(f"🔍 Debug - requirements keys: {list(product_data['requirements'].keys())}")

            # If no similar products found, create fallback products based on quote content
            if not similar_products:
                print("⚠️ No similar products from product_data, creating fallback products...")
                
                # Analyze quote content to determine appropriate fallback products
                quote_content = quote_str.lower()
                print(f"🔍 Debug - Analyzing quote content for keywords: {quote_content[:200]}...")
                
                if any(keyword in quote_content for keyword in ['rtx', 'gpu', 'graphics', 'gaming']):
                    print("🎯 Creating GPU/Gaming fallback products")
                    if self.language == "ja":
                        similar_products = [
                            {
                                'name': 'NVIDIA RTX 4080',
                                'description': '16GB GDDR6Xメモリ搭載の高性能グラフィックスカード',
                                'price': '¥179,850',
                                'vendor': 'NVIDIA'
                            },
                            {
                                'name': 'AMD Radeon RX 7900 XTX',
                                'description': '24GB GDDR6を搭載した強力なゲーミングおよびコンテンツ制作用GPU',
                                'price': '¥149,850',
                                'vendor': 'AMD'
                            },
                            {
                                'name': 'NVIDIA RTX 4060 Ti',
                                'description': '優れたコストパフォーマンスを持つミッドレンジゲーミングGPU',
                                'price': '¥59,850',
                                'vendor': 'NVIDIA'
                            }
                        ]
                    else:
                        similar_products = [
                            {
                                'name': 'NVIDIA RTX 4080',
                                'description': 'High-performance graphics card with 16GB GDDR6X memory',
                                'price': '$1,199',
                                'vendor': 'NVIDIA'
                            },
                            {
                                'name': 'AMD Radeon RX 7900 XTX',
                                'description': 'Powerful gaming and content creation GPU with 24GB GDDR6',
                                'price': '$999',
                                'vendor': 'AMD'
                            },
                            {
                                'name': 'NVIDIA RTX 4060 Ti',
                                'description': 'Mid-range gaming GPU with excellent price-performance ratio',
                                'price': '$399',
                                'vendor': 'NVIDIA'
                            }
                        ]
                elif any(keyword in quote_content for keyword in ['workstation', 'laptop', 'computer', 'pc']):
                    print("🎯 Creating Workstation/Computer fallback products")
                    if self.language == "ja":
                        similar_products = [
                            {
                                'name': 'Dell Precision 7670',
                                'description': 'Intel Core i7プロセッサーとプロフェッショナルグラフィックスを搭載したモバイルワークステーション',
                                'price': '¥420,000',
                                'vendor': 'Dell'
                            },
                            {
                                'name': 'HP ZBook Studio G9',
                                'description': '高性能GPUを搭載したプロフェッショナルワークステーションラップトップ',
                                'price': '¥397,500',
                                'vendor': 'HP'
                            },
                            {
                                'name': 'Lenovo ThinkPad P1 Gen 5',
                                'description': 'Intel vPro技術を搭載した超軽量ワークステーション',
                                'price': '¥412,500',
                                'vendor': 'Lenovo'
                            }
                        ]
                    else:
                        similar_products = [
                            {
                                'name': 'Dell Precision 7670',
                                'description': 'Mobile workstation with Intel Core i7 processor and professional graphics',
                                'price': '$2,800',
                                'vendor': 'Dell'
                            },
                            {
                                'name': 'HP ZBook Studio G9',
                                'description': 'Professional workstation laptop with high-performance GPU',
                                'price': '$2,650',
                                'vendor': 'HP'
                            },
                            {
                                'name': 'Lenovo ThinkPad P1 Gen 5',
                                'description': 'Ultra-portable workstation with Intel vPro technology',
                                'price': '$2,750',
                                'vendor': 'Lenovo'
                            }
                        ]
                elif any(keyword in quote_content for keyword in ['memory', 'ram', 'ddr']):
                    print("🎯 Creating Memory/RAM fallback products")
                    if self.language == "ja":
                        similar_products = [
                            {
                                'name': 'Corsair Vengeance LPX 32GB',
                                'description': 'ゲーミング用に最適化された高性能DDR4メモリキット',
                                'price': '¥19,350',
                                'vendor': 'Corsair'
                            },
                            {
                                'name': 'Kingston Fury Beast 32GB',
                                'description': '優れた互換性を持つ信頼性の高いDDR4メモリ',
                                'price': '¥17,850',
                                'vendor': 'Kingston'
                            },
                            {
                                'name': 'G.Skill Trident Z5 32GB',
                                'description': 'RGBライティング付きプレミアムDDR5メモリ',
                                'price': '¥29,850',
                                'vendor': 'G.Skill'
                            }
                        ]
                    else:
                        similar_products = [
                            {
                                'name': 'Corsair Vengeance LPX 32GB',
                                'description': 'High-performance DDR4 memory kit optimized for gaming',
                                'price': '$129',
                                'vendor': 'Corsair'
                            },
                            {
                                'name': 'Kingston Fury Beast 32GB',
                                'description': 'Reliable DDR4 memory with excellent compatibility',
                                'price': '$119',
                                'vendor': 'Kingston'
                            },
                            {
                                'name': 'G.Skill Trident Z5 32GB',
                                'description': 'Premium DDR5 memory with RGB lighting',
                                'price': '$199',
                                'vendor': 'G.Skill'
                            }
                        ]
                else:
                    print("🎯 Creating Generic business technology fallback products")
                    # Generic business technology products
                    if self.language == "ja":
                        similar_products = [
                            {
                                'name': 'ビジネスソリューションPro',
                                'description': 'エンタープライズサポート付きの包括的なビジネステクノロジーソリューション',
                                'price': '価格についてはお問い合わせください',
                                'vendor': 'エンタープライズ'
                            },
                            {
                                'name': 'プロフェッショナルワークステーション',
                                'description': 'プロフェッショナルアプリケーション用の高性能ワークステーション',
                                'price': '見積もりご要望',
                                'vendor': 'プロフェッショナル'
                            },
                            {
                                'name': 'エンタープライズサーバー',
                                'description': 'エンタープライズ環境向けのスケーラブルサーバーソリューション',
                                'price': 'カスタム価格',
                                'vendor': 'エンタープライズ'
                            }
                        ]
                    else:
                        similar_products = [
                            {
                                'name': 'Business Solution Pro',
                                'description': 'Comprehensive business technology solution with enterprise support',
                                'price': 'Contact for pricing',
                                'vendor': 'Enterprise'
                            },
                            {
                                'name': 'Professional Workstation',
                                'description': 'High-performance workstation for professional applications',
                                'price': 'Quote on request',
                                'vendor': 'Professional'
                            },
                            {
                                'name': 'Enterprise Server',
                                'description': 'Scalable server solution for enterprise environments',
                                'price': 'Custom pricing',
                                'vendor': 'Enterprise'
                            }
                        ]
                
                print(f"✅ Created {len(similar_products)} fallback similar products")
            
            # Double-check that we have similar products - this should NEVER be empty
            if not similar_products:
                print("🚨 CRITICAL: Still no similar products! Creating emergency fallback...")
                if self.language == "ja":
                    similar_products = [
                        {
                            'name': 'テクノロジーソリューションA',
                            'description': 'エンタープライズサポート付きのプロフェッショナルテクノロジーソリューション',
                            'price': '見積もり対応',
                            'vendor': 'テクノロジーパートナー'
                        },
                        {
                            'name': 'テクノロジーソリューションB',
                            'description': '包括的な保証付きの先進的なビジネステクノロジー',
                            'price': '営業にお問い合わせください',
                            'vendor': 'ビジネスパートナー'
                        },
                        {
                            'name': 'テクノロジーソリューションC',
                            'description': '24/7サポート付きのエンタープライズグレードソリューション',
                            'price': 'カスタム価格',
                            'vendor': 'エンタープライズパートナー'
                        }
                    ]
                else:
                    similar_products = [
                        {
                            'name': 'Technology Solution A',
                            'description': 'Professional technology solution with enterprise support',
                            'price': 'Quote available',
                            'vendor': 'Technology Partner'
                        },
                        {
                            'name': 'Technology Solution B',
                            'description': 'Advanced business technology with comprehensive warranty',
                            'price': 'Contact sales',
                            'vendor': 'Business Partner'
                        },
                        {
                            'name': 'Technology Solution C',
                            'description': 'Enterprise-grade solution with 24/7 support',
                            'price': 'Custom pricing',
                            'vendor': 'Enterprise Partner'
                        }
                    ]
                print(f"🆘 Created {len(similar_products)} emergency fallback products")

            print(f"🔍 Debug - Final similar products count: {len(similar_products)}")

            # Generate the pitch deck structure WITHOUT comparison table from LLM
            deck_structure = await pitch_deck_service.extract_ppt_structure(quote_str, include_comparison_table=False)
            
            # Ensure deck_structure has the right format
            if "tables" not in deck_structure:
                deck_structure["tables"] = []
            
            # Don't add any additional tables here - let the pitch deck service handle similar products
            print(f"🔍 Debug - Deck structure has {len(deck_structure.get('slides', []))} slides")
            print(f"🔍 Debug - Deck structure has {len(deck_structure.get('tables', []))} existing tables")

            # Create deck path
            deck_path = f"Data/pitch_decks/pitch_deck_{quote_id}.pptx"
            import os
            pitch_deck_dir = "Data/pitch_decks"
            if not os.path.exists(pitch_deck_dir):
                os.makedirs(pitch_deck_dir, exist_ok=True)
            
            # Generate the presentation with similar products
            file_path = await pitch_deck_service.generate_ppt(
                deck_structure, 
                deck_path, 
                similar_products=similar_products
            )
            
            # Check if file was actually created
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"✅ Pitch deck generated successfully: {file_path}")
                print(f"🔍 Debug - File size: {file_size} bytes")
                print(f"🔍 Debug - Used {len(similar_products)} similar products for comparison")
                
                # Add pitch deck information to quote
                quote['pitch_deck_generated'] = True
                quote['pitch_deck_path'] = file_path
                quote['pitch_deck_url'] = f"/api/quotes/download-pitch-deck/{quote_id}"
                quote['pitch_deck_id'] = quote_id
                quote['similar_products_count'] = len(similar_products)
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

    async def competitor_analysis(self, messages: List[AIMessage], customer_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform competitor analysis based on customer requirements and context"""
        
        print("🔍 Analyzing competitors...")
        
        # Extract relevant information from the last message and customer context
        last_message = messages[-1].content if messages else ""
        requirements = customer_context.get('requirements', {})
        industry = customer_context.get('industry', '')
        
        # Build a prompt for competitor analysis
        analysis_prompt = f"""Analyze the following information to provide a competitor analysis.

CUSTOMER REQUIREMENTS:
{requirements}

LAST MESSAGE:
{last_message}

INDUSTRY CONTEXT:
{industry}

ANALYSIS:
- Identify potential competitors that offer similar products or solutions
- Compare key features, pricing, and value propositions
- Highlight any gaps or opportunities in the current market offering
- Provide a table comparing the top 3 competitors based on the analysis

COMPETITOR ANALYSIS TABLE FORMAT:
{
    "title": "Competitor Analysis",
    "columns": ["Product Name", "Key Features", "Price", "Vendor"],
    "rows": [
        # Fill using similar_products
        # Example: [product_name, features, price, vendor]
    ]
}

"""
        
        # Generate the competitor analysis response
        response = await self.base_provider.generate_response(
            [AIMessage(role="user", content=analysis_prompt)],
            temperature=0.7
        )
        
        return response.content if response and response.content else "No competitor analysis found."