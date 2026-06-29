import psycopg2
import os

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=5432,
        dbname="cocktail_db",
        user="cocktail",
        password="cocktail"
    )

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cocktails (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            ingredients TEXT,
            garnish TEXT,
            instructions TEXT,
            flavor_description TEXT,
            embedding vector(384)
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully")

if __name__ == "__main__":
    init_db()
