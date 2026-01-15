# Tests

Test suite and validation scripts for Georgian RAG system.

## Test Files

### Unit Tests

#### `test_config.py`
Configuration validation test.

**Tests:**
- Environment variable loading
- API key validation
- Qdrant connection
- Cloudinary setup
- Config dataclass structure

**Usage:**
```bash
python tests/test_config.py
```

**Expected output:**
```
Qdrant URL set
Qdrant API key set
Claude API key set
Connection successful
Config validation passed!
```

#### `test_minimal.py`
Minimal import test without external dependencies.

**Tests:**
- Python version compatibility
- Module imports
- Basic logic
- No API calls

**Usage:**
```bash
python tests/test_minimal.py
```

**Expected output:**
```
Python version: 3.10.x
All imports successful
Basic logic works
Minimal test passed!
```

#### `test_conversation.py`
ConversationManager functionality test.

**Tests:**
- Conversation creation
- Message adding (user/assistant)
- History retrieval
- Context window generation
- Metadata tracking
- Redis/in-memory fallback
- Statistics tracking

**Usage:**
```bash
python tests/test_conversation.py
```

**Expected output:**
```
Conversationmanager found!
Stats: {total_conversations: 0, total_messages: 0, ...}
History contains 2 messages
Context window: 77 chars
Metadata: {...}
Conversation cleared
Test complete!
```

#### `test_rag_simple.py`
Simple RAG pipeline integration test.

**Tests:**
- RAG initialization
- Component loading (Qdrant, HybridSearch, etc.)
- Query processing
- Search functionality
- Response generation
- End-to-end workflow

**Usage:**
```bash
python tests/test_rag_simple.py
```

**Requires:**
- `.env` with all API keys
- Qdrant accessible
- Claude API key

### Integration Tests

#### `test_all_components.py`
Complete performance and integration test suite.

**Tests:**
- Cache warmup
- Performance monitoring
- Component timing
- Cache statistics
- Search performance
- Full system integration

**Features:**
- Generates performance reports
- Tests all major components
- Measures response times
- Analyzes bottlenecks
- Creates HTML dashboard

**Usage:**
```bash
python tests/test_all_components.py
```

**Outputs:**
- `performance_metrics.json` - Raw metrics data
- `performance_report.html` - Visual dashboard

**Metrics tracked:**
- Query analysis time
- BM25 search time
- Dense search time
- RRF fusion time
- Cache hit rates
- Total pipeline time

#### `test_search_components.py`
Search engine components test.

**Tests:**
- BM25 search
- Dense search
- RRF fusion
- Query analyzer
- PreFilter engine
- Hybrid search integration

**Usage:**
```bash
python tests/test_search_components.py
```

## Validation Scripts

### `check_qdrant_structure.py`
Validate Qdrant collection structure and data quality.

**Checks:**
- Collection exists
- Vector dimensions (384)
- Document count
- Required fields present
- Field types correct
- Sample document structure

**Usage:**
```bash
python tests/check_qdrant_structure.py
```

**Expected output:**
```
Collection: georgian_attractions
Documents: 1715
Vector size: 384

Fields found:
name (str)
description (str)
category (str)
location (str)
image_url (str)
tags (list)
has_processed_image (bool)
language (str)

Sample document:
{
  "name": "Narikala Fortress",
  "category": "Historical Site",
  ...
}

Structure validation passed!
```

### `check_categories.py`
Analyze category distribution in Qdrant database.

**Checks:**
- All unique categories
- Category counts
- Distribution statistics
- Missing/empty categories
- Category naming consistency

**Usage:**
```bash
python tests/check_categories.py
```

**Expected output:**
```
Category analysis
Total documents: 1715
Total unique categories: 15

Category distribution:
1. Religious site: 450 docs (26.2%)
2. Historical site: 380 docs (22.2%)
3. Museum: 220 docs (12.8%)
4. Natural site: 180 docs (10.5%)
5. Cultural center: 150 docs (8.7%)
...

Documents without category: 12
Empty category values: 5
```

### `check_tags_detail.py`
Detailed tag analysis and statistics.

**Checks:**
- All unique tags
- Tag frequency
- Documents per tag
- Tag distribution
- Popular tags
- Unused tags

**Usage:**
```bash
python tests/check_tags_detail.py
```

**Expected output:**
```
Tag analysis
Total documents: 1715
Documents with tags: 1650
Total unique tags: 234

Top 20 tags:
1. history (450 docs)
2. architecture (380 docs)
3. unesco (220 docs)
4. tourism (210 docs)
5. cultural (180 docs)
...

Tags by frequency:
- Used 100+ times: 15 tags
- Used 50-99 times: 35 tags
- Used 10-49 times: 84 tags
- Used 1-9 times: 100 tags

Documents without tags: 65
```

## Running Tests

### Quick Test (No Dependencies)
```bash
# minimal test - just python
python tests/test_minimal.py
```

### Configuration Test
```bash
# requires .env file
python tests/test_config.py
```

### Full Test Suite
```bash
# run all tests
python tests/test_config.py
python tests/test_minimal.py
python tests/test_conversation.py
python tests/test_rag_simple.py
python tests/test_search_components.py
python tests/test_all_components.py
```

### Validation Scripts
```bash
# data quality checks
python tests/check_qdrant_structure.py
python tests/check_categories.py
python tests/check_tags_detail.py
```

### With Pytest
```bash
# install pytest
pip install pytest

# run all tests
pytest tests/ -v

# run specific test
pytest tests/test_conversation.py -v

# run with coverage
pytest tests/ --cov=./ --cov-report=html
```

## Test Requirements

### Minimal Requirements
Files: `test_minimal.py`

**Needs:** Python 3.8+

### Standard Requirements
Files: `test_config.py`, `test_conversation.py`

**Needs:**
- `.env` file with credentials
- `requirements.txt` installed

### Full Requirements
Files: `test_rag_simple.py`, `test_all_components.py`, `test_search_components.py`

**Needs:**
- All standard requirements
- Qdrant accessible
- Claude API key
- Redis (optional)

### Validation Requirements
Files: `check_*.py` scripts

**Needs:**
- Qdrant accessible
- `.env` with QDRANT_URL and QDRANT_API_KEY

## Environment Setup

**Create `.env` file:**
```bash
# required for most tests
QDRANT_URL=https://your-qdrant-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key
COLLECTION_NAME=georgian_attractions

# claude api
ANTHROPIC_API_KEY=sk-ant-your_key_here

# groq api
GROQ_API_KEY=gsk_your_key_here

# redis (optional)
UPSTASH_REDIS_URL=https://your-redis.upstash.io
UPSTASH_REDIS_TOKEN=your_token_here

# cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

## Test Organization

### By Purpose

**Unit tests:**
- `test_minimal.py` - basic functionality
- `test_config.py` - configuration
- `test_conversation.py` - conversation manager
- `test_search_components.py` - search engines

**Integration tests:**
- `test_rag_simple.py` - end-to-end rag
- `test_all_components.py` - full system

**Validation scripts:**
- `check_qdrant_structure.py` - data structure
- `check_categories.py` - category quality
- `check_tags_detail.py` - tag quality

### By Dependencies

**No external services:**
- `test_minimal.py`

**Needs .env only:**
- `test_config.py`
- `test_conversation.py` (works with in-memory fallback)

**Needs qdrant:**
- `test_search_components.py`
- `check_qdrant_structure.py`
- `check_categories.py`
- `check_tags_detail.py`

**Needs everything:**
- `test_rag_simple.py`
- `test_all_components.py`

## CI/CD Integration

**Example github actions:**
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run minimal tests
        run: python tests/test_minimal.py
      
      - name: Run config tests
        env:
          QDRANT_URL: ${{ secrets.QDRANT_URL }}
          QDRANT_API_KEY: ${{ secrets.QDRANT_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python tests/test_config.py
          python tests/test_conversation.py
      
      - name: Run pytest
        run: pytest tests/ -v
```

## Debugging

**Enable verbose logging:**
```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Test specific component:**
```python
# in test file
def test_specific_feature():
    # your test code
    pass

if __name__ == "__main__":
    test_specific_feature()
```

**Check test output:**
```bash
# run with verbose output
python tests/test_conversation.py -v

# or with pytest
pytest tests/test_conversation.py -v -s
```

## Performance Testing

**Run performance suite:**
```bash
python tests/test_all_components.py
```

**View results:**
```bash
# open html report
open performance_report.html

# or view json
cat performance_metrics.json | jq
```

**Analyze bottlenecks:**

Check `performance_report.html` for:
- Component timings
- Cache hit rates
- Slow operations
- Optimization recommendations

## Notes

- All tests use `.env` for configuration
- Some tests make real API calls (may incur costs)
- Validation scripts are read-only (safe)
- Performance tests generate HTML reports
- Tests handle missing dependencies gracefully
- Tests can run individually or via pytest
- Mock data used where possible to reduce API calls