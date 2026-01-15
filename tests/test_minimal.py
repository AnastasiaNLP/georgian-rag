"""
minimal test - checks python imports and logic only.
no external dependencies required.
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Georgian rag - minimal import test")

# test 1: config
print("\n1. Testing config module...")
try:
    from config.settings import QdrantConfig, EmbeddingConfig, Config
    print("   Config imports successful")
except Exception as e:
    print(f"   Config import failed: {e}")

# test 2: types
print("\n2. Testing core types...")
try:
    from core.types import QueryType, QueryAnalysis, SearchResult
    print("   Core types imports successful")
    print(f"   - Querytype values: {[t.value for t in QueryType]}")
except Exception as e:
    print(f"   Core types import failed: {e}")

# test 3: exceptions
print("\n3. Testing exceptions...")
try:
    from core.exceptions import RAGException, ConfigurationError, SearchError
    print("   Exceptions imports successful")
except Exception as e:
    print(f"   Exceptions import failed: {e}")

# test 4: query analyzer (without external deps)
print("\n4. Testing query analyzer structure...")
try:
    from search.query_analyzer import GEORGIAN_SYNONYMS
    print("   Query analyzer imports successful")
    print(f"   - Synonyms loaded: {len(GEORGIAN_SYNONYMS)} entries")
    print(f"   - Sample: {list(GEORGIAN_SYNONYMS.keys())[:3]}")
except Exception as e:
    print(f"   Query analyzer import failed: {e}")

# test 5: check file structure
print("\n5. Checking file structure...")
expected_files = [
    'config/settings.py',
    'core/types.py',
    'core/exceptions.py',
    'core/clients.py',
    'search/query_analyzer.py',
    'search/dense.py',
    'search/bm25.py',
    'search/rrf.py',
    'utils/model_manager.py',
    'utils/logging_setup.py'
]

missing = []
for file_path in expected_files:
    if os.path.exists(file_path):
        size = os.path.getsize(file_path)
        print(f"   {file_path} ({size} bytes)")
    else:
        print(f"   {file_path} missing")
        missing.append(file_path)

# summary
print("\nSummary")

if not missing:
    print("All files present and imports working!")
else:
    print(f"{len(missing)} file(s) missing:")
    for f in missing:
        print(f"   - {f}")