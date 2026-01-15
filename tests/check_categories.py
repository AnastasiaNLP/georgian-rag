"""
Checking ALL categories in the Qdrant database
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.clients import get_qdrant_client
from config.settings import settings
from collections import Counter

print("Full check of all categories in the QDRANT database.")

client = get_qdrant_client()

# information about the collection
print("\n Collection Information:")
collection_info = client.get_collection(settings.qdrant.collection_name)
total_points = collection_info.points_count
print(f"   Name: {settings.qdrant.collection_name}")
print(f"   Number of points:{total_points}")

# we receive ALL documents through pagination
print(f"\n Collect all {total_points} documents...")

categories = []
tags_list = []
offset = None
retrieved = 0

while True:
    result = client.scroll(
        collection_name=settings.qdrant.collection_name,
        limit=100,  # 100 at a time
        offset=offset,
        with_payload=True,
        with_vectors=False
    )

    points, next_offset = result

    if not points:
        break

    for point in points:
        category = point.payload.get('category', '')
        if category:
            categories.append(category)

        tags = point.payload.get('tags', [])
        if tags:
            tags_list.extend(tags)

    retrieved += len(points)
    print(f" Processed: {retrieved}/{total_points}", end='\r')

    if next_offset is None:
        break

    offset = next_offset

print(f"\n Documents processed: {retrieved}")

#  let's count the categories
counter = Counter(categories)

print("\n Top 50 categories:")
for category, count in counter.most_common(50):
    print(f"   {count:4d} | {category}")

print()
print(f"Total unique categories: {len(counter)}")
print(f"Total documents with categories:{len(categories)}")

# check the keywords for the filters
print("\n Detailed filter check")

keywords_check = {
    'is_religious_site': {
        'words': ['Church', 'Cathedral', 'Monastery', 'Temple', 'Церковь', 'Монастырь', 'Храм', 'Собор'],
        'found': []
    },
    'is_nature_tourism': {
        'words': ['National Park', 'Park', 'Nature', 'Waterfall', 'Mountain', 'Парк', 'Водопад', 'Lake', 'Озеро'],
        'found': []
    },
    'is_historical_site': {
        'words': ['Fortress', 'Castle', 'Palace', 'Крепость', 'Замок', 'Дворец', 'Historic'],
        'found': []
    },
    'is_cultural_heritage': {
        'words': ['Museum', 'Gallery', 'Theater', 'Winery', 'Музей', 'Галерея', 'Винодельня', 'Театр'],
        'found': []
    }
}

# checking categories
for category in categories:
    category_lower = category.lower()

    for filter_name, data in keywords_check.items():
        for word in data['words']:
            if word.lower() in category_lower:
                data['found'].append(category)
                break

# we display the results
for filter_name, data in keywords_check.items():
    found_count = len(data['found'])
    unique_categories = set(data['found'])

    print(f"\n   {'✅' if found_count > 10 else '⚠️' if found_count > 0 else '❌'} {filter_name}:")
    print(f"Documents found: {found_count} ({found_count/len(categories)*100:.1f}%)")
    print(f"Unique categories: {len(unique_categories)}")

    if unique_categories:
        print(f"Examples of categories:")
        for cat in list(unique_categories)[:10]:
            count_cat = data['found'].count(cat)
            print(f"         • {cat} ({count_cat} док.)")

# checking tags
print("\n Checking tags")

if tags_list:
    tag_counter = Counter(tags_list)
    print(f"Total tags found: {len(tags_list)}")
    print(f"Unique tags: {len(tag_counter)}")
    print(f"\n")
    for tag, count in tag_counter.most_common(30):
        print(f"Top 30 tags: {count:4d} | {tag}")
else:
    print("No tags found or empty")

# final recommendations
print("\n Final recommendations")

threshold_keep = 50  # minimum documents for the filter to work

for filter_name, data in keywords_check.items():
    found_count = len(data['found'])
    percentage = (found_count / len(categories) * 100) if categories else 0

    if found_count >= threshold_keep:
        print(f"Leave {filter_name}: {found_count} documents ({percentage:.1f}%)")
    elif found_count > 0:
        print(f"Solve {filter_name}: {found_count} documents ({percentage:.1f}%)")
    else:
        print(f"Delete {filter_name}: documents")

print("Full check completed")
