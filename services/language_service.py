import langdetect
from langdetect import detect, detect_langs
from typing import Dict, List, Tuple, Optional
import logging
from config import settings

logger = logging.getLogger(__name__)

class LanguageService:
    def __init__(self):
        # Use centralized language configuration from settings
        self.supported_languages = {
            'en': {'name': 'English', 'code': 'en'},
            'ja': {'name': 'Japanese', 'code': 'ja'},
            'es': {'name': 'Spanish', 'code': 'es'},
            'fr': {'name': 'French', 'code': 'fr'},
            'de': {'name': 'German', 'code': 'de'},
            'it': {'name': 'Italian', 'code': 'it'},
            'pt': {'name': 'Portuguese', 'code': 'pt'},
            'ko': {'name': 'Korean', 'code': 'ko'},
            'zh': {'name': 'Chinese', 'code': 'zh'}
        }
        
        # Language detection configuration
        self.confidence_threshold = settings.LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD
        self.auto_detection_enabled = settings.ENABLE_AUTO_LANGUAGE_DETECTION
        self.default_language = settings.DEFAULT_LANGUAGE
        
        logger.info(f"🌐 LanguageService initialized with {len(self.supported_languages)} supported languages")
        
    def detect_language(self, text: str) -> Dict:
        """
        Detect primary and secondary language from text with enhanced confidence handling
        Returns: {
            'primary_language': 'en',
            'primary_confidence': 0.95,
            'secondary_language': 'ja', 
            'secondary_confidence': 0.05,
            'is_multilingual': False,
            'all_detected': [...],
            'detection_method': 'langdetect'
        }
        """
        if not self.auto_detection_enabled:
            return self._default_language_response("Auto-detection disabled")
            
        if not text or not text.strip():
            return self._default_language_response("Empty text")
            
        try:
            # Detect all languages with probabilities
            detected = detect_langs(text)
            
            # Filter for supported languages only
            supported_detected = [
                lang for lang in detected 
                if lang.lang in self.supported_languages
            ]
            
            if not supported_detected:
                logger.warning(f"⚠️ No supported languages detected in text, using default: {self.default_language}")
                return self._default_language_response("No supported languages detected")
                
            primary = supported_detected[0]
            secondary = supported_detected[1] if len(supported_detected) > 1 else None
            
            # Check if primary language meets confidence threshold
            primary_lang = primary.lang if primary.prob >= self.confidence_threshold else self.default_language
            primary_confidence = primary.prob if primary.lang == primary_lang else 1.0
            
            # Determine if text is multilingual (multiple languages with decent confidence)
            is_multilingual = (
                len(supported_detected) > 1 and 
                secondary and 
                secondary.prob > 0.3
            )
            
            result = {
                'primary_language': primary_lang,
                'primary_confidence': primary_confidence,
                'secondary_language': secondary.lang if secondary else None,
                'secondary_confidence': secondary.prob if secondary else 0.0,
                'is_multilingual': is_multilingual,
                'all_detected': [
                    {
                        'language': lang.lang, 
                        'confidence': lang.prob,
                        'name': self.supported_languages.get(lang.lang, {}).get('name', lang.lang)
                    } 
                    for lang in supported_detected
                ],
                'detection_method': 'langdetect',
                'confidence_threshold': self.confidence_threshold,
                'text_length': len(text.strip())
            }
            
            logger.debug(f"🌐 Language detection: {primary_lang} ({primary_confidence:.2f}) | "
                        f"Secondary: {secondary.lang if secondary else 'None'} "
                        f"({secondary.prob if secondary else 0:.2f}) | "
                        f"Multilingual: {is_multilingual}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Language detection failed: {e}")
            return self._default_language_response(f"Detection error: {str(e)}")
    
    def _default_language_response(self, reason: str = "Default fallback"):
        """Return default language response with metadata"""
        return {
            'primary_language': self.default_language,
            'primary_confidence': 1.0,
            'secondary_language': None,
            'secondary_confidence': 0.0,
            'is_multilingual': False,
            'all_detected': [],
            'detection_method': 'default_fallback',
            'confidence_threshold': self.confidence_threshold,
            'fallback_reason': reason,
            'text_length': 0
        }
    
    def is_supported_language(self, language_code: str) -> bool:
        """Check if a language code is supported"""
        return language_code in self.supported_languages
    
    def get_supported_languages(self) -> Dict:
        """Get all supported languages with metadata"""
        return self.supported_languages.copy()
    
    def get_language_name(self, language_code: str) -> str:
        """Get human-readable language name"""
        return self.supported_languages.get(language_code, {}).get('name', language_code) 