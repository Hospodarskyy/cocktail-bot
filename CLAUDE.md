# Cocktail Recommender Bot — Project Handoff Document

## Project Overview

A Telegram-based cocktail ordering system for home parties. Born from a personal hobby (bartending tools + frequent guest visits), built as a semester-long MLOps university course project. Dual goals: satisfy course requirements and build something genuinely usable.

**Core idea:** guests order cocktails through Telegram like ordering at a real bar — getting personalized recommendations, discovering new drinks, and having a conversational experience — while the host (admin) gets recipe notifications, inventory management, and reduced manual involvement during parties.

---

## System Roles

**Guest** — interacts via a dedicated Telegram bot (`@bartenderrrr_bot`). Can onboard (describe preferences), get personalized recommendations, place orders, optionally specify preferences per order (e.g. "not too bitter").

**Admin (host)** — interacts via a separate Telegram bot (`@bar_admin_bot`). Manages inventory, receives automatic order notifications with full recipes, views shopping lists, sees active orders.

**Why two separate bots:** simpler UX, cleaner separation of concerns, easier to reason about each bot's command set. Both bots talk to the same FastAPI backend and PostgreSQL database — no duplicated business logic.

---

## Architecture (current + target state)

```
Guest Bot (Telegram) ──┐
                        ├──► FastAPI ──► PostgreSQL (+pgvector)
Admin Bot (Telegram) ───┘         │
                                  ├──► Amazon Bedrock (LLM + image gen) [future]
                                  ├──► Redis (async events) [future]
                                  └──► S3/MinIO (training data, model artifacts)

Airflow ──► exports data from PostgreSQL ──► MinIO/S3 (training dataset)
```

Long-term target architecture (from design doc, not yet implemented): AWS-based with RDS PostgreSQL+pgvector, ElastiCache Redis, Amazon Bedrock, SageMaker, S3, ECS Fargate. Microservices: Bot Gateway, Admin Service, User Service, Order Service, Recipe Service, Recommendation Service, Image Service. See full design doc for details (already submitted as Assignment 1).

---

## ✅ What's Already Done

### Infrastructure (local, Docker Compose)
- `docker-compose.yml` orchestrates: `postgres` (pgvector/pgvector:pg16), `postgres_airflow` (separate DB for Airflow metadata), `minio` (S3-compatible local storage), `api` (FastAPI), `airflow-init` + `airflow-webserver` + `airflow-scheduler` (Airflow **2.9.0** — pinned after Airflow 3.x proved too unstable for local dev: command renames, auth changes, migration errors).
- `Dockerfile` builds the API service using `uv` for dependency management, downloads the Hotaling cocktail dataset from Kaggle at build time (via `kaggle` CLI with credentials passed as build args from `.env`, written to `/root/.kaggle/kaggle.json`).
- `.env` holds: `KAGGLE_USERNAME`, `KAGGLE_KEY`, `GUEST_BOT_TOKEN`, `ADMIN_BOT_TOKEN` (tokens already obtained from BotFather, not yet wired into code).

### Data layer
- Dataset: **Hotaling & Co. cocktail dataset** (`shuyangli94/cocktails-hotaling-co` on Kaggle — note: this is the correct dataset ID, an earlier wrong ID `hotaling/cocktail-dataset` caused 403 errors). 687 cocktails loaded.
- `services/db.py` — connection handling + schema init. Tables so far:
  - `cocktails` (id, name, category, ingredients, garnish, instructions, flavor_description, embedding vector(384))
  - `users` (id BIGINT = Telegram chat_id, name, preferences_text, embedding vector(384))
  - `orders` (id, user_id FK, cocktail_id FK, preferences, created_at)
- `services/data_loader.py` — loads Hotaling CSV into `cocktails` table.
- `services/embedder.py` — generates embeddings via `sentence-transformers` (`all-MiniLM-L6-v2`) for all cocktails, stores in pgvector. Uses tqdm progress bar. Text built from name+ingredients+garnish+instructions.
- `services/users.py` — `onboard_user()` encodes free-text preferences into a 384-dim embedding and upserts into `users`; `get_user_embedding()` fetches it back.
- `services/recommender.py` — cosine similarity search via pgvector (`ORDER BY embedding <=> %s::vector`), now refactored to take `user_id` (looks up stored embedding) instead of raw text.

### API (FastAPI, `main.py`)
- Lifespan handler: initializes DB schema on startup, and — **only if the `cocktails` table is empty** — auto-loads the dataset and generates embeddings (idempotent, avoids reloading on every restart since data persists in the `postgres_data` Docker volume).
- `GET /health`
- `POST /onboard` — `{user_id, name, preferences}` → stores user embedding
- `POST /recommend` — `{user_id, top_k}` → top-K cosine-similarity cocktails for that user; raises 400 if user hasn't onboarded yet
- `POST /order` — `{user_id, cocktail_id, preferences (optional)}` → logs order into `orders` table, fetches recipe, pushes a Telegram message to the admin via `services/notifications.py` (`notify_admin`, using `ADMIN_BOT_TOKEN` + `ADMIN_CHAT_ID` env vars). Implemented and verified end-to-end (curl → DB row → Telegram message received). Logic lives in `services/orders.py` (`place_order`). Raw recipe only — no Bedrock story/adaptation yet (deferred).

### Pipeline / orchestration
- `dags/export_to_minio.py` — Airflow DAG (`export_cocktails_to_minio`, `@daily`, `catchup=False`) that reads the `cocktails` table from PostgreSQL via pandas, converts to CSV, and uploads to a MinIO bucket (`training-data`) via boto3. Verified working — file `cocktails_20260628_180445.csv` confirmed present in MinIO UI.
- This DAG is explicitly a **simulation/placeholder**: in production it should export `orders` (real order history) for CF model retraining, not the static cocktail catalog. Currently exports cocktails because no real order data exists yet.
- Airflow dependencies (`boto3`, `pandas`, `psycopg2-binary`) installed via `_PIP_ADDITIONAL_REQUIREMENTS` env var (acceptable for dev only, not production — should be baked into a custom image eventually).

### Project hygiene
- `uv` used for all Python dependency management (`pyproject.toml` + `uv.lock`).
- Package structure uses `services/` as a proper Python package (`__init__.py` present); imports inside the package use **relative imports** (`from .db import ...`) so files work both as `uv run -m services.module` and via direct path execution — this was a recurring point of confusion, now resolved.
- `.gitignore` excludes `.venv/`, `__pycache__/`, `data/` (dataset now downloaded at build time, not committed), `.env`.

---

## 🚧 What's Next (immediate, in-progress)

`/order` is done (see above). Now building the two Telegram bots. Planned and agreed but **not yet coded**:

### Guest Bot (`@bartenderrrr_bot`) — not yet coded
- `/start` — minimal onboarding: ask one free-text question ("describe what kind of cocktail you'd like"), send the raw answer to `POST /onboard`
- `/recommend` — call `POST /recommend` with the guest's Telegram `chat_id` as `user_id`; for each of the top-5 results, send a message with inline keyboard buttons `[✓ Order] [👎 Not for me]` (callback_data encodes cocktail_id + action)
- Callback handler for `Order` button → ask "any preferences?" with buttons `[No preferences] [Write preferences]` → if free text, capture it → call `POST /order`
- Callback handler for `Not for me` → just log as negative signal (no backend endpoint for this yet — needs to be added, e.g. extend `/order` flow or a separate `/feedback` endpoint)
- `/menu` — currently a stub (no web menu exists yet)

### Admin Bot (`@bar_admin_bot`) — not yet coded
- `/start` — greeting
- `/inventory` — placeholder; **no inventory table or logic exists yet at all** — this is a bigger gap (see below)
- `/orders` — list active orders (needs a query against `orders` table)
- Passive: receives order notifications pushed directly from FastAPI (no bot-side polling needed)

### Suggested code layout for the bots (agreed, not yet created)
```
services/
  bot/
    __init__.py
    main.py              # entrypoints for both bots (or two separate run scripts)
    handlers/
      guest.py            # /start, /recommend, order flow
      admin.py             # /inventory, /orders, notification sending
    keyboards.py          # inline keyboard builders
```
Bots should be added as additional services in `docker-compose.yml`, talking to FastAPI over REST — not touching PostgreSQL directly.

Library choice: `python-telegram-bot` (already discussed, not yet added via `uv add`).

---

## 🔭 Designed But Deliberately Deferred (from Assignment 1 design doc — not started)

These are fully specified in the design doc but intentionally postponed until the bot MVP works end-to-end:

- **Inventory management** — no `inventory` or `ingredients` tables exist yet. Needed for: admin stock CRUD, feasibility filtering (only show makeable cocktails), automatic decrement on order.
- **Ingredient substitution pipeline** — auto-triggered on inventory change, finds "almost-available" cocktails (1 ingredient short), calls Bedrock to generate substitute recipe, caches in an `adapted_recipes` table (always derived from the *original* recipe, never chained adaptations — explicit design constraint to prevent drift).
- **Cocktail story generation** — Bedrock-generated 2-3 sentence origin story per cocktail, cached on first generation in the `cocktails` table, included in admin order notifications.
- **Preference-based recipe adaptation** — when a guest adds free-text preferences at order time, Bedrock adapts the recipe before the admin sees it.
- **Image Service** — Bedrock image generation for each cocktail, stored in S3, `image_url` cached per cocktail, shown in recommendation cards.
- **Web Menu** — static site reading the full cocktail catalog from PostgreSQL directly (bypassing the bot/API), linked via `/menu`.
- **Collaborative filtering (Phase 2 of recommender)** — matrix factorization model trained in SageMaker on real order history (CTR signals from "Not for me" taps + order acceptance), re-ranks the content-based candidates. Currently only Phase 1 (pure content-based cosine similarity) exists.
- **Redis async event bus** — `order.completed` and `inventory.changed` pub/sub events driving Admin Service inventory decrement, User Service profile updates, Recipe Service substitution triggers. Not implemented; currently everything is synchronous within FastAPI request handlers.
- **Shopping list generation** — admin command that uses Bedrock to suggest a shopping list based on inventory + popular cocktails.

---

## 🎓 Course Assignment Context

- **Assignment 1** (submitted): high-level design doc — problem statement, architecture diagram (Mermaid, iterated extensively, final version is a flat single-graph LR diagram without nested subgraphs for readability — see chat history for the exact code and the layered SVG reference used to manually redraw it cleanly in draw.io), ML models description, datasets, microservices breakdown, tools/tech table, ML metrics, success criteria.
- **Assignment 2** (current, mostly done): baseline model + FastAPI wrapper + Docker container + Airflow job exporting training data to object storage. This is what's described in "What's Already Done" above.
- **Assignment 3** (future): add MLFlow tracking for the training service (MLFlow backend — self-hosted or Databricks — save training artifacts to object storage, make the model service scalable, implement champion-challenger deployment scheme).
- **Assignment 4** (future): finish the full pipeline — orchestrated end-to-end on SageMaker/Databricks/Kubeflow, combining all previous pieces (Airflow data gathering → processing → training → tuning [optional] → model registry → metric logging → champion/challenger evaluation → serving), plus a short demo presentation.

**Important:** Telegram bot work is *not* a required deliverable for any MLOps assignment — it's the product layer that makes the project a real, demoable system and the source of real training data (order history) for future CF model work. It can proceed in parallel with or independently of the MLOps assignments' timeline.

---

## Known Gotchas / Lessons Learned (worth preserving)

- **PowerShell vs zsh**: user develops on both Windows (PowerShell) and Mac (zsh). `curl` in PowerShell aliases to `Invoke-WebRequest` — must use `curl.exe` explicitly; line continuation is backtick on PowerShell, backslash on zsh/bash.
- **Python relative imports**: running a file directly (`uv run services/foo.py`) vs as a module (`uv run -m services.foo`) changes `sys.path` resolution — relative imports (`from .db import`) only work with `-m`. Standardized on `-m` for all script invocations.
- **Kaggle dataset ID**: correct is `shuyangli94/cocktails-hotaling-co`, not `hotaling/cocktail-dataset` (404/403 errors otherwise). Kaggle CLI auth requires `~/.kaggle/kaggle.json` (`{"username":..., "key":...}`), not plain env vars, despite some docs suggesting otherwise.
- **Airflow version**: stick with **2.9.0** for local Docker Compose dev. Airflow 3.x changes (`webserver`→`api-server` command rename, `users create` removed in favor of `_AIRFLOW_WWW_USER_CREATE` env var which still generates a random password unpredictably, separate `dag-processor`/`triggerer` services required, execution_date DB migration errors when reusing old volumes) made it too unstable for a quick class project. If revisiting Airflow 3.x, start fresh with the official `docker-compose.yaml` from `airflow.apache.org/docs/apache-airflow/<version>/docker-compose.yaml` rather than hand-rolling it.
- **Airflow + app DB conflict**: Airflow needs its own PostgreSQL database (`postgres_airflow` service, separate from the app's `postgres`/`cocktail_db`) — sharing one Postgres instance/database between the app and Airflow metadata causes schema migration failures.
- **Docker volumes persist data** — `postgres_data` volume means dataset/embeddings only need to be (re)generated once; lifespan code checks `COUNT(*)` on `cocktails` before reloading, making restarts fast and idempotent.
- **`.env` edits don't reach a running container** — `docker-compose.yml` substitutes `${VAR}` into a service's environment only at container *creation* time. Editing `.env` while the container is already running has no effect until you recreate it (`docker compose up -d <service>` — no `--build` needed if only `.env` changed, not code).
- **Telegram `sendMessage` needs the recipient to have messaged the bot first** — a bot can't push to a chat_id that has never started a conversation with it (`400: chat not found` otherwise). The admin must send any message (e.g. `/start`) to `@bar_admin_bot` once; since the Admin Bot isn't coded yet, it won't reply, but the message still registers the chat so push notifications work.
- **`notify_admin()` currently doesn't check the Telegram API response** — failures (bad token, chat not found, etc.) are silent. Worth hardening with response-status logging before relying on it for the real bots.
