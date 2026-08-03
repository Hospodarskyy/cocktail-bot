import os
from datetime import datetime
from io import StringIO

from fastapi import requests

import boto3
import pandas as pd
import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator

DATASET_BUCKET = os.getenv("DATASET_BUCKET", "cocktail-mlops-data-oles")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
SAGEMAKER_TRAINING_REGION = "us-east-1"  # eu-central-1 has zero ml training quota on this account
GITHUB_BRANCH = "upgraded_tg_bot_"
GITHUB_REPO = "https://github.com/Hospodarskyy/cocktail-bot"



def export_data_to_s3(**context):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "cocktail_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
    )
    orders_df = pd.read_sql(
        "SELECT user_id, cocktail_id, created_at FROM orders WHERE cocktail_id IS NOT NULL", conn
    )
    cocktails_df = pd.read_sql(
        "SELECT id, categories FROM cocktails WHERE categories IS NOT NULL", conn
    )
    conn.close()

    s3_client = boto3.client("s3", region_name=AWS_REGION)

    def upload(df, key):
        buf = StringIO()
        df.to_csv(buf, index=False)
        s3_client.put_object(Bucket=DATASET_BUCKET, Key=key, Body=buf.getvalue())

    upload(orders_df, "order-history/orders.csv")
    upload(cocktails_df, "order-history/cocktails_categories.csv")

    print(f"Exported {len(orders_df)} orders and {len(cocktails_df)} cocktail categories "
          f"to s3://{DATASET_BUCKET}/order-history/")



def _run_training_job(entry_point, hyperparameters):
    import shutil
    import subprocess
    import tempfile

    repo_path = tempfile.mkdtemp(prefix="train-code-")
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", "--branch", GITHUB_BRANCH, GITHUB_REPO, repo_path],
            check=True,
        )

        import boto3 as _boto3
        import sagemaker
        from sagemaker.pytorch.estimator import PyTorch

        boto_session = _boto3.Session(region_name=SAGEMAKER_TRAINING_REGION)
        sagemaker_session = sagemaker.Session(boto_session=boto_session)

        estimator = PyTorch(
            entry_point=entry_point,
            source_dir=f"{repo_path}/training",
            role=os.getenv("SAGEMAKER_ROLE_ARN"),
            instance_type="ml.m5.large",
            instance_count=1,
            framework_version="2.1.0",
            py_version="py310",
            sagemaker_session=sagemaker_session,
            hyperparameters=hyperparameters,
            environment={
                "MLFLOW_TRACKING_URI": os.getenv("MLFLOW_TRACKING_URI"),
                "DATASET_BUCKET": DATASET_BUCKET,
                "AWS_DEFAULT_REGION": AWS_REGION,
            },
        )
        estimator.fit()
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)



def preprocess_data(**context):
    batch_id = context["run_id"]
    _run_training_job(
        entry_point="preprocess.py",
        hyperparameters={"batch-id": batch_id},
    )



def _make_train_task(model_name):
    def _train(**context):
        batch_id = context["run_id"]
        data_key = f"processed/{batch_id}/data.joblib"
        _run_training_job(
            entry_point="train_single_model.py",
            hyperparameters={"model": model_name, "data-key": data_key, "batch-id": batch_id},
        )
    return _train



def select_and_register_champion(**context):
    batch_id = context["run_id"]
    _run_training_job(
        entry_point="select_champion.py",
        hyperparameters={"batch-id": batch_id},
    )

    try:
        response = requests.post("http://api:8000/admin/reload-model", timeout=30)
        response.raise_for_status()
        print(f"API reloaded champion model: {response.json()}")
    except Exception as e:
        print(f"WARNING: failed to notify API to reload champion model: {e}")


with DAG(
    dag_id="cocktail_training_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
) as dag:

    export_task = PythonOperator(
        task_id="export_data_to_s3",
        python_callable=export_data_to_s3,
    )

    preprocess_task = PythonOperator(
        task_id="preprocess_data",
        python_callable=preprocess_data,
    )

    train_tasks = [
        PythonOperator(
            task_id=f"train_{model_name}",
            python_callable=_make_train_task(model_name),
        )
        for model_name in ["svd", "als", "bpr", "tuned"]
    ]

    champion_task = PythonOperator(
        task_id="select_and_register_champion",
        python_callable=select_and_register_champion,
    )

    export_task >> preprocess_task >> train_tasks >> champion_task