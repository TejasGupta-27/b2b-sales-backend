import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use mock config for testing
import tests.mock_config
sys.modules['config'] = tests.mock_config

from services.language_service import LanguageService

@pytest.fixture
def language_service():
    return LanguageService()

def test_normalize_language_code_basic(language_service):
    """Test basic language code normalization"""
    assert language_service.normalize_language_code("en") == "en"
    assert language_service.normalize_language_code("EN") == "en"
    assert language_service.normalize_language_code("en-US") == "en"
    assert language_service.normalize_language_code("en_US") == "en"

def test_normalize_language_code_chinese(language_service):
    """Test Chinese language code variants"""
    assert language_service.normalize_language_code("zh") == "zh"
    assert language_service.normalize_language_code("cn") == "zh"
    assert language_service.normalize_language_code("zh-CN") == "zh"
    assert language_service.normalize_language_code("zh_TW") == "zh"

def test_normalize_language_code_empty(language_service):
    """Test handling of empty/None language codes"""
    assert language_service.normalize_language_code("") == "en"  # default language
    assert language_service.normalize_language_code(None) == "en"  # default language

def test_normalize_language_code_unsupported(language_service):
    """Test handling of unsupported language codes"""
    assert language_service.normalize_language_code("xx") == "en"  # default language
    assert language_service.normalize_language_code("unknown") == "en"  # default language

def test_normalize_language_code_supported_languages(language_service):
    """Test all supported language codes"""
    supported = ["en", "ja", "es", "fr", "de", "it", "pt", "ko", "zh"]
    for lang in supported:
        assert language_service.normalize_language_code(lang) == lang
        assert language_service.normalize_language_code(lang.upper()) == lang
