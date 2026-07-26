import os
import boto3

DATASET_BUCKET = os.getenv("DATASET_BUCKET", "cocktail-mlops-data-oles")
DATASET_KEY = os.getenv("DATASET_KEY", "datasets/cocktail-dataset.csv")


def ensure_dataset_downloaded(local_path: str) -> str:
    """
    Downloads the cocktail dataset from S3 if it's not already present locally.
    Relies on the IAM role attached to the EC2/ECS task for credentials —
    no access keys are hardcoded or baked into the image.
    """
    if os.path.exists(local_path):
        print(f"Dataset already present at {local_path}, skipping download")
        return local_path

    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

    print(f"Downloading dataset from s3://{DATASET_BUCKET}/{DATASET_KEY} ...")
    s3_client = boto3.client("s3")
    s3_client.download_file(DATASET_BUCKET, DATASET_KEY, local_path)
    print(f"Dataset downloaded to {local_path}")

    return local_path