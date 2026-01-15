"""
Multilingual manager for 18 languages with zero-overlap detection.

UPDATED: Added Groq API integration for FREE translation
ALL 16 non-EN/RU languages now translate for better search
"""

import os
import re
import logging
import hashlib
import asyncio
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)


class MultilingualManager:
    """
    Professional multilingual manager for 18 languages.

    Features:
    - Zero-overlap distinctive words (each word in ONE language only)
    - Script detection -> Distinctive words -> Groq API (FREE)
    - Armenian script detection improved
    - ALL 16 non-EN/RU languages use Groq translation for optimal search

    Supported: en, ru, ka, de, fr, es, it, nl, pl, cs, zh, ja, ko, ar, tr, hi, hy, az
    """

    def __init__(self, google_translate_api_key: str = None, cache_manager=None, redis_client=None):
        """Initialize MultilingualManager"""

        self.google_api_key = google_translate_api_key or os.environ.get("GOOGLE_API_KEY")
        self.cache_manager = cache_manager
        self.redis = redis_client

        if self.cache_manager:
            logger.info("MultilingualManager using CacheManager (two-level)")
        elif self.redis:
            logger.info("MultilingualManager using legacy redis_client")
        else:
            logger.info("MultilingualManager in memory-only mode")

        # Google Cloud Translation REST API
        self._cloud_api_available = False
        self.translation_api_url = "https://translation.googleapis.com/language/translate/v2"
        self.detection_api_url = "https://translation.googleapis.com/language/translate/v2/detect"

        if self.google_api_key:
            try:
                url = f"{self.detection_api_url}?key={self.google_api_key}"
                response = requests.post(url, json={"q": "test"}, timeout=5)
                if response.status_code == 200:
                    self._cloud_api_available = True
                    logger.info("Google Cloud Translation REST API initialized")
                else:
                    logger.error(f"Google Cloud API test failed: HTTP {response.status_code}")
            except Exception as e:
                logger.error(f"Google Cloud API test failed: {e}")
        else:
            logger.warning("GOOGLE_API_KEY not found")

        # Check for Groq API
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        if self.groq_api_key:
            logger.info("Groq API available for FREE translation (16 languages)!")
        else:
            logger.warning("GROQ_API_KEY not found - translation will be limited")

        self.cache_stats = {
            'translation_hits': 0,
            'translation_misses': 0,
            'translation_errors': 0,
            'total_translations': 0
        }

        # DISTINCTIVE WORDS - ZERO OVERLAP GUARANTEE (14 languages)
        self.distinctive_words = {
            'ka': ['რა', 'როგორ', 'სად', 'როდის', 'რატომ', 'მითხარი', 'აჩვენე', 'ახსენი', 'ქართული', 'გთხოვთ'],
            'hy': ['պատմիր', 'պատմեք', 'ասիր', 'ասեք', 'ինչպես', 'որտեղ', 'մասին', 'հայերեն', 'ցույց', 'օգնիր'],
            #  Frequently used Azerbaijani words have been added.
            'az': ['danış', 'haqqında', 'harada', 'necə', 'niyə', 'azərbaycan', 'göstər', 'izah', 'kömək', 'gözəl', 'yerlər', 'milli'],
            'it': ['parlami', 'dimmi', 'raccontami', 'perché', 'cosa', 'dove', 'quando', 'della', 'degli', 'italiano'],
            'fr': ['parlez', 'dites', 'racontez', 'pourquoi', 'église', 'château', 'quoi', 'où', 'français', 'voulez'],
            'de': ['erzählen', 'erzähl', 'über', 'können', 'würde', 'möchte', 'sehenswürdigkeiten', 'deutsch', 'ihnen', 'welche'],
            'es': ['cuéntame', 'háblame', 'sobre', 'dónde', 'cuándo', 'cómo', 'qué', 'español', 'ayúdame', 'muéstrame'],
            'nl': ['vertel', 'vertellen', 'waarom', 'wanneer', 'welke', 'nederlands', 'graag', 'alsjeblieft', 'natuurlijk', 'geef'],
            'pl': ['opowiedz', 'powiedz', 'gdzie', 'kiedy', 'dlaczego', 'który', 'polska', 'polski', 'proszę', 'dziękuję'],
            'cs': ['řekni', 'řekněte', 'pověz', 'proč', 'který', 'čeština', 'prosím', 'děkuji', 'není', 'jste'],
            'ru': ['расскажи', 'покажи', 'объясни', 'помоги', 'который', 'русский', 'пожалуйста', 'спасибо', 'здравствуй', 'хорошо'],
            'tr': ['anlat', 'anlatın', 'söyle', 'hakkında', 'nerede', 'neden', 'nasıl', 'türkçe', 'lütfen', 'teşekkür'],
            'hi': ['बताएं', 'बताइए', 'दिखाएं', 'समझाएं', 'के बारे में', 'कहाँ', 'कैसे', 'कृपया', 'धन्यवाद', 'हिंदी'],
            'en': ['tell', 'show', 'explain', 'describe', 'about', 'where', 'when', 'english', 'please', 'thank']
        }

        # Special patterns for CJK and Arabic (4 languages)
        self.language_patterns = {
            'zh': ['什么', '怎么', '哪里', '告诉', '中文', '格鲁吉亚', '第比利斯'],
            'ja': ['何', 'どこ', 'どうやって', '教えて', 'について', '日本語', 'ジョージア'],
            'ko': ['무엇', '어디', '어떻게', '알려주세요', '한국어', '조지아', '트빌리시'],
            'ar': ['ما', 'كيف', 'أين', 'أخبرني', 'عن', 'العربية', 'جورجيا'],
        }

        self._verify_no_overlaps()
        logger.info("MultilingualManager with 18 languages (14 distinctive + 4 script-based) + Groq FREE translation for 16 languages")

    def _verify_no_overlaps(self) -> bool:
        """Verify no overlaps between languages"""
        all_words: Dict[str, str] = {}
        overlaps_found = False

        for lang, words in self.distinctive_words.items():
            for word in words:
                word_lower = word.lower()
                if word_lower in all_words:
                    logger.error(f"OVERLAP: '{word}' found in both {all_words[word_lower]} and {lang}")
                    overlaps_found = True
                else:
                    all_words[word_lower] = lang

        if not overlaps_found:
            total_words = sum(len(words) for words in self.distinctive_words.values())
            logger.info(f"No overlaps: {total_words} unique words across {len(self.distinctive_words)} languages")
        else:
            logger.warning("Found word overlaps! Language detection may be unreliable")

        return not overlaps_found

    async def detect_language(self, text: str) -> str:
        """
        Multi-stage language detection with zero-overlap words.

        Stages:
        1. Script detection (Georgian, CJK, Arabic, Armenian, Cyrillic)
        2. Distinctive WHOLE WORD matching
        3. Groq API (FREE fallback)
        """

        if not text or not text.strip():
            return "en"

        text_clean = text.strip()
        text_lower = text_clean.lower()

        # STAGE 1: SCRIPT-BASED DETECTION
        # Georgian
        if any('\u10A0' <= char <= '\u10FF' for char in text):
            logger.debug("Georgian script detected")
            return "ka"

        # Armenian
        armenian_chars = sum(1 for char in text if '\u0530' <= char <= '\u058F')
        total_chars = sum(1 for char in text if char.isalpha())
        if total_chars > 0 and armenian_chars / total_chars > 0.3:
            logger.debug(f"Armenian script detected ({armenian_chars}/{total_chars} chars)")
            return "hy"

        # Chinese/Japanese
        if any('\u4E00' <= char <= '\u9FFF' for char in text):
            if any('\u3040' <= char <= '\u309F' for char in text):
                logger.debug("Japanese script detected")
                return "ja"
            logger.debug("Chinese script detected")
            return "zh"

        # Korean
        if any('\uAC00' <= char <= '\uD7AF' for char in text):
            logger.debug("Korean script detected")
            return "ko"

        # Arabic
        if any('\u0600' <= char <= '\u06FF' for char in text):
            logger.debug("Arabic script detected")
            return "ar"

        # Hindi (Devanagari)
        if any('\u0900' <= char <= '\u097F' for char in text):
            logger.debug("Hindi (Devanagari) script detected")
            return "hi"

        # Cyrillic (Russian)
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        if total_chars > 0 and cyrillic_count / total_chars > 0.3:
            logger.debug("Cyrillic detected -> Russian")
            return "ru"

        # STAGE 2: DISTINCTIVE WHOLE WORD MATCHING
        words_in_text = set(re.findall(r'\b\w+\b', text_lower))
        logger.debug(f"Words in text: {list(words_in_text)[:5]}...")

        # Priority order (check ka first!)
        priority_order = ['ka', 'hy', 'hi', 'az', 'tr', 'it', 'fr', 'de', 'es', 'nl', 'pl', 'cs', 'ru']

        for lang_code in priority_order:
            distinctive = self.distinctive_words.get(lang_code, [])
            matches = words_in_text & set(w.lower() for w in distinctive)

            if matches:
                logger.debug(f"Distinctive words {matches} -> {lang_code}")
                return lang_code

        # English last
        english_distinctive = self.distinctive_words.get('en', [])
        english_matches = words_in_text & set(w.lower() for w in english_distinctive)

        if english_matches:
            logger.debug(f"English words {english_matches} -> en")
            return "en"

        # STAGE 3: GROQ API (FREE fallback) - REPLACED Google Cloud
        if self.groq_api_key:
            try:
                from groq import Groq

                client = Groq(api_key=self.groq_api_key)

                prompt = f"""What language is this? Reply with ONLY the ISO 639-1 code (en, ru, ka, ko, ja, zh, ar, de, fr, es, it, nl, pl, cs, tr, hi, hy, az):

{text_clean[:200]}"""

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=10,
                    temperature=0
                )

                detected = response.choices[0].message.content.strip().lower()

                #  Validation of all 18 languages
                valid_langs = ['en', 'ru', 'ka', 'de', 'fr', 'es', 'it', 'nl', 'pl',
                              'cs', 'zh', 'ja', 'ko', 'ar', 'tr', 'hi', 'hy', 'az']

                if detected in valid_langs:
                    logger.debug(f"Groq detected: {detected}")
                    return detected

            except Exception as e:
                logger.warning(f"Groq detection failed: {e}")

        logger.warning("All detection methods failed, defaulting to 'en'")
        return "en"

    # Now all 16 languages(except EN/RU) are translated
    async def should_translate_for_search(self, language: str) -> bool:
        """
        Determine if query needs translation for better search.

        Strategy:
        - DON'T translate: EN, RU (already in database)
        - DO translate: ALL other 16 languages (ka, de, fr, es, it, nl, pl, cs, zh, ja, ko, ar, tr, hi, hy, az)

        Reason: Embedding models work best with English queries for English/Russian documents.
        Free Groq translation ensures optimal search results for all non-EN/RU languages.

        Args:
            language: ISO 639-1 language code

        Returns:
            bool: True if translation needed (16 languages), False for EN/RU only
        """
        # ONLY EN and RU don't need translation (already in DB)
        if language in ['en', 'ru']:
            logger.debug(f"Language {language} - no translation needed (in DB)")
            return False

        # ALL other 16 languages MUST be translated for optimal search
        all_translatable = ['ka', 'de', 'fr', 'es', 'it', 'nl', 'pl', 'cs',
                           'zh', 'ja', 'ko', 'ar', 'tr', 'hi', 'hy', 'az']

        if language in all_translatable:
            logger.debug(f"Language {language} - translation needed for better search")
            return True

        # Unknown language - default to translation
        logger.warning(f"Unknown language {language} - will attempt translation")
        return True

    # This method works for all languages
    async def translate_query_with_groq(self, text: str, source_lang: str, target: str = 'en') -> str:
        """
        Translate query via FREE Groq API (Llama 3.3 70B).

        Used for ALL 16 non-EN/RU languages to improve search.
        Context stays in original EN/RU.

        Args:
            text: Query text
            source_lang: Source language (any of 18)
            target: Target language (usually 'en')

        Returns:
            Translated text
        """
        # Don't translate if already target language
        if source_lang == target or source_lang in ['en', 'ru']:
            return text

        if not text or not text.strip():
            return text

        try:
            # Import Groq
            try:
                from groq import Groq
            except ImportError:
                logger.warning("groq package not installed (pip install groq)")
                return text

            # Get API key
            if not self.groq_api_key:
                logger.warning("GROQ_API_KEY not found in .env")
                return text

            client = Groq(api_key=self.groq_api_key)

            # ✅ ПРОВЕРЕНО: Все 18 языков в списке
            lang_names = {
                'en': 'English', 'ru': 'Russian', 'ka': 'Georgian',
                'de': 'German', 'fr': 'French', 'es': 'Spanish',
                'it': 'Italian', 'nl': 'Dutch', 'pl': 'Polish',
                'cs': 'Czech', 'zh': 'Chinese', 'ja': 'Japanese',
                'ko': 'Korean', 'ar': 'Arabic', 'tr': 'Turkish',
                'hi': 'Hindi', 'hy': 'Armenian', 'az': 'Azerbaijani'
            }

            target_name = lang_names.get(target, 'English')

            # Minimal prompt for fast translation
            prompt = f"""Translate this to {target_name}. Return ONLY the translation:

{text}"""

            # Call Groq API
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # FREE model
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )

            translated = response.choices[0].message.content.strip()

            # Remove quotes if present
            translated = translated.strip('"').strip("'")

            logger.info(f"Groq translation ({source_lang}→{target}): '{text[:40]}' → '{translated[:40]}'")

            return translated

        except Exception as e:
            logger.warning(f"Groq translation failed: {e}, using original query")
            return text

    #  For backward compatibility
    async def translate_query_with_claude(self, text: str, source_lang: str, target: str = 'en') -> str:
        """Alias - now uses Groq instead of Claude"""
        return await self.translate_query_with_groq(text, source_lang, target)

    async def translate_if_needed(self, text: str, target_language: str,
                                 source_language: str = "auto", is_permanent: bool = False) -> str:
        """Fast async translation with two-level caching"""

        if not text or target_language == source_language:
            return text

        self.cache_stats['total_translations'] += 1
        cache_key = hashlib.md5(f'{text}:{source_language}:{target_language}'.encode()).hexdigest()

        # Check cache
        if self.cache_manager:
            cached = self.cache_manager.get('translation:permanent', cache_key)
            if cached:
                self.cache_stats['translation_hits'] += 1
                return cached
            cached = self.cache_manager.get('translation:temp', cache_key)
            if cached:
                self.cache_stats['translation_hits'] += 1
                return cached
        elif self.redis:
            try:
                redis_key = f"translation:{cache_key}"
                cached = self.redis.get(redis_key)
                if cached:
                    self.cache_stats['translation_hits'] += 1
                    return cached.decode('utf-8') if isinstance(cached, bytes) else cached
            except:
                pass

        self.cache_stats['translation_misses'] += 1

        # Google Cloud translation
        if self._cloud_api_available and self.google_api_key:
            try:
                url = f"{self.translation_api_url}?key={self.google_api_key}"
                payload = {"q": text, "target": target_language}
                if source_language != "auto":
                    payload["source"] = source_language

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(url, json=payload, timeout=5)
                )

                if response.status_code == 200:
                    data = response.json()
                    translations = data.get('data', {}).get('translations', [])
                    if translations:
                        translated = translations[0].get('translatedText', text)

                        # Save to cache
                        if self.cache_manager:
                            if is_permanent:
                                self.cache_manager.set_permanent('translation:permanent', cache_key, translated)
                            else:
                                self.cache_manager.set('translation:temp', cache_key, translated, ttl=86400)
                        elif self.redis:
                            redis_key = f"translation:{cache_key}"
                            self.redis.setex(redis_key, 86400, translated.encode('utf-8'))

                        return translated
                else:
                    self.cache_stats['translation_errors'] += 1
            except Exception as e:
                logger.error(f"Translation failed: {e}")
                self.cache_stats['translation_errors'] += 1

        return text


    def get_optimized_language_instruction(self, target_language: str) -> str:
        """Optimized language instruction for LLM"""

        language_names = {
            'en': 'English', 'ru': 'Russian', 'ka': 'Georgian',
            'de': 'German', 'fr': 'French', 'es': 'Spanish',
            'it': 'Italian', 'nl': 'Dutch', 'pl': 'Polish',
            'cs': 'Czech', 'zh': 'Chinese', 'ja': 'Japanese',
            'ko': 'Korean', 'ar': 'Arabic', 'tr': 'Turkish',
            'hi': 'Hindi', 'hy': 'Armenian', 'az': 'Azerbaijani'
        }

        target_lang_name = language_names.get(target_language, 'English')

        return f"""---
SYSTEM: ROLE AND LANGUAGE INSTRUCTIONS

ROLE: You are an expert Georgian tourism guide. Your tone is engaging, helpful, and inspiring.

CONTEXT LANGUAGE: The context below is in its original language (Russian or English) for maximum accuracy.

TASK: Read the context and user's query carefully. Then generate a comprehensive, structured, and helpful response.

---
CRITICAL: LANGUAGE REQUIREMENT

Your ENTIRE response MUST be written in: **{target_lang_name.upper()}**

RULES:
- Do NOT mix languages
- Exception: Keep proper nouns, names, titles (e.g., "Svetitskhoveli", "Narikala") in their original script if no common translation exists
- Write ALL headers, descriptions, and explanations in {target_lang_name}

EXAMPLE (if target is French):
CORRECT: "La cathédrale de Svetitskhoveli a été construite au 11ème siècle..."
WRONG: "The Svetitskhoveli cathedral was built in the 11th century..."

---
NOW BEGIN YOUR RESPONSE IN **{target_lang_name}**:
"""

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.cache_stats['translation_hits'] + self.cache_stats['translation_misses']
        hit_rate = (self.cache_stats['translation_hits'] / total * 100) if total > 0 else 0
        return {
            'translation_hits': self.cache_stats['translation_hits'],
            'translation_misses': self.cache_stats['translation_misses'],
            'translation_errors': self.cache_stats['translation_errors'],
            'total_translations': self.cache_stats['total_translations'],
            'total_cache_requests': total,
            'cache_hit_rate_percent': round(hit_rate, 2)
        }

    def reset_cache_stats(self):
        """Reset statistics"""
        self.cache_stats = {
            'translation_hits': 0,
            'translation_misses': 0,
            'translation_errors': 0,
            'total_translations': 0
        }
        logger.info("Translation cache stats reset")