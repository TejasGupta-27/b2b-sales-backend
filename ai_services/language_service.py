import langdetect
from langdetect import detect, detect_langs
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class LanguageService:
    def __init__(self):
        # Supported languages mapping
        self.supported_languages = {
            'en': {'name': 'English', 'code': 'en'},
            'ja': {'name': 'Japanese', 'code': 'ja'}
        }
        
    def detect_language(self, text: str) -> Dict:
        """
        Detect primary and secondary language from text
        Returns: {
            'primary_language': 'en',
            'secondary_language': 'ja', 
            'confidence': 0.95,
            'all_detected': [...]
        }
        """
        try:
            # Detect all languages with probabilities
            detected = detect_langs(text)
            
            # Filter for supported languages only
            supported_detected = [
                lang for lang in detected 
                if lang.lang in self.supported_languages
            ]
            
            if not supported_detected:
                return self._default_language_response()
                
            primary = supported_detected[0]
            secondary = supported_detected[1] if len(supported_detected) > 1 else None
            
            return {
                'primary_language': primary.lang,
                'primary_confidence': primary.prob,
                'secondary_language': secondary.lang if secondary else None,
                'secondary_confidence': secondary.prob if secondary else 0,
                'all_detected': [{'lang': lang.lang, 'prob': lang.prob} for lang in supported_detected]
            }
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return self._default_language_response()
    
    def _default_language_response(self):
        return {
            'primary_language': 'en',
            'primary_confidence': 1.0,
            'secondary_language': None,
            'secondary_confidence': 0,
            'all_detected': []
        }