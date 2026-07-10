from .db import get_connection
from .users import get_user_profile, embed_preferences
from .recommend_llm import select_cocktails
from .inventory import available_ingredient_terms, missing_ingredients

MIN_CANDIDATE_POOL = 20
CANDIDATE_POOL_MULTIPLIER = 4

def _to_result(c, vibe=None):
    return {"id": c["id"], "name": c["name"], "ingredients": c["ingredients"], "garnish": c["garnish"], "vibe": vibe}

def _infeasible_cocktail_ids():
    available_terms = available_ingredient_terms()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, required_ingredients FROM cocktails WHERE required_ingredients IS NOT NULL")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        cocktail_id for cocktail_id, required in rows
        if missing_ingredients(required, available_terms)
    ]

def _recommend_with_profile(preferences_text: str, embedding, top_k: int, exclude_ids: list[int] | None):
    combined_exclude = list(exclude_ids or []) + _infeasible_cocktail_ids()

    pool_size = max(MIN_CANDIDATE_POOL, top_k * CANDIDATE_POOL_MULTIPLIER)

    conn = get_connection()
    cur = conn.cursor()

    if combined_exclude:
        cur.execute("""
            SELECT id, name, ingredients, garnish, flavor_description
            FROM cocktails
            WHERE NOT (id = ANY(%s))
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (combined_exclude, embedding, pool_size))
    else:
        cur.execute("""
            SELECT id, name, ingredients, garnish, flavor_description
            FROM cocktails
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (embedding, pool_size))

    candidates = [
        {"id": row[0], "name": row[1], "ingredients": row[2], "garnish": row[3], "flavor_description": row[4]}
        for row in cur.fetchall()
    ]

    cur.close()
    conn.close()

    try:
        chosen = select_cocktails(preferences_text, candidates, top_k)
        by_id = {c["id"]: c for c in candidates}
        ranked = [(by_id[item.id], item.vibe) for item in chosen if item.id in by_id][:top_k]
        if ranked:
            return [_to_result(c, vibe) for c, vibe in ranked]
    except Exception as e:
        print(f"LLM reranking failed, falling back to cosine top-{top_k}: {e}")

    return [_to_result(c) for c in candidates[:top_k]]

def recommend(user_id: int, top_k: int = 5, exclude_ids: list[int] | None = None):
    profile = get_user_profile(user_id)

    if profile is None or profile["preferences_text"] is None:
        raise ValueError("User not found. Please complete onboarding first.")

    return _recommend_with_profile(profile["preferences_text"], profile["embedding"], top_k, exclude_ids)

def recommend_from_text(preferences_text: str, top_k: int = 5, exclude_ids: list[int] | None = None):
    embedding = embed_preferences(preferences_text)
    return _recommend_with_profile(preferences_text, embedding, top_k, exclude_ids)

def cocktail_summary():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM cocktails")
    count = cur.fetchone()[0]

    cur.execute("""
        SELECT category, COUNT(*)
        FROM (SELECT unnest(categories) AS category FROM cocktails WHERE categories IS NOT NULL) sub
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

def cocktails_in_category(category: str, limit: int = 200):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM cocktails WHERE %s = ANY(categories) ORDER BY name LIMIT %s", (category, limit))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [{"id": row[0], "name": row[1]} for row in rows]

if __name__ == "__main__":
    results = recommend(123, top_k=5)
    for r in results:
        print(f"{r['name']} — {r['ingredients'][:80]}")
