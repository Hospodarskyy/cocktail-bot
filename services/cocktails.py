from .db import get_connection
from .flavor import describe_flavor
from .required_ingredients import extract_required_ingredients
from .embedder import build_cocktail_text, model as embedding_model
from .cocktail_category import categorize_cocktail

def create_cocktail(name: str, ingredients: str, garnish: str | None, instructions: str) -> int:
    flavor_description = describe_flavor(name, ingredients, garnish or "", instructions)
    required = extract_required_ingredients(name, ingredients)
    categories = categorize_cocktail(required)
    text = build_cocktail_text(name, ingredients, garnish or "", instructions, flavor_description)
    embedding = embedding_model.encode(text).tolist()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cocktails (name, categories, ingredients, garnish, instructions, flavor_description, required_ingredients, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (name, categories, ingredients, garnish, instructions, flavor_description, required, embedding))
    cocktail_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()
    return cocktail_id
