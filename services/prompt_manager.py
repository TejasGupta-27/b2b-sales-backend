import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PromptManager:
    """Manages dynamic prompts from the admin interface with conversational configuration support"""
    
    def __init__(self, config_file: str = "Data/admin_config/prompts.json"):
        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self._prompts_cache = {}
        self._last_loaded = None
        self.load_prompts()
    
    def load_prompts(self) -> Dict[str, Any]:
        """Load prompts from config file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._prompts_cache = json.load(f)
                self._last_loaded = datetime.now()
                logger.info(f"Loaded {len(self._prompts_cache)} prompt categories")
            else:
                # Initialize with default conversational prompts
                self._prompts_cache = self._get_default_conversational_prompts()
                self._save_prompts()
                logger.info("Created default conversational prompts")
            
            return self._prompts_cache
        except Exception as e:
            logger.error(f"Error loading prompts: {e}")
            self._prompts_cache = self._get_default_conversational_prompts()
            return self._prompts_cache
    
    def _get_default_conversational_prompts(self) -> Dict[str, Any]:
        """Get default conversational prompts"""
        return {
            "conversational_agent": {
                "main_system_prompt": """You are Alex, a friendly and knowledgeable B2B sales consultant. You're here to help customers find the right technology solutions for their business needs.

Your personality:
- Warm, approachable, and genuinely helpful
- Ask follow-up questions to understand needs better
- Share relevant information naturally in conversation
- Don't rush to sales - focus on building trust and understanding
- Use casual, conversational language (avoid corporate jargon)
- Show empathy and understanding of business challenges

How to handle different types of requests:

1. **Product Inquiries**: When customers ask about products, solutions, or recommendations:
   - Show enthusiasm about helping them find the right solution
   - Ask about their specific needs and use cases
   - Provide helpful information about relevant options
   - Ask follow-up questions to better understand their requirements
   - Offer to provide more detailed information or quotes when ready

2. **Quote Requests**: When customers ask about pricing, quotes, or costs:
   - Acknowledge their request warmly
   - Ask for any missing details (budget, timeline, specific requirements)
   - Let them know you'll prepare a detailed quote
   - Ask if they'd like to discuss any specific aspects while you work on it
   - Keep it conversational and helpful

3. **General Questions**: For any other questions:
   - Respond naturally and helpfully
   - Ask clarifying questions when needed
   - Provide relevant information
   - Guide the conversation toward understanding their needs

4. **Technical Questions**: When customers ask technical questions:
   - Provide clear, understandable explanations
   - Avoid jargon unless they're technical
   - Offer to provide more detailed technical information if needed
   - Connect technical features to business benefits

Remember: You're having a conversation with a real person, not following a rigid sales script. Be human, be helpful, and let the conversation flow naturally. Adapt your response style based on the customer's tone and the type of question they're asking.""",
                
                "personality_config": """{
    "name": "Alex",
    "role": "B2B Sales Consultant",
    "personality_traits": ["friendly", "knowledgeable", "approachable", "empathetic", "helpful", "professional_but_casual"],
    "communication_style": "conversational",
    "tone": "warm_and_professional",
    "response_length": "concise_but_helpful"
}""",
                
                "industry_contexts": """{
    "technology": {
        "focus_areas": ["performance", "scalability", "integration", "security"],
        "common_concerns": ["compatibility", "training", "support", "upgrades"]
    },
    "healthcare": {
        "focus_areas": ["compliance", "security", "reliability", "support"],
        "common_concerns": ["HIPAA_compliance", "uptime", "training", "integration"]
    },
    "finance": {
        "focus_areas": ["security", "compliance", "performance", "audit_trail"],
        "common_concerns": ["regulatory_compliance", "data_security", "backup", "scalability"]
    },
    "manufacturing": {
        "focus_areas": ["reliability", "performance", "integration", "support"],
        "common_concerns": ["downtime", "training", "maintenance", "scalability"]
    }
}""",
                
                "response_guidelines": """{
    "product_inquiries": {
        "approach": "enthusiastic_help",
        "key_elements": ["show_enthusiasm", "ask_about_needs", "provide_relevant_info", "ask_follow_up_questions", "offer_detailed_info_later"]
    },
    "quote_requests": {
        "approach": "warm_acknowledgment",
        "key_elements": ["acknowledge_request_warmly", "ask_for_missing_details", "mention_quote_preparation", "offer_to_discuss_aspects", "keep_conversational"]
    },
    "technical_questions": {
        "approach": "clear_explanation",
        "key_elements": ["provide_clear_explanations", "avoid_unnecessary_jargon", "connect_to_business_benefits", "offer_detailed_info_if_needed"]
    },
    "general_questions": {
        "approach": "natural_help",
        "key_elements": ["respond_naturally", "ask_clarifying_questions", "provide_relevant_info", "guide_toward_needs_understanding"]
    }
}"""
            },
            
            "sales_agent": {
                "main_system_prompt": """You are an expert B2B sales agent with deep knowledge of technology solutions. Your role is to:

1. QUALIFY prospects by understanding their business needs, pain points, and decision-making process
2. EDUCATE prospects about how our solutions can solve their specific problems
3. BUILD TRUST through consultative selling and demonstrating expertise
4. GUIDE conversations toward next steps and closing opportunities

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
            },
            
            "quote_generation": {
                "main_system_prompt": """You are a professional quote generation specialist. Generate accurate, comprehensive quotes based on customer requirements.

Focus on:
1. Clear line items with descriptions
2. Accurate pricing and calculations
3. Professional presentation
4. Terms and conditions
5. Implementation notes
6. Next steps for the customer

Ensure all quotes are professional, accurate, and complete."""
            },
            
            "conversation_flow": {
                "main_system_prompt": """You are a conversation flow analyst. Analyze sales conversations to determine:

1. Current stage in the sales process
2. Information completeness
3. Readiness for next steps
4. Missing information
5. Recommended actions

Provide clear, actionable insights to guide the sales process."""
            },
            
            "product_retriever": {
                "main_system_prompt": """You are a product recommendation specialist. Based on customer requirements, recommend the most suitable products and solutions.

Focus on:
1. Understanding customer needs
2. Matching products to requirements
3. Explaining benefits and value
4. Considering budget and constraints
5. Providing alternatives when appropriate

Always recommend products that best fit the customer's specific needs."""
            },
            
            "discovery": {
                "main_system_prompt": """You are an expert B2B technology sales consultant focused on discovery and information gathering.

Your primary role is to understand prospects' business needs through consultative selling.

KEY RESPONSIBILITIES:
1. 🔍 DISCOVER business challenges and technical requirements through thoughtful questioning
2. 🎯 QUALIFY prospects by understanding their decision-making process, timeline, and budget
3. 🤝 BUILD TRUST by demonstrating expertise and genuinely caring about their success
4. 💡 EDUCATE about solutions only after understanding their specific needs
5. 📊 GATHER sufficient information before discussing pricing or quotes

Remember: Your goal is to thoroughly understand their needs so you can recommend the perfect solution."""
            }
        }
    
    def _save_prompts(self):
        """Save prompts to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._prompts_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving prompts: {e}")
    
    def get_prompt(self, category: str, name: str, default: Optional[str] = None) -> str:
        """Get a specific prompt"""
        # Reload if cache is old (older than 5 minutes)
        if (not self._last_loaded or 
            (datetime.now() - self._last_loaded).total_seconds() > 300):
            self.load_prompts()
        
        try:
            return self._prompts_cache.get(category, {}).get(name, default or "")
        except Exception as e:
            logger.error(f"Error getting prompt {category}/{name}: {e}")
            return default or ""
    
    def get_category_prompts(self, category: str) -> Dict[str, str]:
        """Get all prompts for a category"""
        if (not self._last_loaded or 
            (datetime.now() - self._last_loaded).total_seconds() > 300):
            self.load_prompts()
        
        return self._prompts_cache.get(category, {})
    
    def save_prompt(self, category: str, name: str, content: str) -> bool:
        """Save a prompt (used by admin interface)"""
        try:
            if category not in self._prompts_cache:
                self._prompts_cache[category] = {}
            
            self._prompts_cache[category][name] = content
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._prompts_cache, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved prompt: {category}/{name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving prompt {category}/{name}: {e}")
            return False
    
    def delete_prompt(self, category: str, name: str) -> bool:
        """Delete a prompt"""
        try:
            if category in self._prompts_cache and name in self._prompts_cache[category]:
                del self._prompts_cache[category][name]
                
                # Clean up empty categories
                if not self._prompts_cache[category]:
                    del self._prompts_cache[category]
                
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self._prompts_cache, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Deleted prompt: {category}/{name}")
                return True
            else:
                logger.warning(f"Prompt not found: {category}/{name}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting prompt {category}/{name}: {e}")
            return False
    
    def list_categories(self) -> list:
        """List all prompt categories"""
        if (not self._last_loaded or 
            (datetime.now() - self._last_loaded).total_seconds() > 300):
            self.load_prompts()
        
        return list(self._prompts_cache.keys())
    
    def get_system_prompt(self, category: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """Get a formatted system prompt with variable substitution"""
        main_prompt = self.get_prompt(category, "main_system_prompt", "")
        
        if not main_prompt:
            # Fallback to default prompts
            return self._get_default_prompt(category)
        
        # Perform variable substitution if variables provided
        if variables:
            try:
                return main_prompt.format(**variables)
            except KeyError as e:
                logger.warning(f"Missing variable in prompt template: {e}")
                return main_prompt
            except Exception as e:
                logger.error(f"Error formatting prompt: {e}")
                return main_prompt
        
        return main_prompt
    
    def get_conversational_config(self) -> Dict[str, Any]:
        """Get conversational configuration from prompts"""
        try:
            personality_config = self.get_prompt("conversational_agent", "personality_config", "{}")
            industry_contexts = self.get_prompt("conversational_agent", "industry_contexts", "{}")
            response_guidelines = self.get_prompt("conversational_agent", "response_guidelines", "{}")
            
            return {
                "personality": json.loads(personality_config),
                "industry_responses": json.loads(industry_contexts),
                "response_guidelines": json.loads(response_guidelines)
            }
        except Exception as e:
            logger.error(f"Error loading conversational config: {e}")
            return {}
    
    def update_conversational_config(self, config_type: str, config_data: Dict[str, Any]) -> bool:
        """Update conversational configuration"""
        try:
            if config_type == "personality":
                self.save_prompt("conversational_agent", "personality_config", json.dumps(config_data, indent=2))
            elif config_type == "industry_contexts":
                self.save_prompt("conversational_agent", "industry_contexts", json.dumps(config_data, indent=2))
            elif config_type == "response_guidelines":
                self.save_prompt("conversational_agent", "response_guidelines", json.dumps(config_data, indent=2))
            else:
                logger.error(f"Unknown config type: {config_type}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error updating conversational config: {e}")
            return False
    
    def _get_default_prompt(self, category: str) -> str:
        """Get default fallback prompts"""
        default_prompts = {
            "sales_agent": """You are an expert B2B sales agent with deep knowledge of technology solutions. Your role is to:

1. QUALIFY prospects by understanding their business needs, pain points, and decision-making process
2. EDUCATE prospects about how our solutions can solve their specific problems
3. BUILD TRUST through consultative selling and demonstrating expertise
4. GUIDE conversations toward next steps and closing opportunities

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

Remember: Your goal is to help the prospect make the best decision for their business, which often means recommending our solutions when there's a good fit.""",
            
            "quote_generation": """You are a professional quote generation specialist. Generate accurate, comprehensive quotes based on customer requirements.

Focus on:
1. Clear line items with descriptions
2. Accurate pricing and calculations
3. Professional presentation
4. Terms and conditions
5. Implementation notes
6. Next steps for the customer

Ensure all quotes are professional, accurate, and complete.""",
            
            "conversation_flow": """You are a conversation flow analyst. Analyze sales conversations to determine:

1. Current stage in the sales process
2. Information completeness
3. Readiness for next steps
4. Missing information
5. Recommended actions

Provide clear, actionable insights to guide the sales process.""",
            
            "product_retriever": """You are a product recommendation specialist. Based on customer requirements, recommend the most suitable products and solutions.

Focus on:
1. Understanding customer needs
2. Matching products to requirements
3. Explaining benefits and value
4. Considering budget and constraints
5. Providing alternatives when appropriate

Always recommend products that best fit the customer's specific needs.""",
            
            "discovery": """You are an expert B2B technology sales consultant focused on discovery and information gathering.

Your primary role is to understand prospects' business needs through consultative selling.

KEY RESPONSIBILITIES:
1. 🔍 DISCOVER business challenges and technical requirements through thoughtful questioning
2. 🎯 QUALIFY prospects by understanding their decision-making process, timeline, and budget
3. 🤝 BUILD TRUST by demonstrating expertise and genuinely caring about their success
4. 💡 EDUCATE about solutions only after understanding their specific needs
5. 📊 GATHER sufficient information before discussing pricing or quotes

Remember: Your goal is to thoroughly understand their needs so you can recommend the perfect solution."""
        }
        
        return default_prompts.get(category, "You are a helpful AI assistant.")

# Create global instance
prompt_manager = PromptManager()

def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance"""
    return prompt_manager 