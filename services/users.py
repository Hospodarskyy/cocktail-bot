from sentence_transformers import SentenceTransformer
from .db import get_connection

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_preferences(text: str):
    return model.encode(text).tolist()

def onboard_user(user_id: int, name: str, preferences: str):
    embedding = embed_preferences(preferences)

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

def get_user_profile(user_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT preferences_text, embedding FROM users WHERE id = %s", (user_id,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result is None:
        return None
    return {"preferences_text": result[0], "embedding": result[1]}

def get_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT name, preferences_text FROM users WHERE id = %s", (user_id,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result is None:
        return None
    return {"name": result[0], "preferences": result[1]}

def clear_preferences(user_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE users SET preferences_text = NULL, embedding = NULL WHERE id = %s", (user_id,))
    found = cur.rowcount > 0

    conn.commit()
    cur.close()
    conn.close()

    if not found:
        raise ValueError("User not found.")

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