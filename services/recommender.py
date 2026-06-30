from .db import get_connection
from .users import get_user_embedding

def recommend(user_id: int, top_k: int = 5):
    embedding = get_user_embedding(user_id)
    
    if embedding is None:
        raise ValueError("User not found. Please complete onboarding first.")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, ingredients, garnish
        FROM cocktails
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (embedding, top_k))

    results = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "ingredients": row[2],
            "garnish": row[3]
        }
        for row in results
    ]

def cocktail_summary():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM cocktails")
    count = cur.fetchone()[0]

    cur.execute("""
        SELECT category, COUNT(*)
        FROM cocktails
        GROUP BY category
        ORDER BY COUNT(*) DESC
    """)
    categories = cur.fetchall()

    cur.close()
    conn.close()

    return {
        "count": count,
        "categories": [{"category": row[0], "count": row[1]} for row in categories]
    }

if __name__ == "__main__":
    results = recommend(123, top_k=5)
    for r in results:
        print(f"{r['name']} — {r['ingredients'][:80]}")
