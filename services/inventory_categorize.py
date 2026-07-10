import os
from openai import OpenAI, pydantic_function_tool
from tqdm import tqdm
from .db import get_connection
from .models import InventoryCategory, INVENTORY_CATEGORIES

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

CATEGORIES = INVENTORY_CATEGORIES

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

TOOL_NAME = "record_category"
TOOLS = [pydantic_function_tool(
    InventoryCategory,
    name=TOOL_NAME,
    description="Record the bar-stock category for this ingredient."
)]

SYSTEM_PROMPT = (
    "You categorize a bar ingredient name into exactly one of these fixed categories: "
    + ", ".join(CATEGORIES) + ". Base Spirits = gin, vodka, rum, whiskey, tequila, etc. Liqueurs = flavored "
    "spirits like triple sec, amaretto. Bitters = aromatic/cocktail bitters. Juices = fruit juices. "
    "Syrups & Sweeteners = simple syrup, grenadine, honey, sugar. Garnishes = fruit, herbs, olives, twists. "
    "Mixers = soda, tonic, ginger beer. Other = anything that doesn't clearly fit."
)

def categorize_ingredient(name: str) -> str:
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": name}
        ],
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        parallel_tool_calls=False
    )
    result = InventoryCategory.model_validate_json(response.choices[0].message.tool_calls[0].function.arguments)
    return result.category

def generate_inventory_categories():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, ingredient_name FROM inventory WHERE category IS NULL")
    rows = cur.fetchall()

    if not rows:
        cur.close()
        conn.close()
        return

    print(f"Categorizing {len(rows)} inventory ingredients...")
    for ingredient_id, name in tqdm(rows, desc="Categorizing inventory"):
        category = categorize_ingredient(name)
        cur.execute("UPDATE inventory SET category = %s WHERE id = %s", (category, ingredient_id))
        conn.commit()

    cur.close()
    conn.close()
    print("Done categorizing inventory.")
