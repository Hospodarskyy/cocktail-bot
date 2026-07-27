"""
Collaborative filtering training pipeline for the cocktail recommender.

Trains three candidate models (popularity baseline, ALS, truncated SVD)
on implicit user-cocktail interactions, evaluates each with precision@5,
logs everything to MLflow, and promotes the best one to the "champion"
alias in the MLflow Model Registry if it beats the current champion.

Reads its input data (orders + cocktail categories) from S3, where the
`export_orders_to_s3` Airflow DAG deposits fresh CSV snapshots daily —
not from RDS directly, since this script is designed to run inside a
SageMaker Training Job with no VPC access to the database.

Run locally (e.g. in Codespace, against the EC2 MLflow server):
    export MLFLOW_TRACKING_URI=http://<ec2-ip>:5000
    export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
    export DATASET_BUCKET=cocktail-mlops-data-oles
    python -m training.train_cf
"""

import os
import random
from collections import defaultdict
from io import StringIO

import boto3
import joblib
import mlflow
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds

MLFLOW_EXPERIMENT = "cf_recommender_comparison"
MODEL_REGISTRY_NAME = "cf_recommender"
DATASET_BUCKET = os.getenv("DATASET_BUCKET", "cocktail-mlops-data-oles")
ORDERS_KEY = "order-history/orders.csv"
COCKTAILS_CATEGORIES_KEY = "order-history/cocktails_categories.csv"
MIN_REAL_ORDERS = 50          # below this, we bootstrap with synthetic orders
N_SYNTHETIC_USERS = 60
ORDERS_PER_SYNTHETIC_USER = (3, 8)
N_FACTORS = 20
TOP_K = 5
TEST_FRACTION = 0.2
RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Data loading (from S3 — this script runs inside a SageMaker Training Job,
# which has no VPC access to RDS, so it reads the CSV snapshots that the
# `export_orders_to_s3` Airflow DAG produces instead of querying RDS directly)
# ---------------------------------------------------------------------------

def _read_csv_from_s3(key):
    s3_client = boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "eu-central-1"))
    obj = s3_client.get_object(Bucket=DATASET_BUCKET, Key=key)
    return pd.read_csv(StringIO(obj["Body"].read().decode("utf-8")))


def load_cocktails_with_categories():
    """Returns list of (cocktail_id, categories: list[str])."""
    df = _read_csv_from_s3(COCKTAILS_CATEGORIES_KEY)

    def parse_categories(raw):
        if pd.isna(raw):
            return []
        # Postgres TEXT[] comes back through pandas/CSV as a string like "{Sour,Classic}"
        return [c.strip() for c in str(raw).strip("{}").split(",") if c.strip()]

    return [(row["id"], parse_categories(row["categories"])) for _, row in df.iterrows()]


def load_real_orders():
    """Returns list of (user_id, cocktail_id) from real guest orders."""
    df = _read_csv_from_s3(ORDERS_KEY)
    return list(zip(df["user_id"], df["cocktail_id"]))


def synthesize_orders(cocktails_with_categories, n_users=N_SYNTHETIC_USERS):
    """
    Bootstraps plausible implicit-feedback orders for cold-start CF training.

    Real order history is expected to be sparse for a freshly deployed bar
    (this is a home project, not a venue with thousands of guests yet), so
    we simulate synthetic "guests" who each prefer 1-2 cocktail categories
    and order accordingly. This lets us exercise the full CF pipeline
    (train/test split, matrix factorization, evaluation) end-to-end now,
    and gets naturally replaced/diluted by real orders as the bar is used.
    """
    random.seed(RANDOM_SEED)

    by_category = defaultdict(list)
    for cocktail_id, categories in cocktails_with_categories:
        for cat in categories:
            by_category[cat].append(cocktail_id)

    categories = [c for c in by_category if len(by_category[c]) >= 3]
    if not categories:
        raise RuntimeError("No categories with enough cocktails to synthesize orders from")

    synthetic_orders = []
    for synthetic_user_id in range(-1, -(n_users + 1), -1):
        # negative IDs so they never collide with real Telegram user_ids
        preferred = random.sample(categories, k=min(2, len(categories)))
        pool = list({c for cat in preferred for c in by_category[cat]})
        n_orders = random.randint(*ORDERS_PER_SYNTHETIC_USER)
        chosen = random.choices(pool, k=min(n_orders, len(pool)))
        for cocktail_id in chosen:
            synthetic_orders.append((synthetic_user_id, cocktail_id))

    return synthetic_orders


def build_interaction_data():
    """
    Returns (interactions, used_synthetic: bool) where interactions is a
    list of (user_id, cocktail_id) implicit-feedback pairs.
    """
    real_orders = load_real_orders()
    if len(real_orders) >= MIN_REAL_ORDERS:
        print(f"Using {len(real_orders)} real orders (no synthetic bootstrap needed)")
        return real_orders, False

    print(f"Only {len(real_orders)} real orders found (< {MIN_REAL_ORDERS}), "
          f"bootstrapping with synthetic implicit feedback")
    cocktails = load_cocktails_with_categories()
    synthetic = synthesize_orders(cocktails)
    return real_orders + synthetic, True


# ---------------------------------------------------------------------------
# Matrix building + train/test split
# ---------------------------------------------------------------------------

def build_matrix(interactions):
    users = sorted({u for u, _ in interactions})
    items = sorted({i for _, i in interactions})
    user_index = {u: idx for idx, u in enumerate(users)}
    item_index = {i: idx for idx, i in enumerate(items)}

    rows, cols, data = [], [], []
    for u, i in interactions:
        rows.append(user_index[u])
        cols.append(item_index[i])
        data.append(1.0)

    matrix = csr_matrix((data, (rows, cols)), shape=(len(users), len(items)))
    return matrix, users, items, user_index, item_index


def train_test_split_interactions(interactions):
    """Leave-one-out style split: hold out ~TEST_FRACTION of each user's orders."""
    random.seed(RANDOM_SEED)
    by_user = defaultdict(list)
    for u, i in interactions:
        by_user[u].append(i)

    train, test = [], []
    for u, items in by_user.items():
        items = items[:]
        random.shuffle(items)
        n_test = max(1, int(len(items) * TEST_FRACTION)) if len(items) > 1 else 0
        test_items = items[:n_test]
        train_items = items[n_test:] if n_test else items
        for i in train_items:
            train.append((u, i))
        for i in test_items:
            test.append((u, i))

    return train, test


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def train_popularity(train_matrix, items):
    popularity = np.asarray(train_matrix.sum(axis=0)).flatten()
    ranked_items = [items[idx] for idx in np.argsort(-popularity)]
    return {"type": "popularity", "ranked_items": ranked_items}


def recommend_popularity(model, user_idx, k):
    return model["ranked_items"][:k]


def train_als(train_matrix):
    from implicit.als import AlternatingLeastSquares

    model = AlternatingLeastSquares(factors=N_FACTORS, regularization=0.1, iterations=15, random_state=RANDOM_SEED)
    model.fit(train_matrix)
    return {"type": "als", "model": model}


def recommend_als(model, train_matrix, user_idx, k):
    item_ids, _ = model["model"].recommend(
        user_idx, train_matrix[user_idx], N=k, filter_already_liked_items=True
    )
    return list(item_ids)


def train_svd(train_matrix):
    k = min(N_FACTORS, min(train_matrix.shape) - 1)
    k = max(k, 2)
    u, s, vt = svds(train_matrix.astype(float), k=k)
    return {"type": "svd", "u": u, "s": s, "vt": vt}


def recommend_svd(model, user_idx, k):
    scores = model["u"][user_idx] @ np.diag(model["s"]) @ model["vt"]
    return list(np.argsort(-scores)[:k])


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def precision_at_k(recommend_fn, test_by_user, k=TOP_K):
    hits, total = 0, 0
    for user_idx, held_out_item_indices in test_by_user.items():
        if not held_out_item_indices:
            continue
        recs = set(recommend_fn(user_idx, k))
        hits += len(recs & set(held_out_item_indices))
        total += min(k, len(held_out_item_indices))
    return hits / total if total else 0.0


# ---------------------------------------------------------------------------
# MLflow logging + champion-challenger
# ---------------------------------------------------------------------------

def log_and_maybe_promote(run_name, params, metric_value, model_obj, client):
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(params)
        mlflow.log_metric("precision_at_5", metric_value)

        local_path = f"/tmp/{run_name}.joblib"
        joblib.dump(model_obj, local_path)
        mlflow.log_artifact(local_path, artifact_path="model")

        run_id = mlflow.active_run().info.run_id

    return run_id, metric_value


def register_if_champion(client, run_id, metric_value, model_name=MODEL_REGISTRY_NAME):
    model_uri = f"runs:/{run_id}/model"

    try:
        current_champion = client.get_model_version_by_alias(model_name, "champion")
        current_metric = float(
            client.get_run(current_champion.run_id).data.metrics.get("precision_at_5", -1)
        )
    except Exception:
        current_champion = None
        current_metric = -1

    if metric_value > current_metric:
        new_version = mlflow.register_model(model_uri, model_name)
        client.set_registered_model_alias(model_name, "champion", new_version.version)
        print(f"New champion: version {new_version.version} "
              f"(precision@5={metric_value:.4f} > previous {current_metric:.4f})")
        return True

    print(f"Challenger did not beat champion "
          f"(precision@5={metric_value:.4f} <= {current_metric:.4f}), keeping current champion")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    client = mlflow.MlflowClient()

    interactions, used_synthetic = build_interaction_data()
    train_interactions, test_interactions = train_test_split_interactions(interactions)

    train_matrix, users, items, user_index, item_index = build_matrix(train_interactions)

    test_by_user = defaultdict(list)
    for u, i in test_interactions:
        if u in user_index and i in item_index:
            test_by_user[user_index[u]].append(item_index[i])

    base_params = {
        "n_users": len(users),
        "n_items": len(items),
        "n_train_interactions": len(train_interactions),
        "n_test_interactions": len(test_interactions),
        "used_synthetic_bootstrap": used_synthetic,
    }

    results = []

    # --- Popularity baseline ---
    pop_model = train_popularity(train_matrix, items)
    pop_metric = precision_at_k(lambda uidx, k: recommend_popularity(pop_model, uidx, k), test_by_user)
    run_id, metric = log_and_maybe_promote(
        "popularity_baseline", {**base_params, "algorithm": "popularity"}, pop_metric, pop_model, client
    )
    results.append((run_id, metric))

    # --- ALS ---
    try:
        als_model = train_als(train_matrix)
        als_metric = precision_at_k(
            lambda uidx, k: recommend_als(als_model, train_matrix, uidx, k), test_by_user
        )
        run_id, metric = log_and_maybe_promote(
            "als", {**base_params, "algorithm": "als", "factors": N_FACTORS}, als_metric, als_model, client
        )
        results.append((run_id, metric))
    except ImportError:
        print("`implicit` package not installed, skipping ALS")

    # --- SVD ---
    svd_model = train_svd(train_matrix)
    svd_metric = precision_at_k(lambda uidx, k: recommend_svd(svd_model, uidx, k), test_by_user)
    run_id, metric = log_and_maybe_promote(
        "svd", {**base_params, "algorithm": "svd", "factors": N_FACTORS}, svd_metric, svd_model, client
    )
    results.append((run_id, metric))

    # --- Champion selection: best of this batch vs current registry champion ---
    best_run_id, best_metric = max(results, key=lambda r: r[1])
    print(f"\nBest this run: {best_run_id} (precision@5={best_metric:.4f})")
    register_if_champion(client, best_run_id, best_metric)


if __name__ == "__main__":
    main()