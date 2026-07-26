from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
import psycopg2
import pandas as pd
import boto3
from io import StringIO

def export_orders_to_s3():
    # Підключення до PostgreSQL (RDS)
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "cocktail_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer")
    )
    
    # Читаємо дані
    df = pd.read_sql("SELECT id, name, ingredients, garnish, instructions FROM cocktails", conn)
    conn.close()
    
    # Конвертуємо в CSV
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)

    # Завантажуємо в S3 (креденшли беруться з IAM-ролі EC2, нічого не хардкодимо)
    bucket = os.getenv("DATASET_BUCKET", "cocktail-mlops-data-oles")
    s3_client = boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "eu-central-1"))

    s3_client.put_object(
        Bucket=bucket,
        Key=f"order-history/cocktails_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        Body=csv_buffer.getvalue()
    )

    print(f"Exported {len(df)} cocktails to s3://{bucket}/order-history/")

with DAG(
    dag_id="export_orders_to_s3",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False
) as dag:
    
    export_task = PythonOperator(
        task_id="export_cocktails",
        python_callable=export_orders_to_s3
    )