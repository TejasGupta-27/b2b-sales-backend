from typing import List, Dict, Any, Optional, Set, Tuple, Union
from .base import AIProvider, AIMessage
import json
import re
import asyncio
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum
import logging
from collections import Counter
import difflib

logger = logging.getLogger(__name__)

class ResponseIntent(str, Enum):
    """Response intent categories"""
    # Discovery & Information
    DISCOVERY = "discovery"
    REQUIREMENTS = "requirements"
    USE_CASE = "use_case"
    
    # Commercial
    BUDGET = "budget" 
    PRICING = "pricing"
    QUOTE = "quote"
    
    # Product & Technical
    PRODUCT_INFO = "product_info"
    TECHNICAL = "technical"
    COMPARISON = "comparison"
    SPECIFICATIONS = "specifications"
    
    # Process
    TIMELINE = "timeline"
    IMPLEMENTATION = "implementation"
    SUPPORT = "support"
    
    # Social Proof
    SOCIAL_PROOF = "social_proof"
    CASE_STUDIES = "case_studies"
    
    # Next Steps
    NEXT_STEPS = "next_steps"
    DEMO = "demo"
    MEETING = "meeting"

class Priority(str, Enum):
    """Response priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class QuickResponse(BaseModel):
    """Simple quick response model"""
    text: str = Field(..., description="Response text")
    intent: ResponseIntent = Field(..., description="Response intent")
    priority: Priority = Field(default=Priority.MEDIUM, description="Response priority")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    context_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Context relevance")
    tags: Set[str] = Field(default_factory=set, description="Response tags")
    follow_up: Optional[str] = Field(None, description="Optional follow-up question")
    
    @property
    def overall_score(self) -> float:
        """Calculate overall response score"""
        priority_weights = {
            Priority.CRITICAL: 1.0,
            Priority.HIGH: 0.8,
            Priority.MEDIUM: 0.6,
            Priority.LOW: 0.4
        }
        
        return (
            self.confidence * 0.5 + 
            self.context_score * 0.3 + 
            priority_weights[self.priority] * 0.2
        )
    
    def is_similar_to(self, other: 'QuickResponse', threshold: float = 0.8) -> bool:
        """Check if this response is similar to another"""
        similarity = difflib.SequenceMatcher(None, self.text.lower(), other.text.lower()).ratio()
        return similarity >= threshold
    
    class Config:
        use_enum_values = True

class ConversationContext(BaseModel):
    """Conversation context analysis"""
    messages: List[AIMessage]
    customer_context: Optional[Dict[str, Any]] = None
    detected_intents: Set[ResponseIntent] = Field(default_factory=set)
    keywords: Set[str] = Field(default_factory=set)
    sentiment: str = Field(default="neutral")
    stage: str = Field(default="discovery")
    product_mentions: Set[str] = Field(default_factory=set)
    pain_points: List[str] = Field(default_factory=list)
    urgency_indicators: List[str] = Field(default_factory=list)
    last_customer_message: Optional[str] = None
    message_count: int = 0

class ResponseRule(BaseModel):
    """Rule for generating contextual responses"""
    name: str = Field(..., description="Rule name")
    keywords: Set[str] = Field(default_factory=set, description="Trigger keywords")
    intents: Set[ResponseIntent] = Field(default_factory=set, description="Target intents")
    sentiment: Optional[str] = Field(None, description="Required sentiment")
    stage: Optional[str] = Field(None, description="Required conversation stage")
    responses: List[Dict[str, Any]] = Field(..., description="Response templates")
    priority: Priority = Field(default=Priority.MEDIUM)
    
    def matches(self, context: ConversationContext) -> bool:
        """Check if rule matches current context"""
        # Check keywords
        if self.keywords:
            text_words = set(context.last_customer_message.lower().split() if context.last_customer_message else [])
            if not (self.keywords & text_words):
                return False
        
        # Check intents
        if self.intents and not (self.intents & context.detected_intents):
            return False
        
        # Check sentiment
        if self.sentiment and context.sentiment != self.sentiment:
            return False
        
        # Check stage
        if self.stage and context.stage != self.stage:
            return False
        
        return True

class QuickResponseGenerator:
    """Service for generating quick responses"""
    
    def __init__(self, base_provider: AIProvider):
        self.base_provider = base_provider
        self.response_rules = self._initialize_response_rules()
        self.intent_keywords = self._initialize_intent_keywords()
        self.response_library = self._initialize_response_library()
        
    def _initialize_response_rules(self) -> List[ResponseRule]:
        """Initialize response generation rules"""
        return [
            # Pricing/Budget Rules
            ResponseRule(
                name="pricing_inquiry",
                keywords={"price", "cost", "budget", "expensive", "cheap", "pricing"},
                intents={ResponseIntent.PRICING, ResponseIntent.BUDGET},
                responses=[
                    {"text": "What's your budget range?", "intent": ResponseIntent.BUDGET, "confidence": 0.8},
                    {"text": "I can get you a quote", "intent": ResponseIntent.QUOTE, "confidence": 0.7},
                    {"text": "Let me check our pricing", "intent": ResponseIntent.PRICING, "confidence": 0.6}
                ],
                priority=Priority.HIGH
            ),
            
            # Timeline/Urgency Rules
            ResponseRule(
                name="timeline_inquiry",
                keywords={"when", "timeline", "deadline", "urgent", "asap", "quickly"},
                intents={ResponseIntent.TIMELINE},
                responses=[
                    {"text": "When do you need this by?", "intent": ResponseIntent.TIMELINE, "confidence": 0.8},
                    {"text": "What's your timeline?", "intent": ResponseIntent.TIMELINE, "confidence": 0.7},
                    {"text": "How quickly do you need it?", "intent": ResponseIntent.TIMELINE, "confidence": 0.6}
                ],
                priority=Priority.HIGH
            ),
            
            # Technical Requirements
            ResponseRule(
                name="technical_inquiry",
                keywords={"specs", "technical", "requirements", "performance", "compatibility"},
                intents={ResponseIntent.TECHNICAL, ResponseIntent.SPECIFICATIONS},
                responses=[
                    {"text": "What are your technical requirements?", "intent": ResponseIntent.TECHNICAL, "confidence": 0.8},
                    {"text": "Tell me about your current setup", "intent": ResponseIntent.REQUIREMENTS, "confidence": 0.7},
                    {"text": "What specs do you need?", "intent": ResponseIntent.SPECIFICATIONS, "confidence": 0.7}
                ],
                priority=Priority.MEDIUM
            ),
            
            # Product Comparison
            ResponseRule(
                name="comparison_request",
                keywords={"compare", "vs", "versus", "difference", "better", "alternative"},
                intents={ResponseIntent.COMPARISON},
                responses=[
                    {"text": "I can compare options for you", "intent": ResponseIntent.COMPARISON, "confidence": 0.8},
                    {"text": "What would you like to compare?", "intent": ResponseIntent.COMPARISON, "confidence": 0.7},
                    {"text": "Let me show you the differences", "intent": ResponseIntent.COMPARISON, "confidence": 0.6}
                ],
                priority=Priority.MEDIUM
            ),
            
            # Demo/Meeting Requests
            ResponseRule(
                name="demo_meeting",
                keywords={"demo", "show", "meeting", "call", "presentation", "see"},
                intents={ResponseIntent.DEMO, ResponseIntent.MEETING},
                responses=[
                    {"text": "Would you like a demo?", "intent": ResponseIntent.DEMO, "confidence": 0.8},
                    {"text": "Let's schedule a call", "intent": ResponseIntent.MEETING, "confidence": 0.7},
                    {"text": "I can show you how it works", "intent": ResponseIntent.DEMO, "confidence": 0.6}
                ],
                priority=Priority.HIGH
            ),
            
            # Social Proof
            ResponseRule(
                name="social_proof",
                keywords={"customers", "reviews", "testimonials", "case", "references"},
                intents={ResponseIntent.SOCIAL_PROOF, ResponseIntent.CASE_STUDIES},
                responses=[
                    {"text": "I can share customer success stories", "intent": ResponseIntent.CASE_STUDIES, "confidence": 0.8},
                    {"text": "Would you like to see references?", "intent": ResponseIntent.SOCIAL_PROOF, "confidence": 0.7},
                    {"text": "Here are some customer testimonials", "intent": ResponseIntent.SOCIAL_PROOF, "confidence": 0.6}
                ],
                priority=Priority.MEDIUM
            )
        ]
    
    def _initialize_intent_keywords(self) -> Dict[ResponseIntent, Set[str]]:
        """Initialize keyword mappings for intent detection"""
        return {
            ResponseIntent.BUDGET: {"budget", "cost", "price", "expensive", "cheap", "afford", "money"},
            ResponseIntent.TIMELINE: {"timeline", "deadline", "urgent", "asap", "when", "schedule", "quickly"},
            ResponseIntent.TECHNICAL: {"specs", "technical", "requirements", "performance", "compatibility", "system"},
            ResponseIntent.COMPARISON: {"compare", "versus", "vs", "difference", "better", "alternative", "options"},
            ResponseIntent.DEMO: {"demo", "demonstration", "show", "see", "preview", "trial", "test"},
            ResponseIntent.MEETING: {"meeting", "call", "discuss", "talk", "appointment", "schedule", "chat"},
            ResponseIntent.SOCIAL_PROOF: {"references", "testimonials", "case studies", "customers", "reviews", "success"},
            ResponseIntent.PRODUCT_INFO: {"product", "solution", "service", "offering", "features", "benefits"},
            ResponseIntent.QUOTE: {"quote", "proposal", "estimate", "pricing", "cost"},
            ResponseIntent.SUPPORT: {"support", "help", "assistance", "service", "maintenance"},
            ResponseIntent.IMPLEMENTATION: {"implement", "deploy", "install", "setup", "integration"},
            ResponseIntent.USE_CASE: {"use case", "application", "purpose", "goal", "objective"},
            ResponseIntent.REQUIREMENTS: {"requirements", "needs", "must have", "criteria", "specifications"},
            ResponseIntent.DISCOVERY: {"tell me", "more about", "explain", "details", "information"}
        }
    
    def _initialize_response_library(self) -> Dict[ResponseIntent, List[Dict[str, Any]]]:
        """Initialize library of responses by intent"""
        return {
            ResponseIntent.DISCOVERY: [
                {"text": "Tell me more about your needs", "confidence": 0.7, "tags": {"discovery"}},
                {"text": "What are you looking for?", "confidence": 0.6, "tags": {"discovery"}},
                {"text": "Can you share more details?", "confidence": 0.5, "tags": {"discovery"}},
                {"text": "What's your current situation?", "confidence": 0.6, "tags": {"discovery"}}
            ],
            
            ResponseIntent.BUDGET: [
                {"text": "What's your budget range?", "confidence": 0.8, "tags": {"budget", "qualification"}},
                {"text": "Do you have a budget in mind?", "confidence": 0.7, "tags": {"budget"}},
                {"text": "What's your price range?", "confidence": 0.6, "tags": {"budget"}},
                {"text": "How much are you looking to spend?", "confidence": 0.7, "tags": {"budget"}}
            ],
            
            ResponseIntent.TIMELINE: [
                {"text": "When do you need this?", "confidence": 0.8, "tags": {"timeline", "urgency"}},
                {"text": "What's your timeline?", "confidence": 0.7, "tags": {"timeline"}},
                {"text": "How quickly do you need it?", "confidence": 0.6, "tags": {"timeline"}},
                {"text": "When are you looking to start?", "confidence": 0.6, "tags": {"timeline"}}
            ],
            
            ResponseIntent.TECHNICAL: [
                {"text": "What are your technical requirements?", "confidence": 0.8, "tags": {"technical", "specs"}},
                {"text": "Tell me about your setup", "confidence": 0.7, "tags": {"technical"}},
                {"text": "What specs do you need?", "confidence": 0.7, "tags": {"technical", "specs"}},
                {"text": "Any specific technical needs?", "confidence": 0.6, "tags": {"technical"}}
            ],
            
            ResponseIntent.COMPARISON: [
                {"text": "I can compare options for you", "confidence": 0.8, "tags": {"comparison"}},
                {"text": "What would you like to compare?", "confidence": 0.7, "tags": {"comparison"}},
                {"text": "Let me show you the differences", "confidence": 0.6, "tags": {"comparison"}},
                {"text": "Which options interest you?", "confidence": 0.5, "tags": {"comparison"}}
            ],
            
            ResponseIntent.DEMO: [
                {"text": "Would you like a demo?", "confidence": 0.8, "tags": {"demo", "presentation"}},
                {"text": "I can show you how it works", "confidence": 0.7, "tags": {"demo"}},
                {"text": "Want to see it in action?", "confidence": 0.6, "tags": {"demo"}},
                {"text": "Let me demonstrate this", "confidence": 0.6, "tags": {"demo"}}
            ],
            
            ResponseIntent.MEETING: [
                {"text": "Let's schedule a call", "confidence": 0.8, "tags": {"meeting", "call"}},
                {"text": "Would you like to discuss this?", "confidence": 0.7, "tags": {"meeting"}},
                {"text": "Can we set up a meeting?", "confidence": 0.6, "tags": {"meeting"}},
                {"text": "When can we talk?", "confidence": 0.5, "tags": {"meeting"}}
            ],
            
            ResponseIntent.QUOTE: [
                {"text": "I can get you a quote", "confidence": 0.8, "tags": {"quote", "pricing"}},
                {"text": "Let me prepare a proposal", "confidence": 0.7, "tags": {"quote", "proposal"}},
                {"text": "Would you like a detailed quote?", "confidence": 0.6, "tags": {"quote"}},
                {"text": "I'll send you pricing", "confidence": 0.5, "tags": {"quote", "pricing"}}
            ],
            
            ResponseIntent.SOCIAL_PROOF: [
                {"text": "I can share success stories", "confidence": 0.8, "tags": {"social_proof", "testimonials"}},
                {"text": "Would you like references?", "confidence": 0.7, "tags": {"social_proof"}},
                {"text": "Here are customer testimonials", "confidence": 0.6, "tags": {"social_proof"}},
                {"text": "Let me show you case studies", "confidence": 0.6, "tags": {"social_proof", "case_studies"}}
            ],
            
            ResponseIntent.PRODUCT_INFO: [
                {"text": "Let me tell you about our products", "confidence": 0.7, "tags": {"product_info"}},
                {"text": "Here's what we offer", "confidence": 0.6, "tags": {"product_info"}},
                {"text": "Which products interest you?", "confidence": 0.6, "tags": {"product_info"}},
                {"text": "I can explain our solutions", "confidence": 0.5, "tags": {"product_info"}}
            ],
            
            ResponseIntent.NEXT_STEPS: [
                {"text": "What's the next step?", "confidence": 0.7, "tags": {"next_steps"}},
                {"text": "How should we proceed?", "confidence": 0.6, "tags": {"next_steps"}},
                {"text": "What would you like to do next?", "confidence": 0.5, "tags": {"next_steps"}},
                {"text": "Let's move forward", "confidence": 0.6, "tags": {"next_steps"}}
            ]
        }
    
    async def generate_quick_responses(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None,
        num_responses: int = 3,
        min_confidence_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Generate contextually appropriate quick responses"""
        
        try:
            # Analyze conversation context
            context = await self._analyze_conversation_context(messages, customer_context)
            
            # Generate candidate responses
            candidates = await self._generate_candidate_responses(context)
            
            # Filter and rank responses
            filtered_responses = self._filter_and_rank_responses(
                candidates, context, min_confidence_threshold
            )
            
            # Return top N responses
            return [response.dict() for response in filtered_responses[:num_responses]]
            
        except Exception as e:
            logger.error(f"Error generating quick responses: {e}")
            return self._get_fallback_responses()
    
    async def _analyze_conversation_context(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]]
    ) -> ConversationContext:
        """Perform deep analysis of conversation context"""
        
        # Get last customer message
        last_customer_msg = None
        for msg in reversed(messages):
            if msg.role.lower() in ['user', 'customer', 'human']:
                last_customer_msg = msg.content
                break
        
        conversation_text = " ".join([msg.content.lower() for msg in messages if msg.role.lower() in ['user', 'customer', 'human']])
        
        # Detect intents based on keywords
        detected_intents = self._detect_intents(conversation_text)
        
        # Extract keywords
        keywords = self._extract_keywords(conversation_text)
        
        # Analyze sentiment and urgency
        sentiment = self._analyze_sentiment(conversation_text)
        urgency_indicators = self._detect_urgency_indicators(conversation_text)
        
        # Determine conversation stage
        stage = self._determine_conversation_stage(messages, detected_intents)
        
        # Extract product mentions and pain points
        product_mentions = self._extract_product_mentions(conversation_text)
        pain_points = self._extract_pain_points(conversation_text)
        
        return ConversationContext(
            messages=messages,
            customer_context=customer_context,
            detected_intents=detected_intents,
            keywords=keywords,
            sentiment=sentiment,
            stage=stage,
            product_mentions=product_mentions,
            pain_points=pain_points,
            urgency_indicators=urgency_indicators,
            last_customer_message=last_customer_msg,
            message_count=len(messages)
        )
    
    def _detect_intents(self, text: str) -> Set[ResponseIntent]:
        """Detect intents based on keywords in text"""
        detected_intents = set()
        text_words = set(text.lower().split())
        
        for intent, keywords in self.intent_keywords.items():
            # Ensure keywords is a set
            if not isinstance(keywords, set):
                keywords = set(keywords) if keywords else set()
            
            # Check for keyword matches
            if keywords & text_words:
                detected_intents.add(intent)
            
            # Check for phrase matches (for multi-word keywords)
            for keyword in keywords:
                if isinstance(keyword, str) and len(keyword.split()) > 1 and keyword in text:
                    detected_intents.add(intent)
        
        return detected_intents
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract relevant keywords from conversation"""
        # Common stop words to filter out
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'and', 'a', 'to', 'are', 'as', 'an', 
            'or', 'be', 'by', 'this', 'that', 'it', 'with', 'for', 'not', 'you', 
            'have', 'can', 'we', 'i', 'me', 'my', 'do', 'get', 'go', 'will', 'would'
        }
        
        words = set(text.lower().split())
        # Filter out stop words and short words
        keywords = {word for word in words if len(word) > 2 and word not in stop_words}
        
        return keywords
    
    async def _generate_candidate_responses(
        self, 
        context: ConversationContext
    ) -> List[QuickResponse]:
        """Generate candidate responses based on context"""
        
        candidates = []
        
        # Generate rule-based responses
        for rule in self.response_rules:
            if rule.matches(context):
                for response_data in rule.responses:
                    response = QuickResponse(
                        text=response_data["text"],
                        intent=ResponseIntent(response_data["intent"]),
                        priority=rule.priority,
                        confidence=response_data["confidence"],
                        context_score=0.7,  # Base context score for rule matches
                        tags=response_data.get("tags", set())
                    )
                    candidates.append(response)
        
        # Generate intent-based responses
        for intent in context.detected_intents:
            intent_responses = self._generate_intent_responses(intent, context)
            candidates.extend(intent_responses)
        
        # Generate stage-based responses
        stage_responses = self._generate_stage_responses(context.stage, context)
        candidates.extend(stage_responses)
        
        # Generate sentiment-based responses
        sentiment_responses = self._generate_sentiment_responses(context.sentiment, context)
        candidates.extend(sentiment_responses)
        
        return candidates
    
    def _generate_intent_responses(
        self, 
        intent: ResponseIntent, 
        context: ConversationContext
    ) -> List[QuickResponse]:
        """Generate responses for specific intents"""
        
        responses = []
        
        if intent in self.response_library:
            for response_data in self.response_library[intent]:
                response = QuickResponse(
                    text=response_data["text"],
                    intent=intent,
                    confidence=response_data["confidence"],
                    context_score=0.6,  # Base context score
                    tags=response_data.get("tags", set())
                )
                responses.append(response)
        
        return responses
    
    def _generate_stage_responses(
        self, 
        stage: str, 
        context: ConversationContext
    ) -> List[QuickResponse]:
        """Generate responses based on conversation stage"""
        
        responses = []
        
        if stage == "discovery":
            responses.extend([
                QuickResponse(
                    text="Tell me more about your needs",
                    intent=ResponseIntent.DISCOVERY,
                    confidence=0.6,
                    context_score=0.7,
                    tags={"discovery", "qualification"}
                ),
                QuickResponse(
                    text="What challenges are you facing?",
                    intent=ResponseIntent.REQUIREMENTS,
                    confidence=0.6,
                    context_score=0.6,
                    tags={"discovery", "pain_points"}
                )
            ])
        
        elif stage == "evaluation":
            responses.extend([
                QuickResponse(
                    text="Would you like to compare options?",
                    intent=ResponseIntent.COMPARISON,
                    confidence=0.7,
                    context_score=0.7,
                    tags={"comparison", "evaluation"}
                ),
                QuickResponse(
                    text="I can show you customer stories",
                    intent=ResponseIntent.CASE_STUDIES,
                    confidence=0.6,
                    context_score=0.6,
                    tags={"social_proof", "trust"}
                )
            ])
        
        elif stage == "decision":
            responses.extend([
                QuickResponse(
                    text="Ready for a quote?",
                    intent=ResponseIntent.QUOTE,
                    priority=Priority.HIGH,
                    confidence=0.8,
                    context_score=0.8,
                    tags={"quote", "decision"}
                ),
                QuickResponse(
                    text="Let's discuss next steps",
                    intent=ResponseIntent.NEXT_STEPS,
                    priority=Priority.HIGH,
                    confidence=0.7,
                    context_score=0.7,
                    tags={"next_steps", "closing"}
                )
            ])
        
        return responses
    
    def _generate_sentiment_responses(
        self, 
        sentiment: str, 
        context: ConversationContext
    ) -> List[QuickResponse]:
        """Generate responses based on sentiment"""
        
        responses = []
        
        if sentiment == "urgent":
            responses.extend([
                QuickResponse(
                    text="I understand this is urgent",
                    intent=ResponseIntent.TIMELINE,
                    priority=Priority.CRITICAL,
                    confidence=0.8,
                    context_score=0.9,
                    tags={"urgent", "empathy"}
                ),
                QuickResponse(
                    text="Let me prioritize this",
                    intent=ResponseIntent.SUPPORT,
                    priority=Priority.CRITICAL,
                    confidence=0.7,
                    context_score=0.8,
                    tags={"urgent", "support"}
                )
            ])
        
        elif sentiment == "negative":
            responses.extend([
                QuickResponse(
                    text="I'm here to help solve this",
                    intent=ResponseIntent.SUPPORT,
                    priority=Priority.HIGH,
                    confidence=0.7,
                    context_score=0.8,
                    tags={"support", "empathy"}
                ),
                QuickResponse(
                    text="Let's address your concerns",
                    intent=ResponseIntent.REQUIREMENTS,
                    priority=Priority.HIGH,
                    confidence=0.6,
                    context_score=0.7,
                    tags={"support", "problem_solving"}
                )
            ])
        
        elif sentiment == "positive":
            responses.extend([
                QuickResponse(
                    text="Great! Let's move forward",
                    intent=ResponseIntent.NEXT_STEPS,
                    priority=Priority.HIGH,
                    confidence=0.7,
                    context_score=0.7,
                    tags={"positive", "next_steps"}
                ),
                QuickResponse(
                    text="I'm glad to help",
                    intent=ResponseIntent.SUPPORT,
                    confidence=0.6,
                    context_score=0.6,
                    tags={"positive", "support"}
                )
            ])
        
        return responses
    
    def _filter_and_rank_responses(
        self,
        candidates: List[QuickResponse],
        context: ConversationContext,
        min_confidence: float
    ) -> List[QuickResponse]:
        """Filter and rank responses by relevance and confidence"""
        
        # Filter by minimum confidence
        filtered = [r for r in candidates if r.confidence >= min_confidence]
        
        # Remove similar responses
        filtered = self._remove_similar_responses(filtered)
        
        # Calculate enhanced context scores
        for response in filtered:
            response.context_score = self._calculate_context_score(response, context)
        
        # Sort by overall score
        filtered.sort(key=lambda r: r.overall_score, reverse=True)
        
        return filtered
    
    def _remove_similar_responses(self, responses: List[QuickResponse]) -> List[QuickResponse]:
        """Remove responses with similar text content"""
        unique_responses = []
        
        for response in responses:
            is_similar = False
            for existing in unique_responses:
                if response.is_similar_to(existing, threshold=0.7):
                    is_similar = True
                    # Keep the one with higher score
                    if response.overall_score > existing.overall_score:
                        unique_responses.remove(existing)
                        unique_responses.append(response)
                    break
            
            if not is_similar:
                unique_responses.append(response)
        
        return unique_responses
    
    def _calculate_context_score(
        self, 
        response: QuickResponse, 
        context: ConversationContext
    ) -> float:
        """Calculate how well response fits current context"""
        
        score = response.context_score
        
        # Boost for matching intents
        if response.intent in context.detected_intents:
            score += 0.3
        
        # Boost for matching keywords in response tags
        response_words = set(response.text.lower().split())
        keyword_overlap = len(response_words & context.keywords)
        if keyword_overlap > 0:
            score += min(0.1 * keyword_overlap, 0.2)
        
        # Boost for urgency matching
        if context.urgency_indicators and response.priority in [Priority.CRITICAL, Priority.HIGH]:
            score += 0.2
        
        # Boost for sentiment matching
        if context.sentiment == "urgent" and response.priority == Priority.CRITICAL:
            score += 0.2
        elif context.sentiment == "negative" and "support" in response.tags:
            score += 0.15
        elif context.sentiment == "positive" and "next_steps" in response.tags:
            score += 0.1
        
        # Stage-specific boosts
        if context.stage == "decision" and response.intent in [ResponseIntent.QUOTE, ResponseIntent.NEXT_STEPS]:
            score += 0.2
        elif context.stage == "evaluation" and response.intent == ResponseIntent.COMPARISON:
            score += 0.15
        elif context.stage == "discovery" and response.intent in [ResponseIntent.DISCOVERY, ResponseIntent.REQUIREMENTS]:
            score += 0.1
        
        return min(score, 1.0)
    
    def _analyze_sentiment(self, text: str) -> str:
        """Analyze sentiment of conversation text"""
        positive_words = {"great", "excellent", "perfect", "love", "amazing", "fantastic", "good", "yes", "sure"}
        negative_words = {"problem", "issue", "frustrated", "difficult", "wrong", "bad", "terrible", "awful", "no"}
        urgent_words = {"urgent", "asap", "immediately", "critical", "emergency", "quickly", "fast", "now"}
        
        words = set(text.split())
        
        urgent_count = len(words & urgent_words)
        positive_count = len(words & positive_words)
        negative_count = len(words & negative_words)
        
        if urgent_count > 0:
            return "urgent"
        elif positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _detect_urgency_indicators(self, text: str) -> List[str]:
        """Detect urgency indicators in conversation"""
        urgent_phrases = {
            "asap", "urgent", "immediately", "critical", "emergency", "quickly", "fast", "now"
        }
        
        words = set(text.lower().split())
        urgent_words = list(words & urgent_phrases)
        
        return urgent_words
    
    def _extract_product_mentions(self, text: str) -> Set[str]:
        """Extract product mentions from conversation text"""
        # Common product-related terms
        product_terms = {
            "product", "solution", "service", "software", "platform", "system",
            "tool", "application", "app", "package", "suite", "module"
        }
        
        words = set(text.lower().split())
        return words & product_terms
    
    def _extract_pain_points(self, text: str) -> List[str]:
        """Extract pain points and challenges from conversation text"""
        pain_point_indicators = {
            "problem", "issue", "challenge", "difficulty", "pain", "struggle",
            "frustration", "concern", "worry", "trouble", "bottleneck", "hurdle"
        }
        
        words = set(text.lower().split())
        return list(words & pain_point_indicators)
    
    def _determine_conversation_stage(self, messages: List[AIMessage], detected_intents: Set[ResponseIntent]) -> str:
        """Determine the current stage of the conversation"""
        # Ensure detected_intents is a set
        if not isinstance(detected_intents, set):
            detected_intents = set(detected_intents)
            
        # Count message types
        message_count = len(messages)
        customer_messages = sum(1 for msg in messages if msg.role.lower() in ['user', 'customer', 'human'])
        
        # Early stage indicators
        discovery_indicators = {
            ResponseIntent.DISCOVERY,
            ResponseIntent.REQUIREMENTS,
            ResponseIntent.USE_CASE
        }
        
        # Evaluation stage indicators
        evaluation_indicators = {
            ResponseIntent.COMPARISON,
            ResponseIntent.PRODUCT_INFO,
            ResponseIntent.TECHNICAL,
            ResponseIntent.SPECIFICATIONS
        }
        
        # Decision stage indicators
        decision_indicators = {
            ResponseIntent.QUOTE,
            ResponseIntent.PRICING,
            ResponseIntent.BUDGET,
            ResponseIntent.NEXT_STEPS
        }
        
        # Determine stage based on intents and message count
        if message_count <= 2 or (detected_intents & discovery_indicators):
            return "discovery"
        elif detected_intents & decision_indicators:
            return "decision"
        elif detected_intents & evaluation_indicators:
            return "evaluation"
        else:
            # Default to discovery if no clear indicators
            return "discovery"
    
    def _get_fallback_responses(self) -> List[Dict[str, Any]]:
        """Get fallback responses when generation fails"""
        return [
            {
                "text": "I'm here to help. What would you like to know?",
                "intent": ResponseIntent.DISCOVERY,
                "priority": Priority.MEDIUM,
                "confidence": 0.5,
                "context_score": 0.5,
                "tags": {"fallback", "discovery"}
            },
            {
                "text": "Could you tell me more about your needs?",
                "intent": ResponseIntent.REQUIREMENTS,
                "priority": Priority.MEDIUM,
                "confidence": 0.5,
                "context_score": 0.5,
                "tags": {"fallback", "requirements"}
            },
            {
                "text": "How can I assist you today?",
                "intent": ResponseIntent.SUPPORT,
                "priority": Priority.MEDIUM,
                "confidence": 0.5,
                "context_score": 0.5,
                "tags": {"fallback", "support"}
            }
        ]  