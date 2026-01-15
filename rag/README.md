# RAG Context Assembly

Context preparation for LLM generation without document translation.

## Files

### `context.py`

**EnhancedContextAssembler** - Rich context assembly for LLM.

## Key Principle

**Documents stay in original language** (RU/EN) - NO translation!

**Why:**
- Translation degrades quality
- Adds 20+ seconds delay
- LLM generates response directly in target language
- Better than translate → generate → translate

## Features

- **No document translation** - Original RU/EN preserved
- **Location extraction** - City/region from full address
- **Image collection** - Cloudinary + Unsplash
- **Metadata enrichment** - Wikipedia, categories, tags
- **Structured output** - Ready for LLM prompt

## Usage
```python
from rag.context import EnhancedContextAssembler
from multilingual.multilingual_manager import MultilingualManager
from enrichment.web import WebEnrichmentEngine

# Initialize
assembler = EnhancedContextAssembler(
    web_enricher=web_enrichment_engine,
    multilingual_manager=multilingual_manager
)

# Assemble context
context = await assembler.assemble_context(
    search_results=search_results,
    query_analysis=analysis,
    enrichment=enrichment_data
)
```

## Context Structure
```python
{
    "query_info": {
        "detected_language": "en",
        "target_language": "en",
        "intent": "info_request",
        "original_query": "What to see in Tbilisi?",
        "entities": [...],
        "preferences": [...]
    },
    
    "search_results": [
        {
            "rank": 1,
            "name": "Narikala Fortress",
            "description": "Ancient fortress...",  # RU/EN original
            "category": "Historical Site",
            "location": "Tbilisi",  # Extracted city
            "location_full": "Old Tbilisi, Narikala St",  # Full address
            "tags": ["fortress", "history", "views"],
            "score": 0.95,
            "has_image": True,
            "image_url": "https://res.cloudinary.com/...",
            "original_language": "RU"
        }
    ],
    
    "enrichment": {
        "wikipedia_content": "Additional info...",
        "wikipedia_images": [...],
        "unsplash_images": [...],
        "enrichment_sources": ["wikipedia", "unsplash"]
    },
    
    "images": [
        {
            "place": "Narikala Fortress",
            "url": "https://res.cloudinary.com/...",
            "source": "cloudinary",
            "type": "attraction_photo"
        }
    ],
    
    "metadata_summary": {
        "total_results": 5,
        "results_with_images": 4,
        "enrichment_sources": ["wikipedia"],
        "additional_images": 3,
        "language_info": {
            "detected": "en",
            "target": "en",
            "language_name": "English",
            "documents_language": "original (RU/EN)",
            "translation_note": "Documents kept in original for quality"
        }
    }
}
```

## Location Extraction

**LocationExtractor** - Extract city/region from full address.

**Input:** `"Old Tbilisi, Narikala Street, 123"`

**Output:** `"Tbilisi"`

**Method:**
```python
location_info = self.location_extractor.extract_location(payload)
location_text = location_info['primary_location']
```

**Benefits:**
- Clean city names for display
- Better prompt formatting
- User-friendly output

## Image Collection

**Three sources:**

1. **Cloudinary (Database)**
   - From `image_url` field in Qdrant
   - High-quality, processed images
   - Primary source

2. **Unsplash (Enrichment)**
   - Professional stock photos
   - Landscape orientation
   - Up to 3 additional images

3. **Wikipedia (Enrichment)**
   - Historical images
   - Informational photos

**Priority:** Cloudinary → Unsplash → Wikipedia

## Supported Qdrant Fields

**Updated for new structure:**
```python
# Single name field (no name_en/name_ru)
name = payload.get('name')

# Image URL (Cloudinary)
image_url = payload.get('image_url')

# Location (full address)
location = payload.get('location')

# Category
category = payload.get('category')

# Tags (single field)
tags = payload.get('tags', [])

# Description (original language)
description = payload.get('description')

# Language marker
language = payload.get('language', 'RU')
```

## Result Processing

**For each search result:**

1. **Extract payload** - Universal extraction (dict/object)
2. **Get name** - Single name field
3. **Keep description** - NO translation
4. **Extract location** - City/region only
5. **Collect image** - Cloudinary URL
6. **Process tags** - Up to 10 tags
7. **Calculate score** - Relevance ranking

**Output:** Structured result dict

## Language Handling

**18 supported languages:**
```python
LANGUAGE_NAMES = {
    'en': 'English', 'ru': 'Russian', 'ka': 'Georgian',
    'de': 'German', 'fr': 'French', 'es': 'Spanish',
    # ... 18 total
}
```

**Strategy:**
- **Documents:** Stay in RU/EN (original)
- **Response:** Generated directly in target language by LLM
- **No translation:** Saves 20+ seconds, better quality

## Enrichment Integration

**Optional web enrichment:**
```python
if enrichment:
    # Add Wikipedia content
    if enrichment.wikipedia_content:
        context["enrichment"]["wikipedia"] = enrichment.wikipedia_content
    
    # Add Unsplash images
    if enrichment.unsplash_images:
        for img in enrichment.unsplash_images[:3]:
            context["images"].append({
                "url": img["url"],
                "source": "unsplash",
                "photographer": img["photographer"]
            })
```

**Sources tracked:** `enrichment_sources` list

## LLM Formatting

**Plain text format for prompts:**
```python
formatted = assembler.format_context_for_llm(context)
```

**Output:**
```
Document 1:
Name: Narikala Fortress
Category: Historical Site
Location: Tbilisi
Description: Древняя крепость...  (stays in Russian!)
Tags: fortress, history, panoramic
Relevance Score: 0.95
Has Image: True

---

Document 2:
...
```

**Used in:** LLM prompt construction (llm/generator.py)

## Error Handling

**Graceful fallbacks:**
```python
# Missing payload
if not payload:
    result_data = {
        "name": f"Result {doc_id}",
        "description": "No description available",
        "category": "unknown",
        "location": "",
        ...
    }

# Missing fields
name = payload.get('name', 'Unknown')
description = payload.get('description', '')
location = location_info.get('primary_location', '')
```

**No crashes on missing data!**

## Metadata Summary

**Statistics for monitoring:**
```python
metadata_summary = {
    "total_results": 5,
    "results_with_images": 4,
    "enrichment_sources": ["wikipedia", "unsplash"],
    "additional_images": 3,
    "language_info": {
        "detected": "en",
        "target": "ru",
        "documents_language": "original (RU/EN)"
    }
}
```

**Used for:**
- Logging
- Analytics
- Quality metrics

## Integration

**Used by:**
- `pipeline/rag.py` - Main RAG pipeline
- Called after search, before LLM generation

**Uses:**
- `enrichment/location.py` - LocationExtractor
- `multilingual/multilingual_manager.py` - Language info

## Performance

**Timings:**
- Payload extraction: < 0.01s per result
- Location extraction: < 0.01s per result
- Image collection: < 0.01s
- Total assembly: < 0.1s for 5 results

**Optimization:**
- No translation (saves 20+ seconds)
- Minimal processing
- Efficient field access

## Notes

- **Critical:** Documents NOT translated (quality preservation)
- New Qdrant structure fully supported (image_url, single name)
- LocationExtractor for clean location display
- Cloudinary images prioritized
- Up to 5 search results processed
- Up to 3 enrichment images added
- Tags limited to 10 per result
- All fields have safe defaults (no crashes)
