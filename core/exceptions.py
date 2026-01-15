"""
Custom exceptions for Georgian Attractions RAG system.
"""


class RAGException(Exception):
    """Base exception for RAG system"""
    pass


class ConfigurationError(RAGException):
    """Configuration or initialization error"""
    pass


class SearchError(RAGException):
    """Search operation error"""
    pass


class EmbeddingError(RAGException):
    """Embedding model error"""
    pass


class QdrantError(RAGException):
    """Qdrant client error"""
    pass


class EnrichmentError(RAGException):
    """Web enrichment error"""
    pass


class CacheError(RAGException):
    """Cache operation error"""
    pass