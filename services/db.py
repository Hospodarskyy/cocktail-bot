import psycopg2
import os

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "cocktail_db"),
        user=os.getenv("DB_USER", "cocktail"),
        password=os.getenv("DB_PASSWORD", "cocktail"),
        sslmode=os.getenv("DB_SSLMODE", "prefer")
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

    cur.execute("ALTER TABLE cocktails ADD COLUMN IF NOT EXISTS required_ingredients TEXT[];")
    cur.execute("ALTER TABLE cocktails ADD COLUMN IF NOT EXISTS categories TEXT[];")

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
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS ingredients_text TEXT;")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS instructions_text TEXT;")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS story_text TEXT;")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS adjustments_text TEXT;")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS ingredients_json TEXT;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            cocktail_id INTEGER REFERENCES cocktails(id),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            ingredient_name TEXT NOT NULL,
            quantity NUMERIC NOT NULL DEFAULT 0,
            unit TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS inventory_ingredient_name_key
        ON inventory (LOWER(ingredient_name));
    """)

    cur.execute("ALTER TABLE inventory ADD COLUMN IF NOT EXISTS category TEXT;")

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully")

if __name__ == "__main__":
    init_db()