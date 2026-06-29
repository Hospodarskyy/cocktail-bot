from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from .db import get_connection

model = SentenceTransformer("all-MiniLM-L6-v2")

def build_cocktail_text(name, ingredients, garnish, instructions):
    return f"{name}. Ingredients: {ingredients}. Garnish: {garnish}. Preparation: {instructions}"

def generate_embeddings():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, name, ingredients, garnish, instructions FROM cocktails WHERE embedding IS NULL")
    cocktails = cur.fetchall()

    print(f"Generating embeddings for {len(cocktails)} cocktails...")

    for cocktail_id, name, ingredients, garnish, instructions in tqdm(cocktails, desc="Generating embeddings"):
        text = build_cocktail_text(name, ingredients or "", garnish or "", instructions or "")
        embedding = model.encode(text).tolist()

        cur.execute(
            "UPDATE cocktails SET embedding = %s WHERE id = %s",
            (embedding, cocktail_id)
        )

    conn.commit()
    cur.close()
    conn.close()
    print("Done")

if __name__ == "__main__":
    generate_embeddings()
