from typing import List, Dict, Any, Optional
from datetime import datetime
from .base import AIProvider, AIMessage, AIResponse

class ConversationFlowAgent(AIProvider):
    """Intelligent agent for managing conversation flow and determining readiness for different stages"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        
    @property
    def provider_name(self) -> str:
        return f"conversation_flow_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def analyze_conversation_flow(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Intelligently analyze conversation flow using AI"""
        
        print("🧠 Conversation Flow Agent: Analyzing conversation intelligence...")
        print(f"📝 Analyzing {len(messages)} messages")
        
        # Build analysis prompt for the AI
        analysis_prompt = self._build_flow_analysis_prompt(messages, customer_context)
        
        # Create analysis messages
        analysis_messages = [
            AIMessage(role="system", content=analysis_prompt),
            AIMessage(role="user", content="Please analyze this conversation and provide a comprehensive flow assessment.")
        ]
        
        # Get AI analysis
        response = await self.base_provider.generate_response(analysis_messages)
        print(f"🤖 AI Analysis Response Length: {len(response.content)}")
        
        # Parse AI response into structured data
        flow_analysis = self._parse_ai_analysis(response.content, messages, customer_context)
        
        # Enhanced override for ANY quote requests - be more aggressive in detecting quote intent
        conversation_text = " ".join([msg.content.lower() for msg in messages])
        quote_indicators = [
            'give me the pdf', 'generate quote', 'pdf quote', 'send quote', 
            'yes give me the pdf', 'create quote', 'make quote', 'quote me',
            'i want a quote', 'can i get a quote', 'price quote', 'quotation',
            'how much', 'what does it cost', 'pricing', 'price'
        ]
        
        quote_detected = any(phrase in conversation_text for phrase in quote_indicators)
        print(f"🔍 Quote indicators detected: {quote_detected}")
        
        if quote_detected:
            print("🎯 Overriding analysis - quote explicitly requested")
            flow_analysis.update({
                'quote_ready': True,
                'should_generate_quote': True,
                'business_context_score': max(flow_analysis.get('business_context_score', 0), 85),
                'technical_requirements_score': max(flow_analysis.get('technical_requirements_score', 0), 85),
                'decision_readiness_score': max(flow_analysis.get('decision_readiness_score', 0), 95),
                'current_stage': 'quote_ready',
                'reasoning': 'Customer explicitly requested quote generation - immediate quote ready'
            })
        
        # Add some computed metrics
        flow_analysis.update({
            "conversation_metrics": self._calculate_conversation_metrics(messages),
            "ai_analysis_raw": response.content,
            "analysis_timestamp": datetime.now().isoformat()
        })
        
        print(f"📊 Final Analysis - Quote Ready: {flow_analysis.get('quote_ready', False)}")
        print(f"📊 Should Generate Quote: {flow_analysis.get('should_generate_quote', False)}")
        
        return flow_analysis
    
    def _build_flow_analysis_prompt(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build intelligent prompt for conversation flow analysis"""
        
        # Extract conversation content
        conversation_text = "\n".join([
            f"{msg.role.upper()}: {msg.content}" 
            for msg in messages[-10:]  # Last 10 messages for context
        ])
        
        customer_info = ""
        if customer_context:
            customer_info = f"""
CUSTOMER CONTEXT:
- Company: {customer_context.get('company_name', 'Unknown')}
- Industry: {customer_context.get('industry', 'Unknown')}
- Size: {customer_context.get('company_size', 'Unknown')}
- Budget: {customer_context.get('budget_range', 'Unknown')}
- Timeline: {customer_context.get('timeline', 'Unknown')}
"""
        
        return f"""You are an expert conversation flow analyst for B2B sales. Analyze this sales conversation and provide intelligent insights about readiness for quote generation.

{customer_info}

RECENT CONVERSATION:
{conversation_text}

ANALYSIS FRAMEWORK:
1. **Business Context Completeness** (0-100%):
   - Do we know their industry, company size, use case?
   - Are their business needs clear?

2. **Technical Requirements Clarity** (0-100%):
   - Are technical specifications discussed in detail?
   - Do we understand their performance needs?
   - Are specific products/solutions mentioned?

3. **Decision-Making Readiness** (0-100%):
   - Has budget/timeline been discussed?
   - Are decision makers identified?
   - Is there urgency or buying intent?

4. **Quote Readiness Assessment**:
   - Is the customer explicitly asking for quotes/pricing?
   - Do we have enough information for accurate recommendations?
   - What's missing for a complete quote?

5. **Conversation Stage**:
   - initial_discovery / deep_discovery / solution_presentation / quote_ready / closing

6. **Next Best Actions**:
   - What should the sales agent focus on next?
   - What questions still need to be asked?
   - Should we generate a quote or continue discovery?

Please respond in this EXACT JSON format:

json
{{
"business_context_score": 85,
"technical_requirements_score": 70,
"decision_readiness_score": 60,
"quote_ready": true,
"confidence_level": "high",
"current_stage": "solution_presentation",
"reasoning": "Customer has provided detailed technical specs and explicitly requested pricing. Technical requirements are well-defined with specific product mentions.",
"missing_information": ["decision timeline", "exact budget range"],
"next_best_actions": ["generate comprehensive quote", "discuss implementation timeline"],
"should_generate_quote": true,
"key_insights": ["Customer is technically savvy", "Ready to move to pricing", "Has specific requirements"],
"conversation_quality": "excellent"
}}


Base your analysis on the actual conversation content, explicit customer requests, and sales best practices."""
    
    def _parse_ai_analysis(
        self, 
        ai_response: str, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parse AI analysis response into structured data"""
        
        try:
            import json
            import re
            
            # Extract JSON from the response
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(1))
            else:
                # Fallback parsing if JSON isn't properly formatted
                analysis = self._fallback_parse_analysis(ai_response)
            
            # Validate and normalize scores
            analysis['business_context_score'] = max(0, min(100, analysis.get('business_context_score', 50)))
            analysis['technical_requirements_score'] = max(0, min(100, analysis.get('technical_requirements_score', 50)))
            analysis['decision_readiness_score'] = max(0, min(100, analysis.get('decision_readiness_score', 50)))
            
            # Convert to 0-1 scale for compatibility
            analysis['completion_scores'] = {
                'business_context': analysis['business_context_score'] / 100,
                'technical_requirements': analysis['technical_requirements_score'] / 100,
                'operational_requirements': analysis['decision_readiness_score'] / 100,
                'pain_points': self._assess_pain_points_from_conversation(messages) / 100
            }
            
            # Ensure boolean fields
            analysis['quote_ready'] = bool(analysis.get('quote_ready', False))
            analysis['should_generate_quote'] = bool(analysis.get('should_generate_quote', False))
            
            # Validate stage
            valid_stages = ['initial_discovery', 'deep_discovery', 'solution_presentation', 'quote_ready', 'closing']
            if analysis.get('current_stage') not in valid_stages:
                analysis['current_stage'] = 'deep_discovery'
            
            return analysis
            
        except Exception as e:
            print(f"⚠️ Error parsing AI analysis: {e}")
            return self._fallback_analysis(messages, customer_context)
    
    def _fallback_parse_analysis(self, ai_response: str) -> Dict[str, Any]:
        """Fallback parsing when JSON extraction fails"""
        
        # Extract key information using text analysis
        response_lower = ai_response.lower()
        
        # Score extraction (look for percentages or scores)
        import re
        
        business_score = 50
        tech_score = 50
        decision_score = 50
        
        # Look for business context indicators
        if any(term in response_lower for term in ['industry', 'company', 'business well']):
            business_score = 75
        if any(term in response_lower for term in ['company size', 'industry clear', 'business context complete']):
            business_score = 90
            
        # Look for technical indicators  
        if any(term in response_lower for term in ['technical', 'specs', 'requirements', 'performance']):
            tech_score = 70
        if any(term in response_lower for term in ['detailed specs', 'specific products', 'technical requirements clear']):
            tech_score = 85
            
        # Look for decision indicators
        if any(term in response_lower for term in ['budget', 'timeline', 'decision']):
            decision_score = 60
        if any(term in response_lower for term in ['ready to buy', 'quote ready', 'pricing request']):
            decision_score = 80
        
        # Determine quote readiness
        quote_ready = any(term in response_lower for term in [
            'quote ready', 'ready for quote', 'should generate quote', 'pricing request'
        ])
        
        return {
            'business_context_score': business_score,
            'technical_requirements_score': tech_score,
            'decision_readiness_score': decision_score,
            'quote_ready': quote_ready,
            'should_generate_quote': quote_ready,
            'confidence_level': 'medium',
            'current_stage': 'solution_presentation' if quote_ready else 'deep_discovery',
            'reasoning': 'Fallback analysis based on keyword detection',
            'missing_information': ['detailed analysis unavailable'],
            'next_best_actions': ['generate quote'] if quote_ready else ['continue discovery'],
            'key_insights': ['automated analysis'],
            'conversation_quality': 'good'
        }
    
    def _assess_pain_points_from_conversation(self, messages: List[AIMessage]) -> int:
        """Assess how well pain points have been discussed"""
        
        conversation_text = " ".join([msg.content.lower() for msg in messages])
        
        pain_indicators = [
            'slow', 'problem', 'issue', 'challenge', 'frustrated', 'bottleneck', 
            'limitation', 'current system', 'upgrading', 'replacing', 'better performance'
        ]
        
        pain_score = min(100, sum(10 for indicator in pain_indicators if indicator in conversation_text))
        return pain_score
    
    def _fallback_analysis(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback analysis when AI parsing completely fails"""
        
        conversation_text = " ".join([msg.content.lower() for msg in messages])
        
        # Simple heuristic analysis
        tech_mentions = sum(1 for term in ['cpu', 'gpu', 'ram', 'storage', 'specs'] if term in conversation_text)
        quote_requests = sum(1 for term in ['quote', 'price', 'cost', 'pdf'] if term in conversation_text)
        
        return {
            'business_context_score': 60 if customer_context else 30,
            'technical_requirements_score': min(100, tech_mentions * 20),
            'decision_readiness_score': min(100, quote_requests * 30),
            'quote_ready': quote_requests > 0 and tech_mentions > 2,
            'should_generate_quote': quote_requests > 0,
            'confidence_level': 'low',
            'current_stage': 'deep_discovery',
            'reasoning': 'Fallback heuristic analysis',
            'missing_information': ['AI analysis failed'],
            'next_best_actions': ['continue conversation'],
            'key_insights': ['automated fallback'],
            'conversation_quality': 'unknown',
            'completion_scores': {
                'business_context': 0.6 if customer_context else 0.3,
                'technical_requirements': min(1.0, tech_mentions * 0.2),
                'operational_requirements': min(1.0, quote_requests * 0.3),
                'pain_points': 0.5
            }
        }
    
    def _calculate_conversation_metrics(self, messages: List[AIMessage]) -> Dict[str, Any]:
        """Calculate basic conversation metrics"""
        
        user_messages = [msg for msg in messages if msg.role == "user"]
        assistant_messages = [msg for msg in messages if msg.role == "assistant"]
        
        return {
            "total_exchanges": len(user_messages),
            "total_messages": len(messages),
            "conversation_length": sum(len(msg.content.split()) for msg in messages),
            "avg_user_message_length": sum(len(msg.content.split()) for msg in user_messages) / max(len(user_messages), 1),
            "avg_assistant_message_length": sum(len(msg.content.split()) for msg in assistant_messages) / max(len(assistant_messages), 1),
            "engagement_level": "high" if len(user_messages) > 5 else "medium" if len(user_messages) > 2 else "low",
            "conversation_depth": len(user_messages)
        }
    
    async def suggest_next_actions(
        self, 
        flow_analysis: Dict[str, Any], 
        messages: List[AIMessage]
    ) -> Dict[str, Any]:
        """Get AI-powered suggestions for next actions"""
        
        suggestion_prompt = f"""Based on this conversation flow analysis, provide specific guidance for the sales agent.

ANALYSIS SUMMARY:
- Business Context: {flow_analysis.get('business_context_score', 0)}%
- Technical Requirements: {flow_analysis.get('technical_requirements_score', 0)}%
- Decision Readiness: {flow_analysis.get('decision_readiness_score', 0)}%
- Current Stage: {flow_analysis.get('current_stage', 'unknown')}
- Quote Ready: {flow_analysis.get('quote_ready', False)}

MISSING INFO: {flow_analysis.get('missing_information', [])}

Provide specific, actionable guidance in JSON format:

json
{{
"primary_action": "generate_quote | continue_discovery | present_solution",
"specific_questions": ["What specific questions should be asked next?"],
"conversation_strategy": "How should the agent approach the next interaction?",
"urgency_level": "low | medium | high",
"estimated_close_probability": 75
}}"""
        
        suggestion_messages = [
            AIMessage(role="system", content="You are an expert sales strategy advisor."),
            AIMessage(role="user", content=suggestion_prompt)
        ]
        
        response = await self.base_provider.generate_response(suggestion_messages)
        
        try:
            import json
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response.content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except:
            pass
        
        # Fallback suggestions
        return {
            "primary_action": "generate_quote" if flow_analysis.get('quote_ready') else "continue_discovery",
            "specific_questions": flow_analysis.get('next_best_actions', []),
            "conversation_strategy": "Follow customer lead and provide value",
            "urgency_level": "medium",
            "estimated_close_probability": 50
        }

    async def generate_response(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate response using the base provider"""
        return await self.base_provider.generate_response(messages, customer_context, **kwargs)