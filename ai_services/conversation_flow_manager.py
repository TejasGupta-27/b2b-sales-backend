from typing import List, Dict, Any, Optional
from datetime import datetime
from .base import AIProvider, AIMessage, AIResponse
from .function_models import ConversationAnalysis

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
    
    async def analyze_conversation_state(
        self,
        messages: List[AIMessage],
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze conversation state using Pydantic function calling"""
        
        conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
        
        analysis_prompt = f"""Analyze this B2B sales conversation to determine the current stage, readiness levels, and next steps.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT: {customer_context or 'None'}

IMPORTANT: For current_stage, you MUST use one of these exact values:
- "initial_discovery" - First contact, basic information gathering
- "deep_discovery" - Detailed requirements gathering
- "solution_presentation" - Presenting solutions to customer
- "quote_ready" - Customer is ready for pricing
- "closing" - Final negotiation and closing

Analyze the conversation comprehensively to understand:
1. What stage of the sales process we're in (use exact values above)
2. How much business context we understand (0-100)
3. How clear the technical requirements are (0-100) 
4. How ready the customer is to make a decision (0-100)
5. Whether they're ready for a quote
6. What information is still missing
7. What questions should be asked next"""

        try:
            # Use structured response with Pydantic
            analysis = await self.base_provider.generate_structured_response(
                [AIMessage(role="user", content=analysis_prompt)],
                ConversationAnalysis
            )
            
            # Convert to dict with additional processing
            analysis_dict = analysis.model_dump()
            
            # Add completion scores for compatibility
            analysis_dict['completion_scores'] = {
                'business_context': analysis.business_context_score / 100,
                'technical_requirements': analysis.technical_requirements_score / 100,
                'operational_requirements': analysis.decision_readiness_score / 100,
                'pain_points': len([msg for msg in messages if 'problem' in msg.content.lower() or 'issue' in msg.content.lower()]) / 10
            }
            
            return analysis_dict
            
        except Exception as e:
            print(f"⚠️ Pydantic conversation analysis failed: {e}")
            return self._fallback_analysis(messages, customer_context)
    
    def _build_flow_analysis_prompt(
        self, 
        messages: List[AIMessage], 
        customer_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build simplified prompt for conversation flow analysis"""
        
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
        
        return f"""Analyze this B2B sales conversation to understand the customer's readiness for a quote.

{customer_info}

CONVERSATION:
{conversation_text}

Please evaluate:
1. How well do we understand their business needs?
2. Are technical requirements clear?
3. Has the customer expressed interest in pricing?
4. What information is still needed?

Respond with a brief assessment including:
- Business context understanding (percentage)
- Technical requirements clarity (percentage)  
- Decision readiness level (percentage)
- Whether a quote should be generated (yes/no)
- What's missing for a complete quote
- Recommended next steps

Keep your response conversational and helpful."""
    
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