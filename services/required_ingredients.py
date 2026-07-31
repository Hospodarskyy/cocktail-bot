import os
from openai import OpenAI, pydantic_function_tool
from tqdm import tqdm
from .db import get_connection
from .models import RequiredIngredients

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

TOOL_NAME = "record_required_ingredients"
TOOLS = [pydantic_function_tool(
    RequiredIngredients,
    name=TOOL_NAME,
    description="Record the generalized list of ingredients this cocktail requires, for matching against a bar's stock list."
)]

SYSTEM_PROMPT = (
    "You extract a generalized, matchable ingredient list from a cocktail recipe, for comparing against a bar's "
    "stock list. For each ingredient in the recipe, strip specific brand names and give the base category "
    "(e.g. 'No.3 London Dry Gin' -> 'gin', 'Tempus Fugit Creme de Violette' -> 'creme de violette', "
    "'Fresh lime juice' -> 'lime juice'). Exclude always-available basics that are never worth tracking as stock: "
    "ice, water."
)

def extract_required_ingredients(name, ingredients_text) -> list[str]:
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{name}. Ingredients: {ingredients_text}"}
        ],
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        parallel_tool_calls=False
    )
    result = RequiredIngredients.model_validate_json(response.choices[0].message.tool_calls[0].function.arguments)
    return result.ingredients

def generate_required_ingredients():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, name, ingredients FROM cocktails WHERE required_ingredients IS NULL")
    cocktails = cur.fetchall()

    if not cocktails:
        cur.close()
        conn.close()
        return

    print(f"Extracting required ingredients for {len(cocktails)} cocktails...")

    for cocktail_id, name, ingredients in tqdm(cocktails, desc="Extracting required ingredients"):
        required = extract_required_ingredients(name, ingredients or "")
        cur.execute(
            "UPDATE cocktails SET required_ingredients = %s WHERE id = %s",
            (required, cocktail_id)
        )
        conn.commit()

    cur.close()
    conn.close()
    print("Done")

if __name__ == "__main__":
    generate_required_ingredients()
