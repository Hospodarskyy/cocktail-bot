import os
from openai import OpenAI
from tqdm import tqdm
from .db import get_connection

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

SYSTEM_PROMPT = (
    "You are an expert bartender and flavor analyst. Given a cocktail's name and recipe, write a "
    "single concise paragraph (2-3 sentences) describing its flavor and style: spirit character, "
    "sweetness/bitterness/sourness, strength, body (light and refreshing vs rich and warming), and "
    "the mood or occasion it suits. Use plain, evocative flavor language aimed at matching guest "
    "taste preferences in a recommendation engine. Do not just restate the ingredient list."
)

def describe_flavor(name, ingredients, garnish, instructions):
    recipe = f"{name}. Ingredients: {ingredients}. Garnish: {garnish}. Preparation: {instructions}"
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": recipe}
        ]
    )
    return response.choices[0].message.content.strip()

def generate_flavor_descriptions():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, name, ingredients, garnish, instructions FROM cocktails WHERE flavor_description IS NULL")
    cocktails = cur.fetchall()

    if not cocktails:
        cur.close()
        conn.close()
        return

    print(f"Generating flavor descriptions for {len(cocktails)} cocktails...")

    for cocktail_id, name, ingredients, garnish, instructions in tqdm(cocktails, desc="Generating flavor descriptions"):
        description = describe_flavor(name, ingredients or "", garnish or "", instructions or "")
        cur.execute(
            "UPDATE cocktails SET flavor_description = %s WHERE id = %s",
            (description, cocktail_id)
        )
        conn.commit()

    cur.close()
    conn.close()
    print("Done")

if __name__ == "__main__":
    generate_flavor_descriptions()
