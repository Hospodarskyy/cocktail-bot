"""
Trains exactly ONE collaborative-filtering model and logs it to MLflow.

This is the entry point for each of the parallel SageMaker Training Job
tasks (train_svd / train_als / train_bpr / train_tuned) in the Airflow
DAG. It does NOT decide the champion — that comparison happens once, in
select_champion.py, after all parallel branches have finished.

Run inside a SageMaker Training Job (hyperparameters become CLI args
automatically), or manually:
    export MLFLOW_TRACKING_URI=...
    export DATASET_BUCKET=cocktail-mlops-data-oles
    python -m training.train_single_model --model als --data-key processed/<batch_id>/data.joblib --batch-id <batch_id>
"""

import argparse

try:
    from training import common  # local dev / tests: training/ is an importable package
except ImportError:
    import common  # inside SageMaker: source_dir=training/ flattens it, common.py is a sibling file


def _train_and_evaluate(model_name, train_matrix, test_by_user):
    """Returns (model_obj, params, metrics_dict) for a given model name."""
    if model_name == "popularity":
        model = common.train_popularity(train_matrix)
        metrics = common.evaluate_all_k(lambda u, k: common.recommend_popularity(model, u, k), test_by_user)
        params = {"algorithm": "popularity"}
        return model, params, metrics

    if model_name == "svd":
        model = common.train_svd(train_matrix)
        metrics = common.evaluate_all_k(lambda u, k: common.recommend_svd(model, u, k), test_by_user)
        params = {"algorithm": "svd", "factors": common.N_FACTORS}
        return model, params, metrics

    if model_name == "als":
        model = common.train_als(train_matrix)
        metrics = common.evaluate_all_k(
            lambda u, k: common.recommend_als(model, train_matrix, u, k), test_by_user
        )
        params = {"algorithm": "als", "factors": common.N_FACTORS}
        return model, params, metrics

    if model_name == "bpr":
        model = common.train_bpr(train_matrix)
        metrics = common.evaluate_all_k(
            lambda u, k: common.recommend_bpr(model, train_matrix, u, k), test_by_user
        )
        params = {"algorithm": "bpr", "factors": common.N_FACTORS}
        return model, params, metrics

    if model_name == "tuned":
        # Grid search across ALS and BPR together, same as the original
        # single-script pipeline — kept as one combined task since the two
        # loops share the same grid and are cheap compared to a full job.
        best = None  # (algo, factors, reg, score, model_obj)
        for factors in common.TUNING_GRID["factors"]:
            for reg in common.TUNING_GRID["regularization"]:
                als_candidate = common.train_als(train_matrix, n_factors=factors, regularization=reg)
                score = common.precision_at_k(
                    lambda u, k: common.recommend_als(als_candidate, train_matrix, u, k), test_by_user
                )
                if best is None or score > best[3]:
                    best = ("als", factors, reg, score, als_candidate)

                bpr_candidate = common.train_bpr(train_matrix, n_factors=factors, regularization=reg)
                score = common.precision_at_k(
                    lambda u, k: common.recommend_bpr(bpr_candidate, train_matrix, u, k), test_by_user
                )
                if best is None or score > best[3]:
                    best = ("bpr", factors, reg, score, bpr_candidate)

        algo, factors, reg, _, model = best
        recommend_fn = (
            (lambda u, k: common.recommend_als(model, train_matrix, u, k)) if algo == "als"
            else (lambda u, k: common.recommend_bpr(model, train_matrix, u, k))
        )
        metrics = common.evaluate_all_k(recommend_fn, test_by_user)
        params = {"algorithm": algo, "factors": factors, "regularization": reg, "tuned": True}
        return model, params, metrics

    raise ValueError(f"Unknown model: {model_name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=["popularity", "svd", "als", "bpr", "tuned"])
    parser.add_argument("--data-key", required=True, help="S3 key of the preprocessed data joblib")
    parser.add_argument("--batch-id", required=True, help="Airflow DAG run_id, tagged on the MLflow run")
    args = parser.parse_args()

    common.set_mlflow_tracking()

    data = common.download_joblib_from_s3(common.DATASET_BUCKET, args.data_key)
    train_matrix = data["train_matrix"]
    test_by_user = data["test_by_user"]
    users = data["users"]
    items = data["items"]
    base_params = data["base_params"]

    model_obj, params, metrics = _train_and_evaluate(args.model, train_matrix, test_by_user)

    run_id, precision_at_5 = common.log_model_run(
        run_name=args.model,
        model_obj=model_obj,
        params={**base_params, **params},
        metrics_dict=metrics,
        items=items,
        users=users,
        train_matrix=train_matrix,
        batch_id=args.batch_id,
    )

    print(f"Logged run {run_id} for model={args.model} (precision_at_5={precision_at_5:.4f})")


if __name__ == "__main__":
    main()