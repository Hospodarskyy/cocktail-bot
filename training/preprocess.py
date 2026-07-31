import argparse

try:
    from training import common
except ImportError:
    import common


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True, help="Airflow DAG run_id, used to namespace the S3 output key")
    args = parser.parse_args()

    interactions, used_synthetic = common.build_interaction_data()
    train_interactions, test_interactions = common.train_test_split_interactions(interactions)
    train_matrix, users, items, user_index, item_index = common.build_matrix(train_interactions)
    test_by_user = common.build_test_by_user(test_interactions, user_index, item_index)

    base_params = {
        "n_users": len(users),
        "n_items": len(items),
        "n_train_interactions": len(train_interactions),
        "n_test_interactions": len(test_interactions),
        "used_synthetic_bootstrap": used_synthetic,
    }

    package = {
        "train_matrix": train_matrix,
        "test_by_user": test_by_user,
        "users": users,
        "items": items,
        "base_params": base_params,
    }

    data_key = f"processed/{args.batch_id}/data.joblib"
    common.upload_joblib_to_s3(package, common.DATASET_BUCKET, data_key)

    print(f"Uploaded preprocessed data to s3://{common.DATASET_BUCKET}/{data_key}")
    print(f"DATA_KEY={data_key}")
    return data_key


if __name__ == "__main__":
    main()