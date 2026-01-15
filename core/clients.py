"""
Client singletons for external services.
"""
import logging
from typing import Optional
from qdrant_client import QdrantClient
import cloudinary
import cloudinary.uploader
import cloudinary.api

from config.settings import config
from core.exceptions import QdrantError, ConfigurationError

logger = logging.getLogger(__name__)


_qdrant_client: Optional[QdrantClient] = None
_cloudinary_initialized: bool = False


def get_qdrant_client() -> QdrantClient:
    """
    Get global Qdrant client singleton.
    """
    global _qdrant_client

    if _qdrant_client is None:
        try:
            logger.info("Connecting to Qdrant Cloud...")
            _qdrant_client = QdrantClient(
                url=config.qdrant.url,
                api_key=config.qdrant.api_key,
                timeout=config.qdrant.timeout
            )

            collection_info = _qdrant_client.get_collection(config.qdrant.collection_name)

            logger.info(f"Connected to Qdrant Cloud")
            logger.info(f"  URL: {config.qdrant.url[:50]}...")
            logger.info(f"  Collection: {config.qdrant.collection_name}")
            logger.info(f"  Documents: {collection_info.points_count}")
            logger.info(f"  Vector size: {collection_info.config.params.vectors.size}")

        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise QdrantError(f"Failed to initialize Qdrant client: {e}")

    return _qdrant_client


def initialize_cloudinary() -> None:
    """Initialize Cloudinary configuration"""
    global _cloudinary_initialized

    if not _cloudinary_initialized:
        try:
            cloudinary.config(
                cloud_name=config.cloudinary.cloud_name,
                api_key=config.cloudinary.api_key,
                api_secret=config.cloudinary.api_secret,
                secure=True
            )
            _cloudinary_initialized = True
            logger.info(f"Cloudinary initialized: {config.cloudinary.cloud_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Cloudinary: {e}")
            raise ConfigurationError(f"Failed to initialize Cloudinary: {e}")


def is_cloudinary_ready() -> bool:
    """Check if Cloudinary is initialized"""
    return _cloudinary_initialized


def reset_clients():
    """Reset all clients (useful for testing)"""
    global _qdrant_client, _cloudinary_initialized
    _qdrant_client = None
    _cloudinary_initialized = False