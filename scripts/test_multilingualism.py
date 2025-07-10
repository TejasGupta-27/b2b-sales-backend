import os
from langdetect import detect, detect_langs
from services.localisation import get_translation
from services.language_service import LanguageService

# Initialize LanguageService
language_service = LanguageService()

def test_language_detection():
    print("\n🔍 Testing Language Detection")
    test_cases = [
        "Hello, how are you?",  # English
        "こんにちは、お元気ですか？",  # Japanese
        "Hola, ¿cómo estás?",  # Spanish
        "",  # Empty input
        "12345",  # Numbers only
        "Hello こんにちは",  # Mixed languages
    ]

    for text in test_cases:
        result = language_service.detect_language(text)
        print(f"Input: {text}\nResult: {result}\n")

def test_translation_retrieval():
    print("\n🌐 Testing Translation Retrieval")
    test_keys = ["quote_prompt", "non_existent_key"]
    languages = ["en", "ja", "es"]

    for key in test_keys:
        for lang in languages:
            translation = get_translation(key, lang)
            print(f"Key: {key}, Language: {lang}, Translation: {translation}")

def test_dynamic_language_switching():
    print("\n🔄 Testing Dynamic Language Switching")
    messages = [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "user", "content": "こんにちは、お元気ですか？"},
        {"role": "user", "content": "Hola, ¿cómo estás?"},
    ]

    current_language = "en"
    for message in messages:
        detection_result = language_service.detect_language(message["content"])
        detected_language = detection_result.get("primary_language", current_language)

        if detected_language != current_language:
            print(f"Switching language from {current_language} to {detected_language}")
            current_language = detected_language
        else:
            print(f"Language remains {current_language}")

if __name__ == "__main__":
    test_language_detection()
    test_translation_retrieval()
    test_dynamic_language_switching()
