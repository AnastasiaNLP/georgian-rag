"""
simple configuration test - show me the result!

usage:
    python test_config_simple.py
"""

import sys
from pathlib import Path

# add path to project
project_root = Path(__file__).parent.parent  # go up 2 levels
sys.path.insert(0, str(project_root))

print("\nConfiguration test")

# test 1: load .env
print("\n1. Checking .env file...")
env_file = project_root / '.env'
if env_file.exists():
    print(f"   .env found: {env_file}")
else:
    print(f"   .env not found: {env_file}")
    sys.exit(1)

# test 2: import config
print("\n2. Loading configuration...")
try:
    from config.settings import settings, config
    print("   Config successfully imported")
except Exception as e:
    print(f"   Import error: {e}")
    sys.exit(1)

# test 3: check qdrant
print("\n3. Checking qdrant configuration...")
try:
    print(f"   Url: {settings.qdrant.url[:60]}...")
    print(f"   Api key: {'***' + settings.qdrant.api_key[-10:] if settings.qdrant.api_key else 'not set'}")
    print(f"   Collection: {settings.qdrant.collection_name}")
    print(f"   Vector size: {settings.qdrant.vector_size}")

    if settings.qdrant.url and settings.qdrant.api_key:
        print("   Qdrant configured")
    else:
        print("   Qdrant not configured")
except Exception as e:
    print(f"   Error: {e}")

# test 4: check claude/anthropic
print("\n4. Checking claude api...")
try:
    if settings.claude.api_key:
        print(f"   Api key: sk-ant-***{settings.claude.api_key[-10:]}")
        print(f"   Model: {settings.claude.model}")
        print(f"   Max tokens: {settings.claude.max_tokens}")
        print("   Claude api configured")
    else:
        print("   Anthropic_api_key or claude_api_key not set")
except Exception as e:
    print(f"   Error: {e}")

# test 5: check embedding model
print("\n5. Checking embedding configuration...")
try:
    print(f"   Model: {settings.embedding.model_name[:50]}...")
    print(f"   Device: {settings.embedding.device}")
    print(f"   Batch size: {settings.embedding.batch_size}")
    print("   Embedding configured")
except Exception as e:
    print(f"   Error: {e}")

# test 6: check optional services
print("\n6. Checking optional services...")

# redis
try:
    if settings.redis.url and settings.redis.token:
        print(f"   Redis: {settings.redis.url[:40]}...")
    else:
        print("   Redis: not configured (optional)")
except:
    print("   Redis: not configured")

# google translate
try:
    if settings.translation.api_key:
        print(f"   Google translate: configured")
    else:
        print("   Google translate: not configured (optional)")
except:
    print("   Google translate: not configured")

# cloudinary
try:
    if settings.cloudinary.cloud_name:
        print(f"   Cloudinary: {settings.cloudinary.cloud_name}")
    else:
        print("   Cloudinary: not configured (optional)")
except:
    print("   Cloudinary: not configured")

# unsplash
try:
    if settings.unsplash.access_key:
        print(f"   Unsplash: configured")
    else:
        print("   Unsplash: not configured (optional)")
except:
    print("   Unsplash: not configured")

# test 7: check search parameters
print("\n7. Checking search parameters...")
try:
    print(f"   Max results: {settings.search.max_results}")
    print(f"   Dense weight: {settings.search.dense_weight}")
    print(f"   Bm25 weight: {settings.search.bm25_weight}")
    print(f"   Bm25 k1: {settings.search.bm25_k1}")
    print(f"   Bm25 b: {settings.search.bm25_b}")
    print("   Search parameters loaded")
except Exception as e:
    print(f"   Error: {e}")

# final report
print("\nSummary")

# check critical parameters
critical_ok = True

if not settings.qdrant.url or not settings.qdrant.api_key:
    print("Qdrant not configured - required!")
    critical_ok = False

if not settings.claude.api_key:
    print("Claude api key not configured - required!")
    critical_ok = False

if critical_ok:
    print("All required parameters configured!")
else:
    print("Not all required parameters configured")

sys.exit(0 if critical_ok else 1)