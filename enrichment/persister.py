"""
Enrichment persister
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class EnrichmentPersister:
    """
    Persist enrichment data to Qdrant metadata (BACKGROUND).

    Uses BackgroundTaskQueue for non-blocking updates.
    """

    def __init__(
        self,
        qdrant_client,
        collection_name: str,
        background_queue=None
    ):
        """
        Initialize persister.

        Args:
            qdrant_client: Qdrant client instance
            collection_name: Collection name (e.g., 'georgian_attractions')
            background_queue: BackgroundTaskQueue instance (uses global if None)
        """
        self.qdrant = qdrant_client
        self.collection_name = collection_name
        self.background_queue = background_queue

        # import global queue if needed
        if background_queue is None:
            try:
                from utils.background_queue import GLOBAL_BACKGROUND_QUEUE
                self.background_queue = GLOBAL_BACKGROUND_QUEUE
            except ImportError:
                logger.warning("Could not import GLOBAL_BACKGROUND_QUEUE")
                self.background_queue = None

        logger.info(
            f"EnrichmentPersister initialized "
            f"(collection: {collection_name}, background: {'enabled' if background_queue else 'disabled'})"
        )

    def persist_enrichment_async(
        self,
        document_id: str,
        enrichment_data: Dict[str, Any]
    ):
        """
        Queue enrichment update (NON-BLOCKING).

        Returns IMMEDIATELY without waiting for Qdrant

        Args:
            document_id: Document ID to update
            enrichment_data: Enrichment data to save
        """
        if not self.background_queue:
            logger.warning("No background queue, persisting synchronously")
            return self._persist_enrichment_sync(document_id, enrichment_data)

        # add to background queue
        self.background_queue.add_task(
            task_name=f"persist_enrichment_{document_id}",
            func=self._persist_enrichment_sync,
            document_id=document_id,
            enrichment_data=enrichment_data
        )

        logger.info(f"Queued Qdrant update for {document_id} (non-blocking)")

    def _persist_enrichment_sync(
        self,
        document_id: str,
        enrichment_data: Dict[str, Any]
    ) -> bool:
        """
        Actual Qdrant update (BLOCKING - runs in background worker).

        This is the slow operation that happens in background!

        Args:
            document_id: Document ID
            enrichment_data: Data to save

        Returns:
            Success boolean
        """
        try:
            logger.info(f"Updating Qdrant metadata for {document_id}...")

            # get current document
            current_docs = self.qdrant.retrieve(
                collection_name=self.collection_name,
                ids=[document_id]
            )

            if not current_docs:
                logger.warning(f"Document {document_id} not found in Qdrant")
                return False

            current = current_docs[0]

            # handle both Qdrant objects and dicts
            if hasattr(current, 'payload'):
                # real Qdrant object
                updated_payload = dict(current.payload)
            elif isinstance(current, dict):
                # mock dict
                updated_payload = dict(current.get('payload', current))
            else:
                logger.error(f"Unexpected document type: {type(current)}")
                return False

            # add enrichment data
            enriched_fields = []

            if enrichment_data.get('wikipedia_content'):
                updated_payload['description_enriched'] = enrichment_data['wikipedia_content']
                enriched_fields.append('wikipedia_content')

            if enrichment_data.get('wikipedia_images'):
                updated_payload['images_wikipedia'] = enrichment_data['wikipedia_images'][:5]
                enriched_fields.append('wikipedia_images')

            if enrichment_data.get('unsplash_images'):
                if not updated_payload.get('image_url'):
                    updated_payload['images_unsplash'] = [
                        {
                            'url': img.get('urls', {}).get('regular'),
                            'photographer': img.get('user', {}).get('name'),
                            'alt': img.get('alt_description')
                        }
                        for img in enrichment_data['unsplash_images'][:5]
                        if isinstance(img, dict)
                    ]
                    enriched_fields.append('unsplash_images')
                else:
                    logger.info(f"Skipping Unsplash images - Cloudinary image_url already exists: {updated_payload.get('image_url')}")
            # metadata
            updated_payload['enriched_at'] = datetime.now(timezone.utc).isoformat()
            updated_payload['enrichment_sources'] = enrichment_data.get('enrichment_sources', [])
            updated_payload['is_enriched'] = True
            updated_payload['enriched_fields'] = enriched_fields

            # update Qdrant
            self.qdrant.set_payload(
                collection_name=self.collection_name,
                payload=updated_payload,
                points=[document_id]
            )

            logger.info(f"Qdrant updated for {document_id}: {enriched_fields}")
            return True

        except Exception as e:
            logger.error(f"Failed to update Qdrant for {document_id}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def is_enriched(self, document_id: str) -> bool:
        """
        Check if document already enriched.

        Args:
            document_id: Document ID

        Returns:
            True if enriched, False otherwise
        """
        try:
            docs = self.qdrant.retrieve(
                collection_name=self.collection_name,
                ids=[document_id]
            )
            if docs:
                doc = docs[0]
                # handle both Qdrant objects and dicts
                if hasattr(doc, 'payload'):
                    return doc.payload.get('is_enriched', False)
                elif isinstance(doc, dict):
                    return doc.get('payload', doc).get('is_enriched', False)
            return False
        except Exception as e:
            logger.error(f"Error checking enrichment status: {e}")
            return False