from sentence_transformers import SentenceTransformer
from .db import get_connection

model = SentenceTransformer("all-MiniLM-L6-v2")

def recommend(user_preferences: str, top_k: int = 5):
    embedding = model.encode(user_preferences).tolist()

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

if __name__ == "__main__":
    results = recommend("sweet citrusy refreshing drink", top_k=5)
    for r in results:
        print(f"{r['name']} — {r['ingredients'][:80]}")
