from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import psycopg2
import pandas as pd
import boto3
from io import StringIO

def export_cocktails_to_minio():
    # Підключення до PostgreSQL
    conn = psycopg2.connect(
        host="postgres",
        port=5432,
        dbname="cocktail_db",
        user="cocktail",
        password="cocktail"
    )
    
    # Читаємо дані
    df = pd.read_sql("SELECT id, name, ingredients, garnish, instructions FROM cocktails", conn)
    conn.close()
    
    # Конвертуємо в CSV
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    
    # Завантажуємо в MinIO
    s3_client = boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin"
    )
    
    # Створюємо bucket якщо не існує
    try:
        s3_client.create_bucket(Bucket="training-data")
    except Exception:
        pass
    
    # Завантажуємо файл
    s3_client.put_object(
        Bucket="training-data",
        Key=f"cocktails_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        Body=csv_buffer.getvalue()
    )
    
    print(f"Exported {len(df)} cocktails to MinIO")

with DAG(
    dag_id="export_cocktails_to_minio",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False
) as dag:
    
    export_task = PythonOperator(
        task_id="export_cocktails",
        python_callable=export_cocktails_to_minio
    )