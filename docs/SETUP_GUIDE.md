#  Georgian RAG - Setup Guide

Complete setup instructions for the Georgian Attractions RAG system.

---

## 📋 Prerequisites

- **Python**: 3.10 or higher
- **Git**: For cloning the repository
- **API Keys**: Required for external services

---

##  Installation Steps

### 1. Clone Repository

```bash
git clone <your-repo-url>
cd georgian_rag
```

### 2. Create Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy example file
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

### Required API Keys:

```env
# Qdrant (Vector Database)
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_key

# Anthropic (Claude LLM)
ANTHROPIC_API_KEY=sk-ant-your_key

# LangSmith (Monitoring - Optional)
LANGSMITH_API_KEY=ls__your_key

# Cloudinary (Images)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Upstash Redis (Caching - Optional)
UPSTASH_REDIS_URL=https://your-redis.upstash.io
UPSTASH_REDIS_TOKEN=your_token

# Google Translate (Optional)
GOOGLE_TRANSLATE_API_KEY=AIza...

# Unsplash (Images - Optional)
UNSPLASH_ACCESS_KEY=your_unsplash_key

# SerpAPI (Web Search - Optional)
SERPAPI_API_KEY=your_serpapi_key
```

---

##  Testing Installation

### Run Basic Tests

```bash
# Test configuration
python test_config.py

# Test minimal setup
python test_minimal.py

# Test search components
python test_search_components.py
```

### Expected Output:

```
All tests passed!
Configuration loaded successfully
Search components initialized
```

---

##  Quick Start

### Basic Usage Example

```python
from rag import EnhancedGeorgianRAG
from core.clients import QdrantSystem
from search.hybrid import HybridSearchEngine
import asyncio


async def main():
    # Initialize Qdrant
    qdrant = QdrantSystem(
        url="your_qdrant_url",
        api_key="your_qdrant_key",
        collection_name="georgian_attractions"
    )
    qdrant.setup()

    # Initialize Hybrid Search
    hybrid_search = HybridSearchEngine(
        qdrant_client=qdrant.client,
        collection_name="georgian_attractions"
    )
    hybrid_search.initialize()

    # Initialize RAG
    rag = EnhancedGeorgianRAG(
        qdrant_system=qdrant,
        hybrid_search_integrator=hybrid_search,
        api_keys={
            'anthropic_api_key': 'sk-ant-...',
            'langsmith_api_key': 'ls__...',
            'google_translate_api_key': 'AIza...',
            'unsplash_access_key': '...',
            'serpapi_api_key': '...',
            'upstash_url': 'https://...',
            'upstash_token': '...'
        }
    )

    # Initialize system
    if await rag.initialize():
        print(" RAG system initialized!")

        # Ask question
        result = await rag.answer_question(
            query="Tell me about Svetitskhoveli Cathedral",
            target_language="en",
            enable_web_enrichment=True
        )

        print(f"\n Response:\n{result['response']}")
        print(f"\n Metadata: {result['metadata']}")


asyncio.run(main())
```

---

##  Project Structure

```
georgian_rag/
├── config/              # Configuration settings
├── core/                # Core types and clients
├── search/              # Search components (BM25, Dense, Hybrid)
├── multilingual/        # Language detection & translation
├── conversation/        # Conversation management
├── rag/                 # RAG context assembly
├── llm/                 # LLM integration (Claude)
├── enrichment/          # Web enrichment (Wikipedia, Unsplash)
├── utils/               # Utilities (cache, logging, queue)
├── pipeline/            # Main orchestrator
├── tests/               # Test files
├── requirements.txt     # Dependencies
├── .env.example         # Environment template
└── README.md            # Main documentation
```

---

## 🔍 Troubleshooting

### Issue: Import errors

```bash
# Make sure you're in the correct directory
cd georgian_rag

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Issue: Qdrant connection failed

```bash
# Check environment variables
cat .env | grep QDRANT

# Test connection
python -c "from qdrant_client import QdrantClient; client = QdrantClient(url='your_url', api_key='your_key'); print(client.get_collections())"
```

### Issue: Redis connection failed

```bash
# Redis is optional - system will fallback to in-memory cache
# Check Upstash credentials in .env
cat .env | grep UPSTASH
```

### Issue: Model download slow

```bash
# Models are cached after first download
# Default cache: ~/.cache/huggingface/

# Pre-download models (optional)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"
```

---

##  Performance Optimization

### 1. Enable Redis Caching

```env
# Add to .env
UPSTASH_REDIS_URL=https://your-redis.upstash.io
UPSTASH_REDIS_TOKEN=your_token
```

### 2. Adjust Cache TTL

```python
# In your code
cache_manager = CacheManager(
    redis_client=redis_client,
    default_ttl=3600  # 1 hour instead of 24 hours
)
```

### 3. Background Task Workers

```python
# Increase workers for faster background processing
background_queue = BackgroundTaskQueue(max_workers=4)
```

---

##  Security Best Practices

1. **Never commit .env file**
   - Already in .gitignore
   - Use .env.example as template

2. **Rotate API keys regularly**
   - Especially for production deployments

3. **Use environment-specific configs**
   - `.env.development`
   - `.env.production`

4. **Limit Redis access**
   - Use Upstash with IP whitelisting
   - Set strong passwords

---

##  Additional Resources

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [SentenceTransformers](https://www.sbert.net/)
- [LangSmith Tracing](https://docs.smith.langchain.com/)

---

##  Support

For issues and questions:
- Check troubleshooting section above
- Review error logs in `logs/` directory
- Contact: [your-email@example.com]

---

**Last Updated**: 2025-12-09
**Version**: 1.0.0