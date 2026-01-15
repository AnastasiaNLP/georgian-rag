"""
check qdrant data structure
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from core.clients import get_qdrant_client
from config.settings import settings
import json

print("\nQdrant database structure check")

client = get_qdrant_client()

# collection information
print("\n1. Collection information:")
collection_info = client.get_collection(settings.qdrant.collection_name)
print(f"   name: {settings.qdrant.collection_name}")
print(f"   points count: {collection_info.points_count}")
print(f"   vector size: {collection_info.config.params.vectors.size}")

# get several example points
print("\n2. Document examples (first 3):")
points = client.scroll(
    collection_name=settings.qdrant.collection_name,
    limit=3,
    with_payload=True,
    with_vectors=False
)

for i, point in enumerate(points[0], 1):
    print(f"\n   Document {i} (ID: {point.id}):")
    print(f"   Payload keys: {list(point.payload.keys())}")
    # show all fields
    for key, value in point.payload.items():
        if isinstance(value, str) and len(value) > 100:
            print(f"      {key}: {value[:100]}...")
        else:
            print(f"      {key}: {value}")

# check geolocation fields
print("\n3. Geolocation check:")
sample = points[0][0]
geo_fields = [k for k in sample.payload.keys() if 'lat' in k.lower() or 'lon' in k.lower() or 'geo' in k.lower() or 'location' in k.lower()]
print(f"   Found geolocation fields: {geo_fields}")
if geo_fields:
    for field in geo_fields:
        print(f"      {field}: {sample.payload.get(field)}")

# all unique keys in payload
print("\n4. All unique fields in database:")
all_points = client.scroll(
    collection_name=settings.qdrant.collection_name,
    limit=100,
    with_payload=True,
    with_vectors=False
)

all_keys = set()
for point in all_points[0]:
    all_keys.update(point.payload.keys())

print(f" Total unique fields: {len(all_keys)}")
for key in sorted(all_keys):
    print(f"      - {key}")

# check data types
print("\n5. Field data types (from first document):")
for key, value in sample.payload.items():
    print(f"   {key}: {type(value).__name__}")

print("\nCheck completed")