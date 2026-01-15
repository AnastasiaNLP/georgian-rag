"""
Enhanced context assembler for RAG without translating documents.
"""

import logging
from typing import Dict, Any, List
from dataclasses import asdict

from enrichment.location import LocationExtractor

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    'en': 'English', 'ru': 'Russian', 'ka': 'Georgian',
    'de': 'German', 'fr': 'French', 'es': 'Spanish',
    'it': 'Italian', 'nl': 'Dutch', 'pl': 'Polish',
    'cs': 'Czech', 'zh': 'Chinese', 'ja': 'Japanese',
    'ko': 'Korean', 'ar': 'Arabic', 'tr': 'Turkish',
    'hi': 'Hindi', 'hy': 'Armenian', 'az': 'Azerbaijani'
}


class EnhancedContextAssembler:
    """
    Assembles rich context for LLM WITHOUT translating documents.
    KEY PRINCIPLE: Documents stay in original language (RU/EN).
    Only the LLM response will be in target language.
    """

    def __init__(self, web_enricher, multilingual_manager):
        self.web_enricher = web_enricher
        self.multilingual = multilingual_manager
        self.location_extractor = LocationExtractor()

    def extract_payload_from_result(self, item):
        """Universal function to extract payload/metadata from result"""
        if hasattr(item, 'metadata'):
            return item.metadata
        elif hasattr(item, 'payload'):
            return item.payload
        elif isinstance(item, dict):
            return item.get('payload', item.get('metadata', {}))
        else:
            return {}

    def extract_content_from_result(self, item):
        """Extract content from result"""

        if hasattr(item, 'content') and item.content:
            return item.content

        payload = self.extract_payload_from_result(item)

        if payload:
            description = payload.get('description', payload.get('content', ''))
            if description:
                return description

        return ''

    def extract_score_from_result(self, item):
        """Extract score from result"""
        if hasattr(item, 'score'):
            return item.score
        elif isinstance(item, dict):
            return item.get('score', 0.0)
        else:
            return 0.0

    async def assemble_context(self, search_results, query_analysis,
                             enrichment=None) -> Dict[str, Any]:
        """
        Assemble context WITHOUT translating documents.
        Support for new Qdrant fields
        Documents stay in original language.
        Reason: LLM will translate response itself.
        Translating documents = quality loss + 20+ seconds delay.
        """

        if query_analysis is None:
            logger.warning("query_analysis is None, creating default structure")
            query_info = {
                "detected_language": "unknown",
                "target_language": "en",
                "intent": "general",
                "original_query": "",
                "entities": [],
                "preferences": []
            }
        else:
            query_info = query_analysis.to_dict() if hasattr(query_analysis, 'to_dict') else query_analysis.__dict__

        context = {
            "query_info": query_info,
            "search_results": [],
            "enrichment": asdict(enrichment) if enrichment else {},
            "images": [],
            "metadata_summary": {}
        }

        # handle dict/list formats
        if isinstance(search_results, dict):
            results_list = search_results.get('results', [])
            logger.debug(f"Extracted {len(results_list)} results from dict")
        elif isinstance(search_results, list):
            results_list = search_results
            logger.debug(f"Using list with {len(results_list)} results")
        else:
            results_list = []
            logger.warning(f"Unexpected search_results type: {type(search_results)}")

        # process results without translation
        for i, result in enumerate(results_list[:5]):
            payload = self.extract_payload_from_result(result)
            content = self.extract_content_from_result(result)
            score = self.extract_score_from_result(result)

            if payload:
                # single name field (no name)
                display_name = payload.get('name', 'Unknown')
                # original description without translation
                description = (payload.get('description', '') or
                             content or
                             payload.get('content', '') or
                             payload.get('summary', ''))

                # extract location using LocationExtractor
                location_info = self.location_extractor.extract_location(payload)
                location_text = location_info['primary_location']

                # use image_url from Qdrant (Cloudinary)
                image_url = payload.get('image_url')
                has_image = payload.get('has_processed_image', False) or bool(image_url)

                # tags processing
                tags = []
                for tag_field in ['tags']:  # only 'tags' field exists now
                    field_tags = payload.get(tag_field, [])
                    if isinstance(field_tags, list):
                        tags.extend(field_tags)
                    elif isinstance(field_tags, str):
                        tags.extend(field_tags.split(','))

                result_data = {
                    "rank": i + 1,
                    "name": display_name,
                    "description": description,
                    "category": payload.get('category', ''),
                    "location": location_text,  # extracted city/region
                    "location_full": payload.get('location', ''),  # full address
                    "tags": tags[:10],
                    "score": float(score) if score else 0.0,
                    "has_image": has_image,
                    "image_url": image_url,  # cloudinary URL
                    "original_language": payload.get('language', 'RU')
                }

                # add to images list if has image
                if has_image and image_url:
                    context["images"].append({
                        "place": result_data["name"],
                        "url": image_url,  #  use Cloudinary URL
                        "source": "cloudinary",
                        "type": "attraction_photo"
                    })

                context["search_results"].append(result_data)

            else:
                # fallback for missing payload
                doc_id = getattr(result, 'doc_id', str(i))
                context["search_results"].append({
                    "rank": i + 1,
                    "name": f"Result {doc_id[:8]}",
                    "description": content or "No description available",
                    "category": "unknown",
                    "location": "",
                    "location_full": "",
                    "tags": [],
                    "score": float(score) if score else 0.0,
                    "has_image": False,
                    "image_url": None,
                    "original_language": "RU"
                })

        # add enrichment images (Unsplash)
        if enrichment:
            if hasattr(enrichment, 'unsplash_images') and enrichment.unsplash_images:
                context["images"].extend([
                    {
                        "url": img["url"],
                        "thumbnail": img["thumbnail"],
                        "source": "unsplash",
                        "photographer": img["photographer"],
                        "type": "professional_photo"
                    } for img in enrichment.unsplash_images[:3]
                ])

        # summary statistics
        total_results = len(results_list)
        results_with_images = sum(1 for r in context["search_results"] if r["has_image"])

        query_info = context["query_info"]
        detected_language = query_info.get('detected_language', 'unknown')
        target_language = query_info.get('target_language', detected_language)

        context["metadata_summary"] = {
            "total_results": total_results,
            "results_with_images": results_with_images,
            "enrichment_sources": enrichment.enrichment_sources if enrichment and hasattr(enrichment, 'enrichment_sources') else [],
            "additional_images": len(enrichment.unsplash_images) if enrichment and hasattr(enrichment, 'unsplash_images') and enrichment.unsplash_images else 0,
            "language_info": {
                "detected": detected_language,
                "target": target_language,
                "language_name": LANGUAGE_NAMES.get(target_language, "Unknown"),
                "documents_language": "original (RU/EN)",
                "translation_note": "Documents kept in original language for quality. LLM will respond in target language."
            }
        }

        logger.info(f"Context assembled: {total_results} results, language: {detected_language}→{target_language}, NO TRANSLATION applied")

        return context

    def format_context_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Format context for LLM.
        Use extracted location instead of raw address
        Documents stay in original language.
        """
        parts = []

        for result in context["search_results"]:
            parts.append(f"""
Document {result['rank']}:
Name: {result['name']}
Category: {result['category']}
Location: {result['location']}
Description: {result['description']}
Tags: {', '.join(result['tags'][:5])}
Relevance Score: {result['score']:.2f}
Has Image: {result['has_image']}
""")

        return "\n---\n".join(parts)