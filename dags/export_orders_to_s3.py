from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
import psycopg2
import pandas as pd
import boto3
from io import StringIO


def _get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "cocktail_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer")
    )


def _upload_df_to_s3(df, bucket, key, s3_client):
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3_client.put_object(Bucket=bucket, Key=key, Body=csv_buffer.getvalue())


def export_orders_to_s3():
    conn = _get_connection()

    orders_df = pd.read_sql(
        "SELECT user_id, cocktail_id, created_at FROM orders WHERE cocktail_id IS NOT NULL", conn
    )
    cocktails_df = pd.read_sql(
        "SELECT id, categories FROM cocktails WHERE categories IS NOT NULL", conn
    )
    conn.close()

    bucket = os.getenv("DATASET_BUCKET", "cocktail-mlops-data-oles")
    s3_client = boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "eu-central-1"))

    # Fixed (non-timestamped) keys — training always wants the current snapshot,
    # not historical versions, so each run simply overwrites the previous export.
    _upload_df_to_s3(orders_df, bucket, "order-history/orders.csv", s3_client)
    _upload_df_to_s3(cocktails_df, bucket, "order-history/cocktails_categories.csv", s3_client)

    print(f"Exported {len(orders_df)} orders and {len(cocktails_df)} cocktail categories "
          f"to s3://{bucket}/order-history/")


with DAG(
    dag_id="export_orders_to_s3",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False
) as dag:

    export_task = PythonOperator(
        task_id="export_orders",
        python_callable=export_orders_to_s3
    )