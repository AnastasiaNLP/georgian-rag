"""
detailed tag check in database
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from core.clients import get_qdrant_client
from config.settings import settings

print("\nDetailed tag check")

client = get_qdrant_client()

# get first 10 documents
result = client.scroll(
    collection_name=settings.qdrant.collection_name,
    limit=10,
    with_payload=True,
    with_vectors=False
)

print("\nFirst 10 documents:")

for i, point in enumerate(result[0], 1):
    tags = point.payload.get('tags', None)
    print(f"\nDocument {i}:")
    print(f"   ID: {point.id}")
    print(f"   Name: {point.payload.get('name', '')[:50]}")
    print(f"   Tags type: {type(tags)}")
    print(f"   Tags value: {tags}")
    print(f"   Tags length: {len(tags) if tags else 0}")
    # check all keys with 'tag' in name
    tag_keys = [k for k in point.payload.keys() if 'tag' in k.lower()]
    if tag_keys:
        print(f"   Keys with 'tag': {tag_keys}")

print("\nCheck completed")