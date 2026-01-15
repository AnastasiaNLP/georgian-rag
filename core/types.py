"""
Core data types for Georgian Attractions RAG system.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
from enum import Enum


class QueryType(Enum):
    """Query types for adaptive search"""
    FACTUAL = "factual"
    EXPLORATORY = "exploratory"
    COMPARATIVE = "comparative"
    NAVIGATIONAL = "navigational"
    FILTERED = "filtered"


@dataclass
class QueryAnalysis:
    """Query analysis result with extracted entities and intent"""
    original_query: str
    language: str
    detected_language: str
    intent_type: QueryType
    entities: Dict[str, Any]
    query_complexity: str
    suggested_weights: Dict[str, float]
    enhanced_query: str
    implicit_filters: Dict[str, Any]
    semantic_query: str
    keywords: List[str]
    qdrant_filters: List[Any]
    filter_strategy: str
    dense_query: str


@dataclass
class SearchResult:
    """Search result from a single component"""
    doc_id: str
    score: float
    source: str = 'unknown'
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: str = ""

    @property
    def id(self):
        """Alias for doc_id for backward compatibility"""
        return self.doc_id
    @property
    def payload(self):
        """Compatibility with old API"""
        return self.metadata

    @payload.setter
    def payload(self, value):
        """Allows setting payload as metadata"""
        if isinstance(value, dict):
            self.metadata = value
        else:
            self.metadata = {}

    def get_payload_field(self, field_name: str, default=None):
        """Get field from metadata/payload"""
        return self.metadata.get(field_name, default)

    def has_content(self) -> bool:
        """Check if result has meaningful content"""
        return bool(self.content) or bool(self.metadata.get('description'))

    def get_display_name(self) -> str:
        """Get display name for result"""
        name_fields = ['name', 'title']
        for field in name_fields:
            if field in self.metadata and self.metadata[field]:
                return self.metadata[field]
        return f"Document {self.doc_id[:8]}..."

# WEIGHT PROFILES
WEIGHT_PROFILES = {
    QueryType.FACTUAL: {'bm25': 0.7, 'dense': 0.2, 'metadata': 0.1},
    QueryType.EXPLORATORY: {'bm25': 0.4, 'dense': 0.5, 'metadata': 0.1},
    QueryType.COMPARATIVE: {'bm25': 0.4, 'dense': 0.5, 'metadata': 0.1},
    QueryType.NAVIGATIONAL: {'bm25': 0.6, 'dense': 0.3, 'metadata': 0.1},
    QueryType.FILTERED: {'bm25': 0.4, 'dense': 0.3, 'metadata': 0.3}
}

# GEORGIAN SYNONYMS
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