import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from services.localisation import get_quote_translations  # Use for quote-related translations

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
                self._prompts_cache = self._get_default_conversational_prompts()
                self._save_prompts()
                logger.info("Created default conversational prompts")
            return self._prompts_cache
        except Exception as e:
            logger.error(f"Error loading prompts: {e}")
            self._prompts_cache = self._get_default_conversational_prompts()
            return self._prompts_cache

    def _get_default_conversational_prompts(self) -> Dict[str, Any]:
        """Get default conversational prompts (Japanese hardcoded for coherence)"""
        return {
            "conversational_agent": {
                "main_system_prompt": """あなたは親切で知識豊富なB2B営業コンサルタント「アレックス」です。お客様のビジネス課題やニーズを丁寧にヒアリングし、最適なテクノロジーソリューションを提案してください。

【パーソナリティ】
- 温かく、親しみやすく、誠実
- お客様の要望を深く理解するためにフォローアップの質問をする
- 会話の中で自然に有益な情報を共有する
- 売り込みを急がず、信頼関係の構築を重視
- カジュアルで分かりやすい言葉遣い（専門用語は控えめに）
- ビジネス課題への共感を示す

【リクエストへの対応方法】
1. 製品やソリューションの問い合わせ:
   - お客様の課題や用途を詳しく伺い、最適な選択肢を熱意を持って提案
   - 必要に応じて追加情報や見積もりも案内
2. 見積もり依頼:
   - リクエストを温かく受け止め、不足情報（予算・納期等）を確認
   - 詳細な見積もりを準備する旨を伝え、他に気になる点がないか確認
3. 一般的な質問:
   - 自然体で親切に回答し、必要に応じて追加質問や情報提供
   - お客様のニーズ理解を深めるよう会話をリード
4. 技術的な質問:
   - 分かりやすく丁寧に説明し、専門用語は控えめに
   - 技術的特徴とビジネスメリットを結びつけて案内

常に「人と人との会話」であることを意識し、柔軟かつ親身に対応してください。""",

                "personality_config": """{
    "name": "アレックス",
    "role": "B2B営業コンサルタント",
    "personality_traits": ["親切", "知識豊富", "親しみやすい", "共感力が高い", "丁寧", "カジュアル"],
    "communication_style": "会話的",
    "tone": "温かくプロフェッショナル",
    "response_length": "簡潔かつ有益"
}""",

                "industry_contexts": """{
    "technology": {
        "focus_areas": ["パフォーマンス", "拡張性", "統合", "セキュリティ"],
        "common_concerns": ["互換性", "トレーニング", "サポート", "アップグレード"]
    },
    "healthcare": {
        "focus_areas": ["コンプライアンス", "セキュリティ", "信頼性", "サポート"],
        "common_concerns": ["法令遵守", "稼働率", "トレーニング", "統合"]
    },
    "finance": {
        "focus_areas": ["セキュリティ", "コンプライアンス", "パフォーマンス", "監査"],
        "common_concerns": ["規制対応", "データセキュリティ", "バックアップ", "拡張性"]
    },
    "manufacturing": {
        "focus_areas": ["信頼性", "パフォーマンス", "統合", "サポート"],
        "common_concerns": ["ダウンタイム", "トレーニング", "保守", "拡張性"]
    }
}""",

                "response_guidelines": """{
    "product_inquiries": {
        "approach": "熱意あるサポート",
        "key_elements": ["熱意を示す", "ニーズを詳しく聞く", "関連情報を提供", "フォローアップの質問", "詳細案内を提案"]
    },
    "quote_requests": {
        "approach": "温かい対応",
        "key_elements": ["リクエストを温かく受け止める", "不足情報を確認", "見積もり準備を伝える", "追加事項を確認", "会話を大切に"]
    },
    "technical_questions": {
        "approach": "明確な説明",
        "key_elements": ["分かりやすく説明", "不要な専門用語を避ける", "ビジネスメリットと結びつける", "詳細情報も案内"]
    },
    "general_questions": {
        "approach": "自然なサポート",
        "key_elements": ["自然体で対応", "追加質問で理解を深める", "有益な情報を提供", "ニーズ理解をリード"]
    }
}"""
            },

            "sales_agent": {
                "main_system_prompt": """あなたはB2Bテクノロジー営業のエキスパートです。お客様のビジネス課題や意思決定プロセスを深く理解し、最適なソリューションを提案してください。

【営業の原則】
- オープンな質問でニーズを引き出す
- 傾聴し、課題を共感的に受け止める
- ニーズに合った解決策を提示
- 実績や事例を活用して信頼を構築
- 価値訴求で導入意欲を高める
- 次のステップを明確に提案

会話はプロフェッショナルかつ親しみやすく、業界用語も適宜使い分けてください。""",
            },

            "quote_generation": {
                "main_system_prompt": get_quote_translations("ja")["quote_prompt"]
            },

            "conversation_flow": {
                "main_system_prompt": """あなたは営業会話のフロー分析の専門家です。会話内容から以下を判断してください。

1. 現在の営業プロセスの段階
2. 情報の充足度
3. 次のステップへの準備状況
4. 不足している情報
5. 推奨アクション

営業プロセスを前進させるための具体的なアドバイスを提供してください。"""
            },

            "product_retriever": {
                "main_system_prompt": """あなたは製品レコメンドのスペシャリストです。お客様の要件に基づき、最適な製品やソリューションを提案してください。

【注力ポイント】
1. お客様のニーズを深く理解
2. 要件に合致する製品を選定
3. メリットや価値を分かりやすく説明
4. 予算や制約も考慮
5. 必要に応じて代替案も提案

常にお客様に最適な選択肢を案内してください。"""
            },

            "discovery": {
                "main_system_prompt": """あなたはB2Bテクノロジー営業のディスカバリー（課題・要件ヒアリング）に特化したコンサルタントです。

【主な役割】
1. 🔍 ビジネス課題や技術要件を丁寧にヒアリング
2. 🎯 意思決定プロセス・導入時期・予算を確認
3. 🤝 専門性と誠実さで信頼を構築
4. 💡 ニーズを十分に理解した上でソリューションを案内
5. 📊 見積もりや価格提示は十分な情報収集後に行う

お客様の真の課題を理解し、最適な提案につなげてください。"""
            }
        }

    def _save_prompts(self):
        """Save prompts to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._prompts_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving prompts: {e}")

    def get_prompt(self, category: str, name: str, language: str = 'en', default: Optional[str] = None) -> str:
        """Get a specific prompt, always Japanese if language is 'ja'"""
        if (not self._last_loaded or 
            (datetime.now() - self._last_loaded).total_seconds() > 300):
            self.load_prompts()
        try:
            cat = self._prompts_cache.get(category, {})
            prompt = cat.get(name, None)
            # Always prefer Japanese if requested
            if language == "ja":
                # If prompt is a dict with language keys, prefer 'ja'
                if isinstance(prompt, dict):
                    return prompt.get("ja", prompt.get("en", default or ""))
                # If prompt is a string, assume it's Japanese (since we hardcode)
                elif prompt is not None:
                    return prompt
                else:
                    return default or ""
            else:
                # Fallback to English or default
                if isinstance(prompt, dict):
                    return prompt.get(language, prompt.get("en", default or ""))
                elif prompt is not None:
                    return prompt
                else:
                    return default or ""
        except Exception as e:
            logger.error(f"Error getting prompt {category}/{name}: {e}")
            return default or ""

    def get_system_prompt(self, category: str, language: str = 'en', variables: Optional[Dict[str, Any]] = None) -> str:
        """Get a formatted system prompt with variable substitution and language support"""
        main_prompt = self.get_prompt(category, "main_system_prompt", language)
        if not main_prompt:
            return self._get_default_prompt(category, language)
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

    def get_conversational_config(self, language: str = 'en') -> Dict[str, Any]:
        """Get conversational configuration from prompts, always Japanese if language is 'ja'"""
        try:
            personality_config = self.get_prompt("conversational_agent", "personality_config", language, "{}")
            industry_contexts = self.get_prompt("conversational_agent", "industry_contexts", language, "{}")
            response_guidelines = self.get_prompt("conversational_agent", "response_guidelines", language, "{}")
            return {
                "personality": json.loads(personality_config),
                "industry_responses": json.loads(industry_contexts),
                "response_guidelines": json.loads(response_guidelines)
            }
        except Exception as e:
            logger.error(f"Error loading conversational config: {e}")
            return {}

    def update_conversational_config(self, config_type: str, config_data: Dict[str, Any]) -> bool:
        """Update conversational configuration (Japanese only if language is 'ja')"""
        try:
            # Always update the Japanese config for coherence
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

    def save_prompt(self, category: str, name: str, content: str):
        """Save a prompt (overwrites for Japanese if language is 'ja')"""
        if (not self._last_loaded or 
            (datetime.now() - self._last_loaded).total_seconds() > 300):
            self.load_prompts()
        if category not in self._prompts_cache:
            self._prompts_cache[category] = {}
        self._prompts_cache[category][name] = content
        self._save_prompts()

    def _get_default_prompt(self, category: str, language: str = 'en') -> str:
        """Get default fallback prompts (Japanese if language is 'ja')"""
        default_prompts_ja = {
            "sales_agent": """あなたはB2Bテクノロジー営業のエキスパートです。お客様のビジネス課題や意思決定プロセスを深く理解し、最適なソリューションを提案してください。

【営業の原則】
- オープンな質問でニーズを引き出す
- 傾聴し、課題を共感的に受け止める
- ニーズに合った解決策を提示
- 実績や事例を活用して信頼を構築
- 価値訴求で導入意欲を高める
- 次のステップを明確に提案

会話はプロフェッショナルかつ親しみやすく、業界用語も適宜使い分けてください。""",

            "quote_generation": get_quote_translations("ja")["quote_prompt"],

            "conversation_flow": """あなたは営業会話のフロー分析の専門家です。会話内容から以下を判断してください。

1. 現在の営業プロセスの段階
2. 情報の充足度
3. 次のステップへの準備状況
4. 不足している情報
5. 推奨アクション

営業プロセスを前進させるための具体的なアドバイスを提供してください。""",

            "product_retriever": """あなたは製品レコメンドのスペシャリストです。お客様の要件に基づき、最適な製品やソリューションを提案してください。

【注力ポイント】
1. お客様のニーズを深く理解
2. 要件に合致する製品を選定
3. メリットや価値を分かりやすく説明
4. 予算や制約も考慮
5. 必要に応じて代替案も提案

常にお客様に最適な選択肢を案内してください。""",

            "discovery": """あなたはB2Bテクノロジー営業のディスカバリー（課題・要件ヒアリング）に特化したコンサルタントです。

【主な役割】
1. 🔍 ビジネス課題や技術要件を丁寧にヒアリング
2. 🎯 意思決定プロセス・導入時期・予算を確認
3. 🤝 専門性と誠実さで信頼を構築
4. 💡 ニーズを十分に理解した上でソリューションを案内
5. 📊 見積もりや価格提示は十分な情報収集後に行う

お客様の真の課題を理解し、最適な提案につなげてください。"""
        }
        default_prompts_en = {
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

            "quote_generation": get_quote_translations("en")["quote_prompt"],

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
        if language == "ja":
            return default_prompts_ja.get(category, "あなたは親切なAIアシスタントです。")
        else:
            return default_prompts_en.get(category, "You are a helpful AI assistant.")

# Create global instance
prompt_manager = PromptManager()

def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance"""
    return prompt_manager