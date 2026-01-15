"""
Georgian attractions data adapter for hybrid search compatibility.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class GeorgianAttractionsAdapter:
    """
    Adapter for working with Georgian Attractions data.

    Transforms metadata into format compatible with hybrid search.
    """

    def __init__(self):
        self.field_mapping = {
            # main fields
            'name': 'name',
            'description': 'description',
            'location': 'location',
            'category': 'category',
            'language': 'language',
            'language_original': 'language_original',

            # enriched data
            'ner': 'ner',
            'ner_count': 'ner_count',
            'tags': 'tags',
            'tags_count': 'tags_count',

            # quality flags
            'has_images': 'has_images',
            'has_ner': 'has_ner',
            'has_tags': 'has_tags',

            # special flags
            'has_georgian_entities': 'has_georgian_entities',
            'is_religious_site': 'is_religious_site',
            'is_nature_tourism': 'is_nature_tourism',
            'is_cultural_heritage': 'is_cultural_heritage',
            'is_historical_site': 'is_historical_site'
        }

    def adapt_documents(self, raw_documents: List[Dict]) -> List[Dict]:
        """
        Adapt documents to hybrid search format.

        Args:
            raw_documents: Raw documents from Qdrant

        Returns:
            List[Dict]: Adapted documents
        """
        adapted_docs = []

        for doc in raw_documents:
            adapted_doc = self._adapt_single_document(doc)
            adapted_docs.append(adapted_doc)

        return adapted_docs

    def _adapt_single_document(self, doc: Dict) -> Dict:
        """Adapt single document"""
        metadata = doc.get('metadata', {})

        # basic structure of adapted document
        adapted = {
            'id': doc.get('id'),
            'page_content': self._create_searchable_content(metadata),
            'metadata': self._adapt_metadata(metadata)
        }

        return adapted

    def _create_searchable_content(self, metadata: Dict) -> str:
        """Create searchable content from metadata"""
        content_parts = []

        # main description
        description = metadata.get('description', '')
        if description:
            content_parts.append(description)

        # name
        name = metadata.get('name', '')
        if name:
            content_parts.append(name)

        # location
        location = metadata.get('location', '')
        if location:
            content_parts.append(location)

        # category
        category = metadata.get('category', '')
        if category:
            content_parts.append(category)

        # NER entities
        ner_entities = metadata.get('ner', [])
        if ner_entities:
            content_parts.extend(ner_entities)

        # tags
        tags = metadata.get('tags', [])
        if tags:
            content_parts.extend(tags)

        return ' '.join(content_parts)

    def _adapt_metadata(self, original_metadata: Dict) -> Dict:
        """Adapt metadata"""
        adapted_metadata = {}

        # direct field copying
        for original_field, adapted_field in self.field_mapping.items():
            if original_field in original_metadata:
                adapted_metadata[adapted_field] = original_metadata[original_field]

        # add derived fields if missing
        self._add_derived_fields(adapted_metadata, original_metadata)

        return adapted_metadata

    def _add_derived_fields(self, adapted_metadata: Dict, original_metadata: Dict):
        """Add derived fields"""

        # language flags
        if 'language' not in adapted_metadata:
            lang_original = original_metadata.get('language_original', 'en')
            adapted_metadata['language'] = lang_original.upper()

        # data presence flags
        if 'has_description' not in adapted_metadata:
            description = original_metadata.get('description', '')
            adapted_metadata['has_description'] = bool(description.strip())

        if 'has_ner' not in adapted_metadata:
            ner_count = original_metadata.get('ner_count', 0)
            adapted_metadata['has_ner'] = ner_count > 0

        if 'has_tags' not in adapted_metadata:
            tags_count = original_metadata.get('tags_count', 0)
            adapted_metadata['has_tags'] = tags_count > 0

        # full enrichment flag
        adapted_metadata['is_fully_enriched'] = (
            adapted_metadata.get('has_ner', False) and
            adapted_metadata.get('has_tags', False) and
            adapted_metadata.get('has_images', False)
        )

