# Cocktail Bar — Recommendation System & MLOps Pipeline

A home-bar cocktail ordering and recommendation platform: a guest-facing
Telegram bot, an admin bot for inventory management, a FastAPI backend, and
a full cloud-based MLOps pipeline (Airflow → SageMaker → MLflow) for
training and serving a collaborative-filtering recommendation model.


**Components:**
- **Guest Bot** (Telegram) — recommendations, Q&A-based preference discovery, ordering, generated cocktail card images
- **Admin Bot** (Telegram) — inventory management via natural-language commands
- **FastAPI service** — onboarding, recommendation, and ordering endpoints
- **PostgreSQL 16 + pgvector** (AWS RDS) — cocktail catalog, embeddings, orders, inventory
- **Amazon S3** — dataset storage, MLflow artifacts, generated cocktail images (3 buckets)
- **AWS SageMaker** — Managed MLflow (tracking + model registry) and ephemeral Training Jobs
- **Apache Airflow 2.9** (self-hosted via Docker Compose) — pipeline orchestration
- **OpenAI** — preference dialogue, recipe adaptation, glass-type classification for image generation
- **BytePlus Seedream** — cocktail card image generation

## Running locally (Docker Compose)

1. Copy `.env.example` to `.env` and fill in the required values (see
   **Environment Variables** below).

2. Start everything:
```bash
docker compose up -d
```
This brings up: `api`, `guest_bot`, `admin_bot`, `postgres_airflow`,
`airflow-webserver`, `airflow-scheduler`, `airflow-init`.

3. Check the API:
```bash
curl http://localhost:8000/health
```

4. Airflow UI: `http://localhost:8080` (default login: `admin` / `admin`)

## Environment Variables

| Variable | Purpose |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE` | RDS PostgreSQL connection |
| `GUEST_BOT_TOKEN`, `ADMIN_BOT_TOKEN` | Telegram bot tokens |
| `ADMIN_CHAT_ID`, `ADMIN_USER_IDS` | Admin bot access control |
| `API_BASE_URL` | FastAPI base URL, as seen by the bots |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Preference dialogue, recipe adaptation, glass classification |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | (where used for LLM tasks) |
| `ARK_API_KEY` | BytePlus ModelArk — cocktail card image generation |
| `AWS_DEFAULT_REGION` | AWS region for S3/SageMaker calls |
| `DATASET_BUCKET`, `DATASET_KEY` | S3 location of the training dataset |
| `IMAGES_BUCKET` | S3 bucket for generated cocktail card images (public-read) |
| `MLFLOW_TRACKING_URI` | ARN of the SageMaker Managed MLflow App |
| `SAGEMAKER_ROLE_ARN` | IAM role used by SageMaker Training Jobs |
| `COCKTAIL_LOAD_LIMIT` | Optional cap on dataset rows loaded |

## Training Pipeline

The `cocktail_training_pipeline` Airflow DAG (in `dags/`) runs daily:

```
export_data_to_s3 -> preprocess_data -> [train_svd, train_als, train_bpr, train_tuned] -> select_and_register_champion
```

Each training task launches its own ephemeral SageMaker Training Job
(entry points in `training/`). Models are compared by `precision_at_5` in
MLflow and the best challenger is promoted to the `champion` alias in the
`cf-recommender` Model Registry entry. The API serves recommendations from
whichever model currently holds that alias.


## API

### Health check
```bash
curl http://localhost:8000/health
```

### Get recommendations
```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id": 12345, "top_k": 5}'
```

### Session-based recommendations (free-text preferences)
```bash
curl -X POST http://localhost:8000/recommend/session \
  -H "Content-Type: application/json" \
  -d '{"preferences": "sweet citrusy refreshing", "top_k": 5}'
```


## Project Structure

```
dags/                      Airflow DAG (training pipeline)
training/                  Model training code (runs inside SageMaker Training Jobs)
services/                  FastAPI backend, recommender, bots, image generation
services/bot/              Guest & Admin Telegram bot handlers
airflow.Dockerfile         Custom Airflow image (adds git, bakes in Python deps)
docker-compose.yml         Full local/EC2 stack
```
