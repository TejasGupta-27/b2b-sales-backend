import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from ai_services.simple_conversational_agent import SimpleConversationalAgent
from ai_services.language_service import LanguageService
from ai_services.quote_generation_agent import QuoteGenerationAgent
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_multilingual_agent():
    """Test multilingual capabilities of SimpleConversationalAgent."""

    # Mock dependencies
    base_provider = MagicMock()
    base_provider.generate_structured_response = AsyncMock()
    base_provider.generate_response = AsyncMock()
    language_service = LanguageService()
    quote_agent = QuoteGenerationAgent(base_provider, "en")

    # Initialize the agent
    agent = SimpleConversationalAgent(base_provider, language="en")
    agent.language_service = language_service
    agent.quote_agent = quote_agent

    # Mock language detection
    language_service.detect_language = MagicMock(return_value={"primary_language": "ja"})

    # Mock quote generation
    quote_agent.format_quote_response = MagicMock(return_value="見積もりの詳細はこちらです。")

    # Test cases
    test_cases = [
        {"input": "Can you provide a quote for laptops?", "expected_language": "en", "expected_response": "Perfect! I've put together a detailed quote based on our discussion."},
        {"input": "ノートパソコンの見積もりをお願いします。", "expected_language": "ja", "expected_response": "見積もりの詳細はこちらです。"},
        {"input": "I need product recommendations for gaming PCs.", "expected_language": "en", "expected_response": "🔍 Retrieving products using LLM-enhanced hybrid search..."},
        {"input": "ゲーミングPCのおすすめを教えてください。", "expected_language": "ja", "expected_response": "🔍 Retrieving products using LLM-enhanced hybrid search..."},
    ]

    for case in test_cases:
        # Simulate user messages
        messages = [
            {"role": "user", "content": case["input"]}
        ]

        # Run the agent's response generation
        response = await agent.generate_response(messages)

        # Validate language detection
        detected_language = agent.language
        assert detected_language == case["expected_language"], f"Expected language {case['expected_language']}, but got {detected_language}"

        # Validate response content
        assert case["expected_response"] in response.content, f"Expected response to contain '{case['expected_response']}', but got '{response.content}'"
