"""
Query analyzer with optimized filter logic.
"""

import re
import time
import logging
from typing import Dict, List, Any

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny, Range

from core.types import QueryType, QueryAnalysis

logger = logging.getLogger(__name__)


# georgian location synonyms
GEORGIAN_SYNONYMS = {
    'тбилиси': ['tbilisi', 'тифлис', 'თბილისი'],
    'светицховели': ['svetitskhoveli', 'სვეტიცხოველი'],
    'церковь': ['храм', 'собор', 'монастырь', 'church', 'cathedral'],
    'крепость': ['fortress', 'castle', 'ციხე', 'замок'],
    'мцхета': ['mtskheta', 'მცხეთა'],
    'вардзия': ['vardzia', 'ვარძია'],
    'сванетия': ['svaneti', 'სვანეთი'],
    'батуми': ['batumi', 'ბათუმი'],
    'кутаиси': ['kutaisi', 'ქუთაისი'],
    'гори': ['gori', 'გორი'],
    'боржоми': ['borjomi', 'ბორჯომი']
}


class QueryAnalyzer:
    """
    Smart query analyzer with clean filter logic.

    Features:
    - Boolean flags only for explicit markers
    - Composite filters for known entities
    - Quality and language filters only on explicit request
    - Optimized strategies to reduce fallback
    """

    def __init__(self):
        try:
            import pymorphy2
            self.morph_ru = pymorphy2.MorphAnalyzer()
        except ImportError:
            self.morph_ru = None
            logger.warning("pymorphy2 not installed, Russian morphology unavailable")

        try:
            from nltk.stem import SnowballStemmer
            from nltk.corpus import stopwords
            self.stemmer_en = SnowballStemmer("english")
            self.stop_words_ru = set(stopwords.words('russian'))
            self.stop_words_en = set(stopwords.words('english'))
        except ImportError:
            self.stemmer_en = None
            self.stop_words_ru = set()
            self.stop_words_en = set()
            logger.warning("NLTK not configured, basic tokenization")

        # keyword to metadata flags mapping
        self.keyword_to_flags = {
            'церковь': ['is_religious_site'], 'храм': ['is_religious_site'],
            'монастырь': ['is_religious_site'], 'собор': ['is_religious_site'],
            'church': ['is_religious_site'], 'cathedral': ['is_religious_site'],
            'monastery': ['is_religious_site'],
            'ტაძარი': ['is_religious_site'], 'ეკლესია': ['is_religious_site'],
            'მონასტერი': ['is_religious_site'], 'ღვთისმშობლის': ['is_religious_site'],
            'წმინდა': ['is_religious_site'],

            'крепость': ['is_historical_site'], 'fortress': ['is_historical_site'],
            'castle': ['is_historical_site'], 'замок': ['is_historical_site'],
            'дворец': ['is_historical_site'], 'palace': ['is_historical_site'],

            'водопад': ['is_nature_tourism'], 'waterfall': ['is_nature_tourism'],
            'заповедник': ['is_nature_tourism'], 'wildlife': ['is_nature_tourism'],
            'термальный': ['is_nature_tourism'], 'thermal': ['is_nature_tourism'],
            'горнолыжный': ['is_nature_tourism'], 'ski resort': ['is_nature_tourism'],

            'винодельня': ['is_cultural_heritage'], 'winery': ['is_cultural_heritage'],
            'дегустация': ['is_cultural_heritage'], 'tasting': ['is_cultural_heritage'],
            'музей': ['is_cultural_heritage'], 'museum': ['is_cultural_heritage'],
            'галерея': ['is_cultural_heritage'], 'gallery': ['is_cultural_heritage'],
            'театр': ['is_cultural_heritage'], 'theater': ['is_cultural_heritage'],
            'опера': ['is_cultural_heritage'], 'opera': ['is_cultural_heritage'],
        }

        # known entities from database
        self.known_entities = [
            'светицховели', 'svetitskhoveli', 'სვეტიცხოველი', 'sveticxoveli',
            'нарикала', 'narikala', 'ნარიყალა', 'нарикала',
            'уплисцихе', 'uplistsikhe', 'უფლისციხე', 'upliscixe',
            'вардзия', 'vardzia', 'ვარძია', 'вардзиа',
            'батуми', 'batumi', 'ბათუმი',
            'тбилиси', 'tbilisi', 'თბილისი',
            'боржоми', 'borjomi', 'ბორჯომი',
            'мцхета', 'mtskheta', 'მცხეთა',
            'мост мира', 'bridge of peace', 'мирис хиди',
            'старый город', 'old town', 'дзвели калаки',
            'площадь европы', 'europe square',
            'мтацминда', 'mtatsminda', 'მთაწმინდა',
            'сололаки', 'sololaki',
            'авлабари', 'avlabari'
        ]

        # transliteration mapping
        self.transliteration_map = {
            'светицховели': ['svetitskhoveli', 'Svetitskhoveli', 'sveticxoveli'],
            'svetitskhoveli': ['светицховели', 'Светицховели'],
            'სვეტიცხოველი': ['svetitskhoveli', 'Svetitskhoveli', 'светицховели'],
            'нарикала': ['narikala', 'Narikala', 'нарикала'],
            'narikala': ['нарикала', 'Нарикала'],
            'ნარიყალა': ['narikala', 'Narikala', 'нарикала'],
            'тбилиси': ['tbilisi', 'Tbilisi'],
            'tbilisi': ['тбилиси', 'Тбилиси'],
            'თბილისი': ['tbilisi', 'Tbilisi', 'тбилиси'],
            'мцхета': ['mtskheta', 'Mtskheta'],
            'მცხეთა': ['mtskheta', 'Mtskheta', 'мцхета'],
            'батуми': ['batumi', 'Batumi'],
            'ბათუმი': ['batumi', 'Batumi', 'батуми'],
            'боржоми': ['borjomi', 'Borjomi'],
            'ბორჯომი': ['borjomi', 'Borjomi', 'боржоми'],
            'уплисцихе': ['uplistsikhe', 'Uplistsikhe'],
            'უფლისციხე': ['uplistsikhe', 'Uplistsikhe', 'уплисцихе'],
            'вардзия': ['vardzia', 'Vardzia'],
            'ვარძია': ['vardzia', 'Vardzia', 'вардзия'],
            'ტაძარი': ['cathedral', 'собор', 'church'],
            'ეკლესია': ['church', 'церковь'],
            'მონასტერი': ['monastery', 'монастырь']
        }

        logger.info("QueryAnalyzer initialized with optimized filter logic")

    def analyze(self, query: str) -> QueryAnalysis:
        """Full query analysis"""
        start_time = time.time()

        clean_query = self._clean_query(query)
        language = self._detect_language(clean_query)
        intent_type = self._classify_intent(clean_query)
        entities = self._extract_entities(clean_query, language)
        complexity = self._assess_complexity(clean_query)
        enhanced_query = self._enhance_query(clean_query, language, intent_type)
        implicit_filters = self._extract_implicit_filters(clean_query)
        suggested_weights = self._calculate_weights(intent_type, entities)
        semantic_query = self._build_semantic_query(clean_query, language, intent_type)
        keywords = self._extract_keywords(clean_query, language)
        qdrant_filters = self._build_qdrant_filters(clean_query, entities)
        filter_strategy = self._determine_filter_strategy(clean_query, qdrant_filters)
        dense_query = self._build_dense_query(clean_query, language, intent_type, entities)

        analysis = QueryAnalysis(
            original_query=query,
            language=language,
            detected_language=language,
            intent_type=intent_type,
            entities=entities,
            query_complexity=complexity,
            suggested_weights=suggested_weights,
            enhanced_query=enhanced_query,
            implicit_filters=implicit_filters,
            semantic_query=semantic_query,
            keywords=keywords,
            qdrant_filters=qdrant_filters,
            filter_strategy=filter_strategy,
            dense_query=dense_query
        )

        logger.info(f"Query analysis: {intent_type.value}, {len(qdrant_filters)} filters, strategy: {filter_strategy}, {time.time() - start_time:.3f}s")
        return analysis

    def _build_qdrant_filters(self, query: str, entities: Dict) -> List[Any]:
        """Build Qdrant filters with optimized logic"""
        filters = []
        query_lower = query.lower()

        # boolean flags only for explicit markers
        explicit_religious = ['церковь', 'храм', 'монастырь', 'собор', 'church', 'cathedral', 'monastery']
        if any(word in query_lower for word in explicit_religious):
            filter_condition = FieldCondition(key="is_religious_site", match=MatchValue(value=True))
            filters.append(filter_condition)
            logger.debug("Added boolean filter: is_religious_site")

        explicit_historical = ['крепость', 'fortress', 'castle', 'замок', 'дворец', 'palace']
        if any(word in query_lower for word in explicit_historical):
            filter_condition = FieldCondition(key="is_historical_site", match=MatchValue(value=True))
            filters.append(filter_condition)
            logger.debug("Added boolean filter: is_historical_site")

        # composite filters only for known entities
        found_known_entity = False
        for entity in self.known_entities:
            if re.search(r'\b' + re.escape(entity) + r'\b', query_lower, re.IGNORECASE):
                found_known_entity = True
                logger.info(f"Found known entity '{entity}', creating targeted filter")

                variants = [
                    entity.lower(),
                    entity.upper(),
                    entity.capitalize(),
                    entity
                ]

                if entity.lower() in self.transliteration_map:
                    for trans in self.transliteration_map[entity.lower()]:
                        variants.extend([trans, trans.lower(), trans.upper(), trans.capitalize()])

                for key, values in self.transliteration_map.items():
                    if entity.lower() in [v.lower() for v in values]:
                        variants.extend([key, key.lower(), key.upper(), key.capitalize()])

                variants = list(set(variants))
                logger.debug(f"Created {len(variants)} variants for '{entity}'")

                entity_filter = Filter(
                    should=[
                        FieldCondition(key="name", match=MatchAny(any=variants)),
                        FieldCondition(key="tags", match=MatchAny(any=variants))
                    ]
                )
                filters.append(entity_filter)
                logger.debug(f"Added OR filter for '{entity}' across 5 fields")
                break

        # quality filter only on explicit request
        # explicit_quality_words = ['лучшие', 'топ', 'best', 'top']
        # if any(word in query_lower for word in explicit_quality_words):
        #    filters.append(FieldCondition(key="quality_score", range=Range(gte=0.5)))
        #   logger.debug("Added quality filter (score >= 0.5)")

        # language filter only on explicit request
        if 'на русском' in query_lower or 'in english' in query_lower:
            if 'на русском' in query_lower:
                filters.append(FieldCondition(key="language", match=MatchValue(value="RU")))
                logger.debug("Added language filter: RU")
            elif 'in english' in query_lower:
                filters.append(FieldCondition(key="language", match=MatchValue(value="EN")))
                logger.debug("Added language filter: EN")

        logger.info(f"Built {len(filters)} filters total")
        return filters

    def _clean_query(self, query: str) -> str:
        """Clean query"""
        query = re.sub(r'\s+', ' ', query.strip())
        query = re.sub(r'[^\w\s\-]', ' ', query)
        return query.lower()

    def _detect_language(self, query: str) -> str:
        """Detect query language"""
        cyrillic_chars = len(re.findall(r'[а-яё]', query.lower()))
        latin_chars = len(re.findall(r'[a-z]', query.lower()))
        georgian_chars = len(re.findall(r'[ა-ჿ]', query))
        total_chars = len(re.findall(r'[а-яёa-zა-ჿ]', query.lower()))

        if total_chars == 0:
            return 'mixed'

        cyrillic_ratio = cyrillic_chars / total_chars
        latin_ratio = latin_chars / total_chars
        georgian_ratio = georgian_chars / total_chars

        if georgian_ratio > 0.3:
            return 'ka'
        elif cyrillic_ratio > 0.5:
            return 'ru'
        elif latin_ratio > 0.5:
            return 'en'
        else:
            return 'mixed'

    def _classify_intent(self, query: str) -> QueryType:
        """Classify query intent"""
        query_lower = query.lower()

        if any(indicator in query_lower for indicator in
               ['где', 'when', 'что такое', 'what is', 'где находится', 'where is']):
            return QueryType.FACTUAL

        if any(indicator in query_lower for indicator in
               ['как добраться', 'how to get', 'маршрут', 'route', 'дорога']):
            return QueryType.NAVIGATIONAL

        if any(indicator in query_lower for indicator in
               ['похожие', 'similar', 'как', 'like', 'сравнить', 'compare']):
            return QueryType.COMPARATIVE

        if any(indicator in query_lower for indicator in
               ['красивые', 'интересные', 'лучшие', 'beautiful', 'interesting', 'best']):
            return QueryType.EXPLORATORY

        if any(word in query_lower for word in
               ['фильтр', 'filter', 'только', 'only', 'тип', 'type']):
            return QueryType.FILTERED

        return QueryType.EXPLORATORY

    def _extract_entities(self, query: str, language: str) -> Dict[str, List[str]]:
        """Extract entities from query"""
        entities = {
            'locations': [],
            'categories': [],
            'organizations': []
        }

        location_patterns = {
            'тбилиси': ['tbilisi', 'თბილისი'],
            'батуми': ['batumi', 'ბათუმი'],
            'мцхета': ['mtskheta', 'მცხეთა'],
            'боржоми': ['borjomi', 'ბორჯომი']
        }

        for location, variants in location_patterns.items():
            if location in query or any(v in query for v in variants):
                entities['locations'].append(location)

        if any(word in query for word in ['церковь', 'храм', 'собор', 'church', 'cathedral']):
            entities['categories'].append('церковь')
        if any(word in query for word in ['крепость', 'замок', 'fortress', 'castle']):
            entities['categories'].append('крепость')
        if any(word in query for word in ['музей', 'museum']):
            entities['categories'].append('музей')

        return entities

    def _assess_complexity(self, query: str) -> str:
        """Assess query complexity"""
        words = query.split()
        if len(words) <= 2:
            return "simple"
        elif len(words) <= 5:
            return "moderate"
        else:
            return "complex"

    def _enhance_query(self, query: str, language: str, intent_type: QueryType) -> str:
        """Enhance query with additional context"""
        enhanced = query
        if intent_type == QueryType.EXPLORATORY and language == 'ru':
            enhanced += " туристическая достопримечательность Грузия"
        elif intent_type == QueryType.EXPLORATORY and language == 'en':
            enhanced += " tourist attraction Georgia"
        return enhanced

    def _extract_implicit_filters(self, query: str) -> Dict[str, Any]:
        """Extract implicit filters from query"""
        filters = {}

        if any(word in query for word in ['с фото', 'with photo', 'изображение', 'картинка']):
            filters['has_images'] = True

        if any(word in query for word in ['новинка', 'новое', 'recent', 'new']):
            filters['is_recent'] = True

        if any(word in query for word in
               ['церковь', 'храм', 'монастырь', 'church', 'cathedral', 'monastery']):
            filters['has_religion_tags'] = True

        if any(word in query for word in
               ['гора', 'озеро', 'водопад', 'парк', 'mountain', 'lake', 'waterfall', 'park']):
            filters['has_nature_tags'] = True

        if any(word in query for word in
               ['крепость', 'замок', 'музей', 'fortress', 'castle', 'museum']):
            filters['is_historical_site'] = True

        return filters

    def _calculate_weights(self, intent_type: QueryType, entities: Dict) -> Dict[str, float]:
        """Calculate weights for search components"""
        if intent_type == QueryType.FACTUAL:
            return {'bm25': 0.6, 'dense': 0.3, 'metadata': 0.1}
        elif intent_type == QueryType.EXPLORATORY:
            return {'bm25': 0.3, 'dense': 0.5, 'metadata': 0.2}
        elif intent_type == QueryType.COMPARATIVE:
            return {'bm25': 0.2, 'dense': 0.6, 'metadata': 0.2}
        else:
            return {'bm25': 0.4, 'dense': 0.4, 'metadata': 0.2}

    def _build_semantic_query(self, query: str, language: str, intent_type: QueryType) -> str:
        """Build semantic query"""
        semantic = query

        if intent_type == QueryType.EXPLORATORY:
            semantic += " красивая туристическая достопримечательность Грузия туризм" if language == 'ru' else " beautiful tourist attraction Georgia tourism"
        elif intent_type == QueryType.FACTUAL:
            semantic += " информация история описание Грузия" if language == 'ru' else " information history description Georgia"

        for location, synonyms in GEORGIAN_SYNONYMS.items():
            if location in query:
                semantic += " " + " ".join(synonyms[:2])
                break

        return semantic.strip()

    def _extract_keywords(self, query: str, language: str) -> List[str]:
        """Extract keywords from query"""
        keywords = []
        words = re.findall(r'\b\w+\b', query.lower())

        for word in words:
            if len(word) > 2:
                if (language == 'ru' and word in self.stop_words_ru) or \
                   (language == 'en' and word in self.stop_words_en):
                    continue

                is_place_name = any(entity in word for entity in self.known_entities)
                is_in_transliteration = word in self.transliteration_map

                if is_place_name or is_in_transliteration:
                    keywords.append(word)
                    if word in self.transliteration_map:
                        for variant in self.transliteration_map[word]:
                            if variant.lower() not in keywords:
                                keywords.append(variant.lower())
                else:
                    if language == 'ru' and self.morph_ru:
                        keywords.append(self.morph_ru.parse(word)[0].normal_form)
                    elif language == 'en' and self.stemmer_en:
                        keywords.append(self.stemmer_en.stem(word))
                    else:
                        keywords.append(word)

        return keywords

    def _determine_filter_strategy(self, query: str, filters: List[Any]) -> str:
        """Determine filter strategy"""
        if not filters:
            return "loose"

        if any(entity.lower() in query.lower() for entity in self.known_entities):
            if len(filters) <= 2:
                return 'moderate'
            else:
                return 'loose'

        if len(filters) >= 1:
            return 'loose'

        return 'loose'

    def _build_dense_query(self, query: str, language: str, intent_type: QueryType, entities: Dict) -> str:
        """Build query for dense search"""
        dense_query = query

        if intent_type == QueryType.EXPLORATORY:
            if language == 'ru':
                dense_query += " красивая туристическая достопримечательность Грузия туризм"
            elif language == 'ka':
                dense_query += " ლამაზი ტურისტული ღირსშესანიშნაობა საქართველო ტურიზმი beautiful tourist attraction Georgia"
            else:
                dense_query += " beautiful tourist attraction Georgia tourism"

        elif intent_type == QueryType.FACTUAL:
            if language == 'ru':
                dense_query += " информация история описание Грузия"
            elif language == 'ka':
                dense_query += " ინფორმაცია ისტორია აღწერა საქართველო information history Georgia"
            else:
                dense_query += " information history description Georgia"

        elif intent_type == QueryType.COMPARATIVE:
            if language == 'ru':
                dense_query += " похожий архитектура стиль"
            elif language == 'ka':
                dense_query += " მსგავსი არქიტექტურა სტილი similar architecture style"
            else:
                dense_query += " similar architecture style"

        elif intent_type == QueryType.NAVIGATIONAL:
            if language == 'ru':
                dense_query += " как добраться маршрут дорога Грузия"
            elif language == 'ka':
                dense_query += " როგორ მივიდე მარშრუტი გზა საქართველო how to get route Georgia"
            else:
                dense_query += " how to get route directions Georgia"

        for location in entities.get('locations', []):
            if location in GEORGIAN_SYNONYMS:
                dense_query += " " + " ".join(GEORGIAN_SYNONYMS[location][:2])
                break

        categories = entities.get('categories', [])
        if categories:
            category_context = {
                'церковь': 'религиозный храм православный',
                'крепость': 'историческая архитектура фортификация',
                'музей': 'культурное наследие экспозиция',
                'парк': 'природа отдых прогулка',
                'гора': 'альпинизм походы природа',
                'озеро': 'водоем природа рыбалка',
                'водопад': 'природа каскад вода'
            }

            for category in categories:
                if category in category_context:
                    dense_query += " " + category_context[category]
                    break

        return dense_query.strip()