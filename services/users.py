from sentence_transformers import SentenceTransformer
from .db import get_connection

model = SentenceTransformer("all-MiniLM-L6-v2")

def onboard_user(user_id: int, name: str, preferences: str):
    embedding = model.encode(preferences).tolist()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (id, name, preferences_text, embedding)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            preferences_text = EXCLUDED.preferences_text,
            embedding = EXCLUDED.embedding
    """, (user_id, name, preferences, embedding))

    conn.commit()
    cur.close()
    conn.close()

def get_user_embedding(user_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT embedding FROM users WHERE id = %s", (user_id,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result is None:
        return None
    return result[0]

def list_recent_users(limit: int = 10):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, preferences_text
        FROM users
        ORDER BY id DESC
        LIMIT %s
    """, (limit,))

    results = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {"user_id": row[0], "name": row[1], "preferences": row[2]}
        for row in results
    ]