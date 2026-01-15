# Configuration

Centralized configuration management for Georgian RAG system.

## Files

### `settings.py`

Complete configuration system using dataclasses and environment variables.

**Configuration Sections:**

1. **QdrantConfig** - Vector database settings
   - URL, API key, collection name
   - Vector size (384), timeout

2. **EmbeddingConfig** - Embedding model settings
   - Model: `paraphrase-multilingual-MiniLM-L12-v2`
   - Device (CPU/CUDA), batch size

3. **CloudinaryConfig** - Image storage
   - Cloud name, API credentials
   - Folder: `georgian_attractions`

4. **ClaudeConfig** - Claude API settings
   - Model: `claude-haiku-4-5-20251001`
   - Max tokens: 4000, temperature: 0.7

5. **GroqConfig** - Groq API settings
   - Model: `mixtral-8x7b-32768`
   - Alternative LLM backend

6. **RedisConfig** - Upstash Redis caching
   - URL, token, TTL (24 hours)

7. **TranslationConfig** - Google Translate (optional)
   - API key, default language

8. **UnsplashConfig** - Image enrichment (optional)
   - Access key, per page limit

9. **SearchConfig** - Search parameters
   - Max results, hybrid search weights
   - BM25 parameters (k1=1.5, b=0.75)

10. **EnrichmentConfig** - Web enrichment
    - Wikipedia, Unsplash enabled flags
    - Cache TTL (7 days)

11. **MultilingualConfig** - Language support
    - 18 supported languages
    - Auto-detection enabled

12. **LoggingConfig** - Logging setup
    - Level, format, file rotation

13. **DatasetConfig** - HuggingFace dataset
    - Name: `AIAnastasia/georgian-attractions`

## Usage
```python
from config.settings import settings, config

# Access configurations
qdrant_url = settings.qdrant.url
claude_model = settings.claude.model
languages = settings.multilingual.supported_languages

# Validate configuration
if settings.validate():
    print("Configuration valid")

# Print status
settings.print_status()
```

## Environment Variables

All settings loaded from `.env` file:

**Required:**
- `QDRANT_URL`, `QDRANT_API_KEY`
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
- `ANTHROPIC_API_KEY`

**Optional:**
- `UPSTASH_REDIS_URL`, `UPSTASH_REDIS_TOKEN`
- `GOOGLE_TRANSLATE_API_KEY`
- `UNSPLASH_ACCESS_KEY`
- `GROQ_API_KEY`

## Validation

Critical configs validated on startup:
- Qdrant credentials
- Cloudinary credentials  
- Claude API key

Missing required configs will raise `ValueError`.

## Directory Structure

Auto-created directories:
- `data/` - Data storage
- `.cache/` - Cache directory
- `logs/` - Log files

## Supported Languages

18 languages configured in `MultilingualConfig`:
- Core: EN, RU, KA
- European: DE, FR, ES, IT, PT, PL, NL
- Asian: ZH, JA, KO
- Middle Eastern: AR, HE
- South Asian: HI, BN
- Other: TR
