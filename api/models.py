"""
Api models
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class LanguageCode(str, Enum):
    """Supported language codes"""
    EN = "en"
    RU = "ru"
    KA = "ka"
    DE = "de"
    FR = "fr"
    ES = "es"
    IT = "it"
    NL = "nl"
    PL = "pl"
    CS = "cs"
    ZH = "zh"
    JA = "ja"
    KO = "ko"
    AR = "ar"
    TR = "tr"
    HI = "hi"
    HY = "hy"
    AZ = "az"


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    query: str = Field(..., description="User query")
    target_language: LanguageCode = Field(LanguageCode.EN, description="Target language for response")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for multi-turn")
    enable_web_enrichment: bool = Field(True, description="Enable web enrichment")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")


class Source(BaseModel):
    """
    Added image_url field from Qdrant structure
    """
    id: str
    name: str
    location: Optional[str] = None
    score: float
    category: Optional[str] = None
    image_url: Optional[str] = Field(None, description="Cloudinary image URL")
    description: Optional[str] = Field(None, description="Short description")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    language: str
    sources: List[Source]
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    components: Dict[str, str] = {}
    issues: List[str] = []
    initialized: bool = False
    warmed_up: bool = False


class StatsResponse(BaseModel):
    """System statistics response"""
    cache_stats: Dict[str, Any] = {}
    search_stats: Dict[str, Any] = {}
    system_info: Dict[str, Any] = {}
    uptime: float = 0


class SearchRequest(BaseModel):
    """Request model for search endpoint"""
    query: str = Field(..., description="Search query")
    language: LanguageCode = Field(LanguageCode.EN, description="Query language")
    top_k: int = Field(10, ge=1, le=50, description="Number of results")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters")


class SearchResponse(BaseModel):
    """Response model for search endpoint"""
    results: List[Source]
    total: int
    query: str
    language: str
    search_time: float


class ClearCacheRequest(BaseModel):
    """Request to clear cache"""
    namespace: Optional[str] = Field(None, description="Cache namespace to clear")
    temp_only: bool = Field(True, description="Clear only temporary cache")


class CacheStatsResponse(BaseModel):
    """Cache statistics response"""
    cache_type: str
    cache_size: int
    max_cache_size: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    total_requests: int


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class LanguageInfo(BaseModel):
    """Language information"""
    code: str
    name: str
    native_name: Optional[str] = None


class LanguagesResponse(BaseModel):
    """Response with supported languages"""
    languages: List[LanguageInfo]
    total: int


class EnrichmentRequest(BaseModel):
    """Request for content enrichment"""
    doc_id: str = Field(..., description="Document ID to enrich")
    force: bool = Field(False, description="Force re-enrichment")


class EnrichmentResponse(BaseModel):
    """Response from enrichment"""
    doc_id: str
    enriched: bool
    enrichment_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: str = Field(..., description="Message type: ping, chat, status, response, error")
    data: Optional[Dict[str, Any]] = Field(None, description="Message data")
    timestamp: datetime = Field(default_factory=datetime.now)


class SystemInfo(BaseModel):
    """System information"""
    version: str
    model: str
    collection: str
    documents_count: int
    supported_languages: int
    features: List[str]


class SystemInfoResponse(BaseModel):
    """Response with system information"""
    info: SystemInfo
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)