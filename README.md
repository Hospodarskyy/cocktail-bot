# Cocktail Recommender

Baseline content-based recommendation system for cocktails using sentence-transformers and pgvector.

## Setup

1. Start PostgreSQL:
```bash
docker compose up postgres -d
```

2. Initialize DB:
```bash
uv run -m services.db
```

3. Load dataset (place CSV in data/):
```bash
uv run -m services.data_loader
```

4. Generate embeddings:
```bash
uv run -m services.embedder
```

5. Run API:
```bash
uv run uvicorn main:app --reload
```

## API

### Health check
```bash
curl.exe http://localhost:8000/health
```

### Get recommendations
```bash
curl.exe -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"preferences": "sweet citrusy refreshing", "top_k": 5}'
```
