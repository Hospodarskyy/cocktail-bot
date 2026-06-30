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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            name TEXT,
            preferences_text TEXT,
            embedding vector(384)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            cocktail_id INTEGER REFERENCES cocktails(id),
            preferences TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            cocktail_id INTEGER REFERENCES cocktails(id),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully")

if __name__ == "__main__":
    init_db()