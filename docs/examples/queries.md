# Example Queries

## English
```bash
curl -X POST http://localhost:8000/query \
  -d '{"query": "Best churches in Georgia", "language": "en", "top_k": 5}'
```

## German
```bash
curl -X POST http://localhost:8000/query \
  -d '{"query": "Schönste Orte in Tiflis", "language": "de", "top_k": 3}'
```

## French
```bash
curl -X POST http://localhost:8000/query \
  -d '{"query": "Les plus beaux endroits en Géorgie", "language": "fr", "top_k": 5}'
```

## Russian
```bash
curl -X POST http://localhost:8000/query \
  -d '{"query": "Что посмотреть в Батуми?", "language": "ru", "top_k": 5}'
```
