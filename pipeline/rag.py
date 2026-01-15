"""
Enhanced Georgian RAG - Main orchestrator with full async architecture.
Added Groq integration for free query translation
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from langsmith import traceable

logger = logging.getLogger(__name__)


# query analysis classes
class QueryIntent(Enum):
    """Query intent classification"""
    INFO_REQUEST = "info_request"
    RECOMMENDATION = "recommendation"
    ROUTE_PLANNING = "route_planning"
    FOLLOW_UP = "follow_up"
    GENERAL = "general"


@dataclass
class EnhancedQueryAnalysis:
    """Enhanced query analysis result"""
    original_query: str
    intent: QueryIntent
    detected_language: str
    target_language: str
    entities: List[str]
    preferences: List[str]
    needs_enrichment: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'original_query': self.original_query,
            'intent': self.intent.value if isinstance(self.intent, QueryIntent) else self.intent,
            'detected_language': self.detected_language,
            'target_language': self.target_language,
            'entities': self.entities,
            'preferences': self.preferences,
            'needs_enrichment': self.needs_enrichment
        }


class EnhancedGeorgianRAG:
    """
    Complete multilingual RAG system with FULLY async architecture + Groq translation.

    FEATURES:
    - Automatic language detection
    - FREE query translation via Groq (for distant languages)
    - Hybrid translation logic
    - Claude generates responses directly in user's language
    Features:
    - 18 languages support
    - FULLY ASYNC: Non-blocking search and LLM calls
    - OPTIMIZED: Direct target language generation (no translation of response)
    - Web enrichment (Wikipedia, Unsplash, SerpAPI)
    - Two-level caching (temporary + permanent)
    - Background Qdrant updates (non-blocking)
    - LangSmith tracing
    - Conversation management (multi-turn dialogues)
    - DisclaimerManager integration
    """

    def __init__(self,
                 qdrant_system=None,
                 hybrid_search_integrator=None,
                 disclaimer_manager=None,
                 api_keys: Dict[str, str] = None,
                 config: Dict = None):

        self.qdrant_system = qdrant_system
        self.hybrid_search = hybrid_search_integrator
        self.disclaimer_manager = disclaimer_manager
        self.config = config or {}

        self.api_keys = api_keys or {}
        required_keys = [
            'anthropic_api_key', 'langsmith_api_key', 'google_translate_api_key',
            'unsplash_access_key', 'serpapi_api_key'
        ]

        for key in required_keys:
            if key not in self.api_keys:
                logger.warning(f"Missing API key: {key}")

        # redis connection
        self.redis_client = None

        # try Upstash REST API first
        if 'upstash_url' in self.api_keys and 'upstash_token' in self.api_keys:
            try:
                from upstash_redis import Redis
                self.redis_client = Redis(
                    url=self.api_keys['upstash_url'],
                    token=self.api_keys['upstash_token']
                )
                self.redis_client.set("connection_test", "ok")
                logger.info("Upstash Redis (REST) connected")
            except Exception as e:
                logger.warning(f"Upstash connection failed: {e}")

        # fallback to redis_url if available
        elif 'redis_url' in self.api_keys:
            try:
                import redis
                self.redis_client = redis.from_url(self.api_keys['redis_url'])
                self.redis_client.ping()
                logger.info("Redis connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")

        # cache manager
        from utils.CacheManager import CacheManager
        self.cache_manager = CacheManager(
            redis_client=self.redis_client,
            default_ttl=86400
        )
        logger.info("CacheManager initialized")

        # background queue - assuming global queue exists
        self.background_queue = None  # will be set if available

        # enrichment persister
        self.enrichment_persister = None

        # components
        self.multilingual_manager = None
        self.web_enricher = None
        self.context_assembler = None
        self.response_generator = None
        self.conversation_manager = None

        # system state
        self.is_initialized = False

        logger.info("EnhancedGeorgianRAG initialized with Groq FREE translation support")

    async def initialize(self) -> bool:
        """Initialize all components"""
        try:
            logger.info("Initializing EnhancedGeorgianRAG...")

            # initialize Qdrant
            if self.qdrant_system and hasattr(self.qdrant_system, 'setup'):
                if hasattr(self.qdrant_system, 'setup'):
                    self.qdrant_system.setup()

            # initialize Hybrid Search
            if self.hybrid_search and hasattr(self.hybrid_search, 'initialize'):
                if not getattr(self.hybrid_search, 'is_initialized', False):
                    self.hybrid_search.initialize()

            # enrichment persister
            if self.qdrant_system:
                logger.warning("EnrichmentPersister not available yet")
            else:
                logger.warning("Qdrant not available, EnrichmentPersister not initialized")

            # multilingualManager with cache_manager
            from multilingual.multilingual_manager import MultilingualManager
            self.multilingual_manager = MultilingualManager(
                google_translate_api_key=self.api_keys.get('google_translate_api_key'),
                cache_manager=self.cache_manager
            )

            # WebEnrichmentEngine
            logger.warning("WebEnrichmentEngine not migrated yet")
            self.web_enricher = None

            # ContextAssembler
            from rag.context import EnhancedContextAssembler
            self.context_assembler = EnhancedContextAssembler(
                web_enricher=self.web_enricher,
                multilingual_manager=self.multilingual_manager
            )

            # ResponseGenerator
            from llm.generator import EnhancedResponseGenerator
            self.response_generator = EnhancedResponseGenerator(
                anthropic_api_key=self.api_keys.get('anthropic_api_key'),
                langsmith_api_key=self.api_keys.get('langsmith_api_key'),
                multilingual_manager=self.multilingual_manager,
                disclaimer_manager=self.disclaimer_manager
            )

            # ConversationManager
            from conversation.manager import ConversationManager
            self.conversation_manager = ConversationManager(
                redis_client=self.redis_client,
                max_history=20,
                ttl=86400
            )
            logger.info("ConversationManager initialized")

            # verify components
            if not self._verify_components():
                return False

            self.is_initialized = True
            logger.info("EnhancedGeorgianRAG initialization complete!")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    def _verify_components(self) -> bool:
        """Verify all components are initialized"""
        required = {
            'multilingual_manager': self.multilingual_manager,
            'context_assembler': self.context_assembler,
            'response_generator': self.response_generator,
            'conversation_manager': self.conversation_manager,
            'hybrid_search': self.hybrid_search
        }

        for name, component in required.items():
            if not component:
                logger.error(f"Missing component: {name}")
                return False

        logger.info("All components verified")
        return True

    @traceable(name="answer_tourism_question")
    async def answer_question(
        self,
        query: str,
        target_language: str = None,  #
        conversation_id: Optional[str] = None,
        enable_web_enrichment: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        FULLY ASYNC: Main method for answering questions with automatic language detection.

        WORKFLOW:
        1. Detect user's language automatically
        2. Translate query to EN via Groq (FREE) if needed (only for distant languages)
        3. Search in Qdrant with translated query
        4. Claude generates response DIRECTLY in user's language (reading EN/RU context)
        5. NO translation of final response needed

        Args:
            query: User's question in ANY of 18 languages
            target_language: Optional. If None, uses detected language
            conversation_id: Optional conversation ID
            enable_web_enrichment: Enable web enrichment
            **kwargs: Additional parameters (top_k)

        Returns:
            Dict with response, sources, metadata
        """

        if not self.is_initialized:
            return {
                "response": "System not initialized. Please call initialize() first.",
                "error": True,
                "conversation_id": conversation_id,
                "metadata": {}
            }

        start_time = datetime.now()

        try:
            logger.info(f"Processing query: {query[:100]}...")

            # automatic language detection
            detected_lang = await self.multilingual_manager.detect_language(query)
            logger.info(f"Detected user language: {detected_lang}")

            # if target_language not specified, use detected
            if target_language is None:
                target_language = detected_lang
                logger.info(f"Auto-set target_language to: {target_language}")

            # hybrid translation
            search_query = query
            query_was_translated = False

            # check if translation needed (only for distant languages)
            should_translate = await self.multilingual_manager.should_translate_for_search(detected_lang)

            if should_translate:
                logger.info(f"Translating {detected_lang} query to EN via Groq ...")

                search_query = await self.multilingual_manager.translate_query_with_groq(
                    text=query,
                    source_lang=detected_lang,
                    target='en'
                )

                if search_query != query:
                    query_was_translated = True
                    logger.info(f"Query translated: '{query[:40]}...' → '{search_query[:40]}...'")
                else:
                    logger.warning(f"Translation returned same text, using original")
            else:
                logger.info(f"Query in {detected_lang}, translation not needed for search")

            # conversation context
            conversation_context = ""
            if conversation_id and self.conversation_manager:
                conversation_context = self.conversation_manager.get_context_window(
                    conversation_id=conversation_id,
                    max_tokens=2000,
                    format="string"
                )

                if conversation_context:
                    logger.info(f"Using conversation {conversation_id} ({len(conversation_context)} chars context)")
            # query analysis
            query_analysis = await self._analyze_query_enhanced(query, target_language)

            if query_analysis:
                logger.info(f"Intent: {query_analysis.intent.value}, Enrichment: {query_analysis.needs_enrichment}")
            else:
                logger.warning("Query analysis returned None")

            # add user message to conversation
            if conversation_id and self.conversation_manager:
                self.conversation_manager.add_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=query,
                    metadata={
                        "language": detected_lang,
                        "intent": query_analysis.intent.value if query_analysis else 'unknown'
                    }
                )
            # hybrid search
            top_k = kwargs.get('top_k', 5)
            logger.info(f"Running hybrid search (top_k={top_k})...")

            loop = asyncio.get_event_loop()
            search_results = await loop.run_in_executor(
                None,
                self.hybrid_search.search,
                search_query,
                top_k
            )

            logger.info(f"Search complete: {len(search_results) if search_results else 0} results")

            # extract results from dict if needed
            if isinstance(search_results, dict) and 'results' in search_results:
                search_results_list = search_results['results']
            else:
                search_results_list = search_results

            # web enrichment (optional)
            enrichment = None
            if enable_web_enrichment and query_analysis and query_analysis.needs_enrichment:
                if self.web_enricher:
                    logger.info(f"Starting web enrichment (ASYNC)...")
                    async with self.web_enricher:
                        enrichment = await self.web_enricher.enrich_content(search_results_list, query_analysis)
                        logger.info(f"Enrichment complete: {enrichment.enrichment_sources if enrichment else []}")
                else:
                    logger.warning("WebEnrichmentEngine not available")

            # context assembly
            logger.info(f"Assembling context...")

            if hasattr(self.context_assembler, 'is_heavy_operation'):
                context = await loop.run_in_executor(
                    None,
                    self.context_assembler.assemble_context,
                    search_results_list,
                    query_analysis,
                    enrichment
                )
            else:
                context = await self.context_assembler.assemble_context(
                    search_results_list,
                    query_analysis,
                    enrichment
                )

            # add comprehensive query info to context
            context['query_info'] = {
                'original_query': query,  # original user query (any language)
                'search_query': search_query,  # translated for search (EN)
                'detected_language': detected_lang,
                'target_language': target_language,
                'query_was_translated': query_was_translated,
                'intent': query_analysis.intent.value if query_analysis else 'general'
            }

            # add conversation history to context
            if conversation_context:
                context['conversation_history'] = conversation_context

            # generate response
            logger.info(f"Generating response in '{target_language}'...")

            response_data = await self.response_generator.generate_response(
                context=context
            )

            logger.info(f"Response generated: {len(response_data['response'])} chars")

            # add assistant response to conversation
            if conversation_id and self.conversation_manager:
                source_ids = [r.get('id', '') if isinstance(r, dict) else str(getattr(r, 'id', ''))
                             for r in search_results_list[:3]]

                self.conversation_manager.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response_data["response"],
                    metadata={
                        "language": target_language,
                        "sources": source_ids
                    }
                )
            # response with source objects
            processing_time = (datetime.now() - start_time).total_seconds()

            from api.models import Source

            api_sources = []
            for result_item in search_results_list[:5]:
                if hasattr(result_item, 'payload'):
                    payload = result_item.payload
                    score = float(result_item.score) if hasattr(result_item, 'score') else 0.0
                else:
                    payload = result_item
                    score = float(result_item.get('score', 0.0))

                # extract location
                if self.context_assembler and hasattr(self.context_assembler, 'location_extractor'):
                    location_info = self.context_assembler.location_extractor.extract_location(payload)
                    primary_location = location_info.get('primary_location', payload.get('location', ''))
                else:
                    primary_location = payload.get('location', '')

                api_sources.append(Source(
                    id=str(payload.get('id', '')),
                    name=payload.get('name', 'Unknown'),
                    location=primary_location,
                    score=score,
                    category=payload.get('category', ''),
                    image_url=payload.get('image_url'),
                    description=payload.get('description', '')[:200] if payload.get('description') else None
                ))

            result = {
                "response": response_data["response"],
                "language": target_language,
                "sources": api_sources,
                "conversation_id": conversation_id,
                "metadata": {
                    "detected_language": detected_lang,
                    "target_language": target_language,
                    "query_was_translated": query_was_translated,
                    "search_query": search_query if query_was_translated else None,
                    "search_results_count": len(search_results_list),
                    "enrichment_enabled": enable_web_enrichment,
                    "enrichment_sources": enrichment.enrichment_sources if enrichment else [],
                    "processing_time": processing_time,
                    "model_used": response_data.get("model", "unknown"),
                    "total_tokens": response_data.get("total_tokens", 0),
                    "with_disclaimer": response_data.get("with_disclaimer", False),
                    "translation_service": "groq" if query_was_translated else None
                }
            }

            logger.info(f"Query processed in {processing_time:.2f}s, "
                       f"lang: {detected_lang}→{target_language}, "
                       f"translated: {query_was_translated}")

            return result

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            import traceback
            traceback.print_exc()

            error_lang = target_language or 'en'
            error_message = await self._get_error_response(error_lang, str(e))

            return {
                "response": error_message,
                "error": True,
                "conversation_id": conversation_id,
                "metadata": {
                    "error_type": type(e).__name__,
                    "processing_time": (datetime.now() - start_time).total_seconds()
                }
            }

    async def _analyze_query_enhanced(self, query: str, target_language: str = None) -> EnhancedQueryAnalysis:
        """
        Full implementation of query analysis.
        """
        try:
            # detect query language
            detected_lang = await self.multilingual_manager.detect_language(query)

            # determine target language for response
            target_lang = target_language or detected_lang

            # classify intent
            intent = self._classify_intent(query)

            # extract entities (places, attractions)
            entities = self._extract_entities_basic(query)

            # extract user preferences
            preferences = self._extract_preferences_basic(query)

            # determine if web enrichment is needed
            needs_enrichment = self._check_needs_enrichment(query, intent, entities)

            analysis = EnhancedQueryAnalysis(
                original_query=query,
                intent=intent,
                detected_language=detected_lang,
                target_language=target_lang,
                entities=entities,
                preferences=preferences,
                needs_enrichment=needs_enrichment
            )

            return analysis

        except Exception as e:
            logger.error(f"Error in _analyze_query_enhanced: {e}")
            return EnhancedQueryAnalysis(
                original_query=query,
                intent=QueryIntent.GENERAL,
                detected_language='en',
                target_language=target_language or 'en',
                entities=[],
                preferences=[],
                needs_enrichment=False
            )

    def _detect_language_simple(self, query: str) -> str:
        """Simple language detection by script"""
        query_lower = query.lower()

        if any('\u10a0' <= char <= '\u10ff' for char in query):
            return 'ka'
        if any('\u0400' <= char <= '\u04ff' for char in query):
            return 'ru'
        if any('\u0600' <= char <= '\u06ff' for char in query):
            return 'ar'
        if any('\u4e00' <= char <= '\u9fff' for char in query):
            return 'zh'
        if any('\u3040' <= char <= '\u30ff' for char in query):
            return 'ja'
        if any('\uac00' <= char <= '\ud7af' for char in query):
            return 'ko'

        return 'en'

    def _classify_intent(self, query: str) -> QueryIntent:
        """Classify query intent"""
        query_lower = query.lower()

        if any(word in query_lower for word in ['how to get', 'route', 'directions', 'как добраться', 'маршрут', 'путь']):
            return QueryIntent.ROUTE_PLANNING

        if any(word in query_lower for word in ['recommend', 'suggest', 'best', 'top', 'рекомендуете', 'посоветуйте', 'лучшие']):
            return QueryIntent.RECOMMENDATION

        if any(word in query_lower for word in ['what is', 'tell me about', 'information', 'что такое', 'расскажи о', 'информация']):
            return QueryIntent.INFO_REQUEST

        if any(word in query_lower for word in ['more about', 'also', 'and what about', 'еще о', 'также', 'а что насчет']):
            return QueryIntent.FOLLOW_UP

        return QueryIntent.GENERAL

    def _extract_entities_basic(self, query: str) -> List[str]:
        """Basic entity extraction"""
        common_places = [
            "тбилиси", "tbilisi", "батуми", "batumi", "светицховели",
            "svetitskhoveli", "сванети", "svaneti", "кахетия", "kakheti",
            "нарикала", "narikala", "вардзия", "vardzia", "мцхета", "mtskheta",
            "казбеги", "kazbegi", "гудаури", "gudauri", "боржоми", "borjomi",
            "уреки", "ureki", "пляж уреки"
        ]
        query_lower = query.lower()
        return [place for place in common_places if place in query_lower]

    def _extract_preferences_basic(self, query: str) -> List[str]:
        """Basic preference extraction"""
        preferences_map = {
            "wine": ["wine", "вино", "винодельня", "winery"],
            "history": ["history", "история", "historical", "исторический"],
            "nature": ["nature", "природа", "mountain", "горы", "озеро", "lake", "пляж", "beach"],
            "culture": ["culture", "культура", "traditional", "традиционный"],
            "architecture": ["architecture", "архитектура", "building", "здание"],
            "food": ["food", "еда", "cuisine", "кухня", "restaurant", "ресторан"],
            "adventure": ["джипы", "jeep", "off-road", "приключения", "активный отдых"]
        }

        query_lower = query.lower()
        found_preferences = []

        for pref, keywords in preferences_map.items():
            if any(keyword in query_lower for keyword in keywords):
                found_preferences.append(pref)

        return found_preferences

    def _check_needs_enrichment(self, query: str, intent: QueryIntent, entities: List[str]) -> bool:
        """Determine if web enrichment is needed"""
        query_lower = query.lower()

        needs_current_info = any(word in query_lower for word in [
            'price', 'cost', 'hours', 'open', 'closed', 'ticket',
            'цена', 'стоимость', 'часы', 'открыт', 'закрыт', 'билет'
        ])

        if needs_current_info:
            return True

        if intent == QueryIntent.RECOMMENDATION and len(entities) == 0:
            return True

        if intent == QueryIntent.ROUTE_PLANNING:
            return True

        info_keywords = [
            'пляж', 'beach', 'озеро', 'lake', 'гора', 'mountain',
            'монастырь', 'monastery', 'церковь', 'church', 'крепость', 'fortress',
            'парк', 'park', 'музей', 'museum', 'площадь', 'square',
            'расскажи', 'tell', 'покажи', 'show', 'что такое', 'what is'
        ]

        if intent == QueryIntent.INFO_REQUEST:
            if any(keyword in query_lower for keyword in info_keywords):
                return True

        return False

    async def _get_error_response(self, language: str, error: str) -> str:
        """Get localized error message"""
        messages = {
            "en": f"I apologize, but I encountered an error while processing your request. Please try again. (Error: {error})",
            "ru": f"Извините, при обработке вашего запроса произошла ошибка. Пожалуйста, попробуйте еще раз. (Ошибка: {error})",
            "ka": f"ვწუხვარ, თქვენი მოთხოვნის დამუშავებისას მოხდა შეცდომა. გთხოვთ, სცადოთ ხელახლა.",
            "de": f"Entschuldigung, bei der Bearbeitung Ihrer Anfrage ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.",
            "fr": f"Désolé, une erreur s'est produite lors du traitement de votre demande. Veuillez réessayer."
        }
        return messages.get(language, messages["en"])

    # hybrid search cache
    def get_hybrid_search_cache_stats(self) -> Dict[str, Any]:
        """Get HybridSearch cache statistics"""
        if not hasattr(self.hybrid_search, 'get_cache_health'):
            return {'error': 'HybridSearch cache not available'}

        return self.hybrid_search.get_cache_health()

    def clear_hybrid_search_cache(self):
        """Clear HybridSearch cache"""
        if hasattr(self.hybrid_search, 'clear_caches'):
            self.hybrid_search.clear_caches()
            logger.info("HybridSearch caches cleared")
        else:
            logger.warning("HybridSearch cache clearing not available")

    # cache and management queue
    def get_cache_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Statistics for all caches"""
        stats = {}

        if self.cache_manager:
            stats['cache_manager'] = self.cache_manager.get_stats(namespace)

        if hasattr(self.hybrid_search, 'get_cache_health'):
            stats['hybrid_search_cache'] = self.hybrid_search.get_cache_health()

        return stats

    def get_background_queue_status(self) -> Dict[str, Any]:
        """Get background task queue status"""
        if not self.background_queue:
            return {'error': 'Background queue not initialized'}
        return self.background_queue.get_stats()

    def clear_cache(self, namespace: Optional[str] = None, temp_only: bool = True) -> int:
        """Clear all caches"""
        total_cleared = 0

        if self.cache_manager:
            if temp_only:
                count = 0
                temp_namespaces = [
                    'translation:temp',
                    'enrichment:temp',
                    'search:dense:embeddings',
                    'search:dense:results',
                    'search:bm25:results',
                    'search:hybrid:final',
                    'search:prefilter'
                ]
                for ns in temp_namespaces:
                    count += self.cache_manager.clear_namespace(ns)
                logger.info(f"Cleared {count} temporary cache entries")
                total_cleared += count
            else:
                if namespace:
                    count = self.cache_manager.clear_namespace(namespace)
                    logger.info(f"Cleared {count} entries from namespace '{namespace}'")
                    total_cleared += count
                else:
                    count = 0
                    all_namespaces = [
                        'translation:temp', 'translation:permanent',
                        'enrichment:temp', 'enrichment:permanent',
                        'search:dense:embeddings', 'search:dense:results',
                        'search:bm25:results', 'search:hybrid:final',
                        'search:prefilter'
                    ]
                    for ns in all_namespaces:
                        count += self.cache_manager.clear_namespace(ns)
                    logger.info(f"Cleared {count} total cache entries")
                    total_cleared += count

        if hasattr(self.hybrid_search, 'clear_caches'):
            self.hybrid_search.clear_caches()
            logger.info("HybridSearch caches also cleared")
            total_cleared += 100

        return total_cleared

    # batch processing
    async def process_batch(self, queries: List[str], **kwargs) -> List[Dict[str, Any]]:
        """Process multiple queries in parallel"""
        logger.info(f"Processing batch of {len(queries)} queries")

        tasks = []
        for query in queries:
            task = self.answer_question(query, **kwargs)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error in batch item {i}: {result}")
                final_results.append({
                    "response": "An error occurred processing this query.",
                    "error": True,
                    "error_message": str(result)
                })
            else:
                final_results.append(result)

        logger.info(f"Batch processing complete: {len(final_results)} results")
        return final_results

    # system status
    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status"""
        return {
            "initialized": self.is_initialized,
            "components": {
                "qdrant": bool(self.qdrant_system),
                "hybrid_search": bool(self.hybrid_search),
                "redis": bool(self.redis_client),
                "cache_manager": bool(self.cache_manager),
                "multilingual": bool(self.multilingual_manager),
                "web_enricher": bool(self.web_enricher),
                "context_assembler": bool(self.context_assembler),
                "response_generator": bool(self.response_generator),
                "conversation_manager": bool(self.conversation_manager),
                "background_queue": bool(self.background_queue),
                "enrichment_persister": bool(self.enrichment_persister),
                "disclaimer_manager": bool(self.disclaimer_manager)
            },
            "cache_stats": self.get_cache_stats() if self.cache_manager else {},
            "queue_status": self.get_background_queue_status() if self.background_queue else {}
        }