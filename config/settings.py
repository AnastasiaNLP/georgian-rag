"""
Georgian Attractions RAG - Configuration Settings
Centralized configuration management for all components.
"""

import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / ".cache"
LOGS_DIR = PROJECT_ROOT / "logs"

# creating directories
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# qdrant configuration
@dataclass
class QdrantConfig:
    """Qdrant Vector Database Configuration"""
    url: str = os.getenv('QDRANT_URL', '')
    api_key: str = os.getenv('QDRANT_API_KEY', '')
    collection_name: str = os.getenv('COLLECTION_NAME', 'georgian_attractions')
    vector_size: int = int(os.getenv('VECTOR_SIZE', '384'))
    timeout: int = 30

    def validate(self) -> bool:
        """Validate Qdrant configuration"""
        if not self.url or not self.api_key:
            raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in .env file")
        return True

# embedding model configuration
@dataclass
class EmbeddingConfig:
    """Embedding Model Configuration"""
    model_name: str = os.getenv(
        'EMBEDDING_MODEL',
        'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    )
    vector_size: int = int(os.getenv('VECTOR_SIZE', '384'))
    device: str = os.getenv('DEVICE', 'cpu')
    batch_size: int = int(os.getenv('BATCH_SIZE', '32'))
    max_seq_length: int = 512
    normalize_embeddings: bool = True

# cloudinary configuration
@dataclass
class CloudinaryConfig:
    """Cloudinary Image Storage Configuration"""
    cloud_name: str = os.getenv('CLOUDINARY_CLOUD_NAME', '')
    api_key: str = os.getenv('CLOUDINARY_API_KEY', '')
    api_secret: str = os.getenv('CLOUDINARY_API_SECRET', '')
    folder: str = 'georgian_attractions'

    def validate(self) -> bool:
        """Validate Cloudinary configuration"""
        if not self.cloud_name or not self.api_key or not self.api_secret:
            raise ValueError("Cloudinary credentials must be set in .env file")
        return True

# claude api configuration
@dataclass
class ClaudeConfig:
    """Anthropic Claude API Configuration"""
    api_key: str = os.getenv('ANTHROPIC_API_KEY', '')
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 60

    def validate(self) -> bool:
        """Validate Claude API configuration"""
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set in .env file")
        return True

# groq api configuration
@dataclass
class GroqConfig:
    """Groq API Configuration"""
    api_key: str = os.getenv('GROQ_API_KEY', '')
    model: str = "mixtral-8x7b-32768"
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 60

    def validate(self) -> bool:
        """Validate Groq API configuration"""
        if not self.api_key:
            raise ValueError("GROQ_API_KEY must be set in .env file")
        return True

# redis cache configuration
@dataclass
class RedisConfig:
    """Upstash Redis Configuration for Caching"""
    url: Optional[str] = os.getenv('UPSTASH_REDIS_URL')
    token: Optional[str] = os.getenv('UPSTASH_REDIS_TOKEN')
    enabled: bool = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
    ttl: int = 86400  # 24 hours in seconds

    def is_available(self) -> bool:
        """Check if Redis is properly configured"""
        return bool(self.url and self.token and self.enabled)

# google translate configuration
@dataclass
class TranslationConfig:
    """Google Cloud Translation API Configuration"""
    api_key: Optional[str] = os.getenv('GOOGLE_TRANSLATE_API_KEY')
    enabled: bool = bool(os.getenv('GOOGLE_TRANSLATE_API_KEY'))
    default_target_language: str = 'en'

# unsplash configuration
@dataclass
class UnsplashConfig:
    """Unsplash API Configuration for Image Enrichment"""
    access_key: Optional[str] = os.getenv('UNSPLASH_ACCESS_KEY')
    secret_key: Optional[str] = os.getenv('UNSPLASH_SECRET_KEY')
    enabled: bool = bool(os.getenv('UNSPLASH_ACCESS_KEY'))
    per_page: int = 5


# search configuration
@dataclass
class SearchConfig:
    """Search Engine Configuration"""
    max_results: int = int(os.getenv('MAX_SEARCH_RESULTS', '10'))
    min_score: float = 0.5
    use_hybrid: bool = True  # Dense + BM25
    dense_weight: float = 0.7
    bm25_weight: float = 0.3

    # BM25 Parameters
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

# web enrichment configuration
@dataclass
class EnrichmentConfig:
    """Web Enrichment Configuration"""
    enabled: bool = os.getenv('WEB_ENRICHMENT_ENABLED', 'true').lower() == 'true'
    wikipedia_enabled: bool = True
    unsplash_enabled: bool = bool(os.getenv('UNSPLASH_ACCESS_KEY'))
    max_wikipedia_sentences: int = 3
    cache_ttl: int = 604800  # 7 days in seconds

# multilingual  configuration
@dataclass
class MultilingualConfig:
    """Multi-language Support Configuration"""
    supported_languages: List[str] = None
    default_language: str = 'en'
    auto_detect: bool = True
    translate_queries: bool = True

    def __post_init__(self):
        if self.supported_languages is None:
            self.supported_languages = [
                'en', 'ru', 'ka',  # Core languages
                'de', 'fr', 'es', 'it', 'pt',  # European
                'zh', 'ja', 'ko',  # Asian
                'ar', 'he',  # Middle Eastern
                'hi', 'bn',  # South Asian
                'tr', 'pl', 'nl'  # Other
            ]

# logging configuration
@dataclass
class LoggingConfig:
    """Logging Configuration"""
    level: str = os.getenv('LOG_LEVEL', 'INFO')
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    file_path: Path = LOGS_DIR / 'georgian_rag.log'
    max_bytes: int = 10_485_760  # 10 MB
    backup_count: int = 5

# dataset configuration
@dataclass
class DatasetConfig:
    """HuggingFace Dataset Configuration"""
    name: str = os.getenv('DATASET_NAME', 'AIAnastasia/georgian-attractions')
    split: str = 'train'
    cache_dir: Path = CACHE_DIR / 'datasets'

# main configuration container
class Config:
    """Main Configuration Container"""

    def __init__(self):
        self.qdrant = QdrantConfig()
        self.embedding = EmbeddingConfig()
        self.cloudinary = CloudinaryConfig()
        self.groq = GroqConfig()
        self.claude = ClaudeConfig()
        self.redis = RedisConfig()
        self.translation = TranslationConfig()
        self.unsplash = UnsplashConfig()
        self.search = SearchConfig()
        self.enrichment = EnrichmentConfig()
        self.multilingual = MultilingualConfig()
        self.logging = LoggingConfig()
        self.dataset = DatasetConfig()

    def validate(self) -> bool:
        """Validate critical configurations"""
        try:
            self.qdrant.validate()
            self.cloudinary.validate()
            self.claude.validate()
            return True
        except ValueError as e:
            print(f"Configuration Error: {e}")
            return False

    def print_status(self):
        """Print configuration status"""
        print("GEORGIAN ATTRACTIONS RAG - Configuration Status")
        print(f"\n Qdrant: {'✅' if self.qdrant.url else '❌'}")
        print(f"   URL: {self.qdrant.url[:50]}...")
        print(f"   Collection: {self.qdrant.collection_name}")

        print(f"\n  Cloudinary: {'✅' if self.cloudinary.cloud_name else '❌'}")
        print(f"   Cloud: {self.cloudinary.cloud_name}")

        print(f"\n Claude API: {'✅' if self.claude.api_key else '❌'}")
        print(f"   Model: {self.claude.model}")

        print(f"\n Redis Cache: {'✅' if self.redis.is_available() else '❌ (Optional)'}")

        print(f"\n Translation: {'✅' if self.translation.enabled else '❌ (Optional)'}")

        print(f"\n Unsplash: {'✅' if self.unsplash.enabled else '❌ (Optional)'}")

        print(f"\n Search Config:")
        print(f"   Max Results: {self.search.max_results}")
        print(f"   Hybrid Search: {self.search.use_hybrid}")

        print(f"\n Languages: {len(self.multilingual.supported_languages)} supported")

# global config
config = Config()
settings = config

# convenience configuration
def get_config() -> Config:
    """Get global configuration instance"""
    return config


def validate_config() -> bool:
    """Validate all critical configurations"""
    return config.validate()


if __name__ == "__main__":
    # test configuration
    config.print_status()
    config.validate()