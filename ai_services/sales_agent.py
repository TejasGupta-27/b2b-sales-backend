import json
from typing import List, Dict, Any, Optional
from .base import AIProvider, AIMessage, AIResponse
from models.lead import Lead
class SalesAgentProvider(AIProvider):
    """Specialized AI provider for B2B sales conversations"""
    
    def __init__(self, base_provider: AIProvider, **kwargs):
        super().__init__(**kwargs)
        self.base_provider = base_provider
        self.sales_knowledge = self._load_sales_knowledge()
    
    @property
    def provider_name(self) -> str:
        return f"sales_agent_{self.base_provider.provider_name}"
    
    def is_configured(self) -> bool:
        return self.base_provider.is_configured()
    
    async def generate_response(
        self, 
        messages: List[AIMessage], 
        lead: Optional[Lead] = None,
        conversation_stage: str = "discovery",
        **kwargs
    ) -> AIResponse:
        # Add sales context and lead information to the conversation
        enhanced_messages = self._add_sales_context(messages, lead, conversation_stage)
        
        # Call the base provider with enhanced context
        response = await self.base_provider.generate_response(enhanced_messages, **kwargs)
        
        # Post-process the response for sales-specific enhancements
        enhanced_response = self._enhance_sales_response(response, lead, conversation_stage)
        
        return enhanced_response
    
    def _add_sales_context(self, messages: List[AIMessage], lead: Optional[Lead], stage: str) -> List[AIMessage]:
        """Add sales-specific context to the conversation"""
        
        # Build the system prompt for the sales agent
        system_prompt = self._build_sales_system_prompt(lead, stage)
        
        # Create enhanced message list
        enhanced_messages = [AIMessage(role="system", content=system_prompt)]
        
        # Add lead context if available
        if lead:
            lead_context = self._build_lead_context(lead)
            enhanced_messages.append(AIMessage(role="system", content=lead_context))
        
        # Add conversation stage guidance
        stage_guidance = self._get_stage_guidance(stage)
        enhanced_messages.append(AIMessage(role="system", content=stage_guidance))
        
        # Add the original messages
        enhanced_messages.extend(messages)
        
        return enhanced_messages
    
    def _build_sales_system_prompt(self, lead: Optional[Lead], stage: str) -> str:
        """Build the main system prompt for the sales agent"""
        return f"""You are an expert B2B sales agent with deep knowledge of technology solutions. Your role is to:

1. QUALIFY prospects by understanding their business needs, pain points, and decision-making process
2. EDUCATE prospects about how our solutions can solve their specific problems
3. BUILD TRUST through consultative selling and demonstrating expertise
4. GUIDE conversations toward next steps and closing opportunities

Current conversation stage: {stage}

Key sales principles to follow:
- Ask open-ended discovery questions
- Listen actively and acknowledge pain points
- Present solutions that directly address stated needs
- Use social proof and case studies when relevant
- Create urgency through value demonstration
- Always suggest clear next steps

Communication style:
- Professional but conversational
- Consultative, not pushy
- Focus on value, not features
- Use industry-specific language when appropriate
- Be empathetic to business challenges

Remember: Your goal is to help the prospect make the best decision for their business, which often means recommending our solutions when there's a good fit."""

    def _build_lead_context(self, lead: Lead) -> str:
        """Build context about the specific lead"""
        context_parts = [
            f"LEAD INFORMATION:",
            f"Company: {lead.company_name}",
            f"Contact: {lead.contact_name} ({lead.email})",
        ]
        
        if lead.industry:
            context_parts.append(f"Industry: {lead.industry}")
        
        if lead.company_size:
            context_parts.append(f"Company Size: {lead.company_size.value}")
        
        if lead.pain_points:
            context_parts.append(f"Known Pain Points: {', '.join(lead.pain_points)}")
        
        if lead.budget_range:
            context_parts.append(f"Budget Range: {lead.budget_range}")
        
        if lead.decision_timeline:
            context_parts.append(f"Decision Timeline: {lead.decision_timeline}")
        
        if lead.decision_makers:
            context_parts.append(f"Decision Makers: {', '.join(lead.decision_makers)}")
        
        if lead.notes:
            context_parts.append(f"Additional Notes: {lead.notes}")
        
        return "\n".join(context_parts)
    
    def _get_stage_guidance(self, stage: str) -> str:
        """Get stage-specific guidance for the conversation"""
        stage_guidance = {
            "discovery": """
DISCOVERY STAGE FOCUS:
- Ask about their current challenges and pain points
- Understand their existing solutions and what's not working
- Identify budget and timeline constraints
- Determine who else is involved in decision-making
- Qualify the opportunity size and fit

Key questions to explore:
- What's driving them to look for a solution now?
- What's the impact of not solving this problem?
- How are they handling this currently?
- What would success look like?
- Who else would be involved in this decision?
""",
            "presentation": """
PRESENTATION STAGE FOCUS:
- Present solutions that directly address their stated needs
- Use specific examples and case studies from similar companies
- Demonstrate clear ROI and value proposition
- Address potential objections proactively
- Create urgency through scarcity or timing

Key elements to include:
- Specific benefits tied to their pain points
- Social proof from similar customers
- Clear ROI calculations
- Implementation timeline
- Next steps for moving forward
""",
            "objection_handling": """
OBJECTION HANDLING FOCUS:
- Listen carefully to understand the real concern
- Acknowledge their perspective before responding
- Provide specific evidence to address concerns
- Reframe objections as opportunities to clarify value
- Ask follow-up questions to ensure resolution

Common objections and approaches:
- Price: Focus on ROI and cost of not solving the problem
- Timing: Explore the cost of waiting and opportunity loss
- Authority: Identify decision-makers and build consensus
- Need: Revisit pain points and consequences
- Trust: Provide references and guarantees
""",
            "closing": """
CLOSING STAGE FOCUS:
- Summarize the value proposition and fit
- Create urgency for decision-making
- Propose specific next steps
- Address any final concerns
- Get commitment to move forward

Closing techniques:
- Assumption close: "When would you like to start implementation?"
- Alternative close: "Would you prefer option A or option B?"
- Urgency close: "This pricing is only available until..."
- Trial close: "How does this sound so far?"
- Direct close: "Are you ready to move forward?"
"""
        }
        
        return stage_guidance.get(stage, "Focus on understanding the prospect's needs and presenting relevant solutions.")
    
    def _enhance_sales_response(self, response: AIResponse, lead: Optional[Lead], stage: str) -> AIResponse:
        """Post-process the response for sales-specific enhancements"""
        
        # Add sales-specific metadata
        enhanced_content = response.content
        
        # Add conversation insights
        insights = self._extract_conversation_insights(response.content, lead)
        
        # Update the response with enhanced content
        response.content = enhanced_content
        
        # Add sales metadata
        if not response.usage:
            response.usage = {}
        
        response.usage.update({
            "conversation_stage": stage,
            "insights": insights,
            "lead_id": lead.id if lead else None
        })
        
        return response
    
    def _extract_conversation_insights(self, response_content: str, lead: Optional[Lead]) -> Dict[str, Any]:
        """Extract insights from the conversation for lead management"""
        insights = {
            "action_items": [],
            "next_steps": [],
            "pain_points_mentioned": [],
            "objections_raised": [],
            "buying_signals": [],
            "follow_up_needed": False
        }
        
        # Simple keyword-based extraction (could be enhanced with NLP)
        content_lower = response_content.lower()
        
        # Detect action items
        if any(phrase in content_lower for phrase in ["let's schedule", "i'll send", "follow up", "next step"]):
            insights["follow_up_needed"] = True
        
        # Detect buying signals
        buying_signals = ["budget", "timeline", "when can we", "how soon", "decision", "approval"]
        for signal in buying_signals:
            if signal in content_lower:
                insights["buying_signals"].append(signal)
        
        # Detect objections
        objection_phrases = ["too expensive", "not sure", "need to think", "concern", "worried about"]
        for objection in objection_phrases:
            if objection in content_lower:
                insights["objections_raised"].append(objection)
        
        return insights
    
    def _load_sales_knowledge(self) -> Dict[str, Any]:
        """Load sales knowledge base (case studies, objection handling, etc.)"""
        # This would typically load from a database or file
        return {
            "case_studies": [],
            "objection_responses": {},
            "value_propositions": {},
            "industry_insights": {}
        } 