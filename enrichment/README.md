# Web Enrichment (Optional)

**Status:** Not currently active in production.

Web content enrichment with Wikipedia, Unsplash, and SerpAPI.

## Files

- `location.py` - Google Geocoding enrichment
- `persister.py` - Qdrant metadata updates
- `web.py` - Wikipedia, Unsplash, SerpAPI integration

## Usage

Currently disabled. To enable, configure in `.env`:
```bash
UNSPLASH_ACCESS_KEY=your_key
SERPAPI_API_KEY=your_key  
GOOGLE_GEOCODING_API_KEY=your_key
```

## Notes

- Base Qdrant collection already contains images (Cloudinary)
- Enrichment adds: Wikipedia descriptions, additional images
- Optional feature for future use
