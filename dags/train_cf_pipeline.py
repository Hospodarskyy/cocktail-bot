from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import subprocess
import os


def run_cf_training():
    # Свіжий git clone - гарантує, що тренується точно той код, що в GitHub,
    # незалежно від стану диска на цьому EC2
    repo_path = "/tmp/train-code"
    subprocess.run(["rm", "-rf", repo_path], check=True)
    subprocess.run([
        "git", "clone", "--depth=1", "--branch", "upgraded_tg_bot_",
        "https://github.com/Hospodarskyy/cocktail-bot", repo_path
    ], check=True)

    from sagemaker.sklearn.estimator import SKLearn

    estimator = SKLearn(
        entry_point="train_cf.py",
        source_dir=f"{repo_path}/training",
        role=os.getenv("SAGEMAKER_ROLE_ARN"),
        instance_type="ml.m5.large",
        instance_count=1,
        framework_version="1.2-1",
        py_version="py3",
        environment={
            "MLFLOW_TRACKING_URI": os.getenv("MLFLOW_TRACKING_URI"),
            "DATASET_BUCKET": os.getenv("DATASET_BUCKET", "cocktail-mlops-data-oles"),
            "AWS_DEFAULT_REGION": os.getenv("AWS_DEFAULT_REGION", "eu-central-1"),
        },
    )

    estimator.fit()


with DAG(
    dag_id="train_cf_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False
) as dag:

    train_task = PythonOperator(
        task_id="run_cf_training",
        python_callable=run_cf_training
    )