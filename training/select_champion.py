import argparse

import mlflow

try:
    from training import common
except ImportError:
    import common

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True)
    args = parser.parse_args()

    client = common.set_mlflow_tracking()

    experiment = client.get_experiment_by_name(common.MLFLOW_EXPERIMENT)
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string=f"tags.batch_id = '{args.batch_id}'",
    )

    if not runs:
        raise RuntimeError(
            f"No MLflow runs found with batch_id={args.batch_id} — did the training tasks run first?"
        )

    best_run = max(runs, key=lambda r: r.data.metrics.get("precision_at_5", -1))
    best_metric = best_run.data.metrics["precision_at_5"]

    print(f"Best of batch {args.batch_id}: run {best_run.info.run_id} "
          f"({best_run.data.params.get('algorithm')}, precision_at_5={best_metric:.4f})")

    common.register_if_champion(client, best_run.info.run_id, best_metric)


if __name__ == "__main__":
    main()