"""
Localization service for quote generation
Provides translations for different languages with hybrid detection support
"""

# Translation dictionary for quote generation
quote_translations = {
    "en": {
        "intro": "🎯 **Excellent! Based on our thorough discussion and your specific requirements, I've prepared a comprehensive, customized quote using our intelligent product matching system.**",
        "quote_number": "📋 **Quote #{quote_number}**",
        "analysis": "✅ **Complete Requirements Analysis:** Our conversation covered all the essential areas needed for an accurate quote - your business context, technical requirements, operational needs, and specific challenges.",
        "ai_confidence": "🤖 **AI-Powered Recommendations:** Our system identified a {confidence:.1%} match with your requirements based on our comprehensive product intelligence!",
        "investment_summary": "💰 **Investment Summary:**",
        "subtotal": "• Subtotal: **${subtotal:,.2f}**",
        "tax": "• Tax: ${tax:,.2f}",
        "total": "• **Total Investment: ${total:,.2f}**",
        "valid_until": "• Quote valid until: {date}",
        "pdf_ready": "📄 **[Download Complete Quote PDF]({url})**",
        "pdf_pending": "📄 **Quote PDF:** Currently being generated...",
        "pdf_error": " (Note: PDF generation encountered an issue - please contact support if needed)",
        "ppt_ready": "📊 **[Download Pitch Deck]({url})**",
        "next_steps": "**Next Steps:**",
        "next_with_ppt": [
            "1. Review the detailed quote with all selected products and solutions",
            "2. Check out the pitch deck for a visual overview of the solution",
            "3. Let me know if you'd like to discuss any aspects in more detail",
            "4. I can arrange product demos or technical consultations if helpful",
            "5. We can finalize implementation timeline and support arrangements"
        ],
        "next_without_ppt": [
            "1. Review the detailed quote with all selected products and solutions",
            "2. Let me know if you'd like to discuss any aspects in more detail",
            "3. I can arrange product demos or technical consultations if helpful",
            "4. We can finalize implementation timeline and support arrangements"
        ],
        "confidence_note": "This quote reflects our thorough understanding of your business needs and technical requirements. I'm confident these recommendations will deliver the performance and value you're looking for! 🚀",
        # PDF Labels
        "pdf_labels": {
            "quote_number": "Quote Number:",
            "date": "Date:",
            "valid_until": "Valid Until:",
            "customer_information": "Customer Information",
            "company": "Company:",
            "contact": "Contact:",
            "email": "Email:",
            "phone": "Phone:",
            "quote_details": "Quote Details",
            "item": "Item",
            "description": "Description",
            "qty": "Qty",
            "unit_price": "Unit Price",
            "total": "Total",
            "subtotal": "Subtotal:",
            "tax": "Tax:",
            "total_amount": "Total:",
            "terms_and_conditions": "Terms and Conditions",
            "implementation_notes": "Implementation Notes",
            "next_steps": "Next Steps"
        },
        # Quote generation prompts
        "quote_prompt": """Based on this sales conversation, generate a complete structured quote.

CONVERSATION:
{conversation_text}

CUSTOMER CONTEXT:
{safe_context}

Generate a complete quote with:
1. Customer information extracted from conversation
2. 2-5 most relevant products based on their needs (use realistic technology products)
3. Professional pricing with subtotal, tax, and total
4. Business context explaining why these products fit
5. Professional terms and conditions
6. Implementation notes and next steps
7. Professional quote title and company tagline

Make sure all prices are realistic and the quote looks professional. If specific products weren't mentioned, suggest appropriate technology solutions based on the conversation context. Set language to English."""
    },
    "ja": {
        "intro": "🎯 **鈴木様との丁寧なヒアリングをもとに、最適な提案書をご用意しました。**",
        "quote_number": "📋 **見積番号: {quote_number}**",
        "analysis": "✅ **要件整理:** ご要望・課題・技術条件を十分にヒアリングし、必要な項目をすべてカバーしております。",
        "ai_confidence": "🤖 **AIレコメンド:** ご要望に対する一致度: {confidence:.1%}",
        "investment_summary": "💰 **費用サマリー:**",
        "subtotal": "• 小計: **¥{subtotal:,.0f}**",
        "tax": "• 税金: ¥{tax:,.0f}",
        "total": "• **合計費用: ¥{total:,.0f}**",
        "valid_until": "• 有効期限: {date}",
        "pdf_ready": "📄 **[見積PDFをダウンロード]({url})**",
        "pdf_pending": "📄 **見積PDF:** 現在生成中です...",
        "pdf_error": "（※PDF生成に失敗しました。問題が続く場合はサポートまでご連絡ください）",
        "ppt_ready": "📊 **[提案スライドをダウンロード]({url})**",
        "next_steps": "**次のステップ:**",
        "next_with_ppt": [
            "1. 見積内容をご確認ください",
            "2. 提案資料をご覧ください",
            "3. ご不明点があればお気軽にご相談ください",
            "4. 製品デモや技術説明も承ります",
            "5. 導入スケジュールやサポート体制の最終調整を行いましょう"
        ],
        "next_without_ppt": [
            "1. 見積内容をご確認ください",
            "2. ご不明点があればお気軽にご相談ください",
            "3. 製品デモや技術説明も承ります",
            "4. 導入スケジュールやサポート体制の最終調整を行いましょう"
        ],
        "confidence_note": "この見積もりは、貴社の課題と技術要件に対する深い理解に基づいています。🚀",
        # PDF Labels in Japanese
        "pdf_labels": {
            "quote_number": "見積番号:",
            "date": "発行日:",
            "valid_until": "有効期限:",
            "customer_information": "お客様情報",
            "company": "会社名:",
            "contact": "ご担当者:",
            "email": "メールアドレス:",
            "phone": "電話番号:",
            "quote_details": "見積詳細",
            "item": "商品名",
            "description": "商品説明",
            "qty": "数量",
            "unit_price": "単価",
            "total": "小計",
            "subtotal": "小計:",
            "tax": "消費税:",
            "total_amount": "合計:",
            "terms_and_conditions": "契約条件",
            "implementation_notes": "導入に関して",
            "next_steps": "次のステップ"
        },
        # Quote generation prompts in Japanese
        "quote_prompt": """この営業会話に基づいて、完全な構造化見積もりを生成してください。

会話内容:
{conversation_text}

顧客コンテキスト:
{safe_context}

以下を含む完全な見積もりを生成してください:
1. 会話から抽出した顧客情報
2. ニーズに基づく2-5の最適な製品（現実的な技術製品を使用）
3. 小計、税金、合計を含む適切な価格設定
4. これらの製品が適している理由を説明するビジネスコンテキスト
5. 専門的な契約条件
6. 導入に関する注意事項と次のステップ
7. 専門的な見積もりタイトルと会社キャッチフレーズ

すべての価格は現実的で、見積もりが専門的に見えるようにしてください。特定の製品が言及されていない場合は、会話のコンテキストに基づいて適切な技術ソリューションを提案してください。言語は日本語に設定してください。"""
    }
}

def get_quote_translations(language: str, fallback: bool = True) -> dict:
    """
    Get quote translations for specified language with fallback support
    
    Args:
        language: Target language code
        fallback: Whether to fallback to English if language not found
    
    Returns:
        Dictionary containing translations for the language
    """
    # Direct lookup
    if language in quote_translations:
        return quote_translations[language]
    
    # Fallback to English if enabled
    if fallback and language != 'en':
        logger.warning(f"⚠️ Language '{language}' not found, falling back to English")
        return quote_translations.get('en', {})
    
    # Return empty dict if no fallback
    logger.error(f"❌ Language '{language}' not found and no fallback enabled")
    return {}

def get_supported_languages() -> list:
    """Get list of supported language codes"""
    return list(quote_translations.keys())

def detect_language_from_content(content: str) -> str:
    """
    Simple content-based language detection fallback
    
    Args:
        content: Text content to analyze
        
    Returns:
        Detected language code
    """
    if not content:
        return 'en'
    
    # Simple heuristic-based detection for common languages
    content_lower = content.lower()
    
    # Japanese detection
    japanese_chars = set('あいうえおかきくけこがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽまみむめもやゆよらりるれろわをん')
    if any(char in japanese_chars for char in content_lower):
        return 'ja'
    
    # Spanish detection
    spanish_indicators = ['señor', 'señora', 'precio', 'cotización', 'empresa', 'producto']
    if any(indicator in content_lower for indicator in spanish_indicators):
        return 'es'
    
    # French detection
    french_indicators = ['monsieur', 'madame', 'prix', 'devis', 'entreprise', 'produit']
    if any(indicator in content_lower for indicator in french_indicators):
        return 'fr'
    
    # Default to English
    return 'en'

def get_translation(key: str, language: str, fallback: bool = True) -> str:
    """Retrieve a specific translation key for the given language."""
    translations = quote_translations.get(language, {})
    if not translations and fallback:
        translations = quote_translations.get('en', {})
    return translations.get(key, f"[Missing translation for {key}]")