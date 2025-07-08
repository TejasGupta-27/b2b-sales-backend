# Multilingualism Handling in B2B Sales Backend

This document outlines how multilingualism is managed across the B2B sales backend, ensuring robust language detection, translation, and dynamic language switching.

## Key Components

### 1. Language Detection
- **Service**: `services/language_service.py`
- **Description**: Detects the primary and secondary languages of user input using `langdetect`.
- **Features**:
  - Confidence threshold for reliable detection.
  - Multilingual detection support.
  - Default language fallback when detection fails.

### 2. Translation Retrieval
- **Service**: `services/localisation.py`
- **Description**: Provides translations for various keys and supports fallback to English if a translation is missing.
- **Key Functions**:
  - `get_translation(key, language, fallback=True)`: Retrieves a specific translation key for the given language.
  - `get_quote_translations(language, fallback=True)`: Retrieves quote-specific translations.

### 3. Dynamic Language Switching
- **Service**: `ai_services/simple_conversational_agent.py`
- **Description**: Dynamically switches the language of the agent and its dependent components (e.g., `quote_agent`, `hybrid_retriever`) based on user input.
- **Key Method**:
  - `detect_and_switch_language(messages)`: Detects the language of the latest user message and updates the agent's language.

### 4. Multilingual PDF Generation
- **Service**: `services/pdf_generator.py`
- **Description**: Generates PDFs with multilingual support, including localized labels and font registration for non-Latin scripts.
- **Key Method**:
  - `update_styles_for_language(language)`: Updates styles dynamically based on the language.

### 5. Testing and Validation
- **Script**: `scripts/test_ppt_link_fix.py`
- **Description**: Validates translation retrieval and ensures proper handling of multilingual responses.
- **Key Test**:
  - `test_translations()`: Tests that translations are properly loaded for different languages.

## Best Practices
- Centralize all translation logic in `services/localisation.py`.
- Use `LanguageService` for consistent language detection across components.
- Ensure fallback mechanisms are in place for unsupported or missing translations.
- Regularly test multilingual features using dedicated scripts.

## Future Improvements
- Consolidate font and style logic for PDF and PPT generation to reduce redundancy.
- Expand support for additional languages and scripts.
- Enhance logging for better monitoring of multilingual operations.

---

For any issues or suggestions, please contact the development team.
