import os
from openai import OpenAI, pydantic_function_tool
from .models import OrderMessage

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

TOOL_NAME = "record_order_message"
TOOLS = [pydantic_function_tool(
    OrderMessage,
    name=TOOL_NAME,
    description="Record a bartender-ready version of this cocktail order: unit-normalized ingredients, clear steps, and a short story."
)]

SYSTEM_PROMPT = (
    "You prepare a cocktail order for the bartender fulfilling it. Given the raw recipe (which uses ounces and "
    "other imperial units), rewrite the ingredient list with liquid measurements converted to milliliters so it "
    "matches how the bar's stock is tracked, keep non-liquid items as-is, restate the instructions as clear "
    "numbered steps, and add a short story about the cocktail's history or legend. If the guest specified "
    "preferences for this particular order (e.g. 'less sweet', 'not too bitter', 'stronger', 'no citrus', an "
    "allergy), adjust the ingredient amounts, substitutions, or instructions to honor them while keeping it "
    "recognizably the same cocktail — favor small quantity tweaks over swapping core spirits — and summarize "
    "the change in `adjustments`. If a substitution is needed and a list of ingredients currently in stock at "
    "the bar is given, you MUST pick the substitute from that stock list if a reasonable one exists there — "
    "never suggest something that isn't in stock when an in-stock alternative would work. Only reach for "
    "something not in the stock list if nothing on it is a sensible substitute, and say so plainly in "
    "`adjustments` (e.g. 'not in stock — needs sourcing') so the bartender isn't caught by surprise. If there "
    "are no preferences, leave `adjustments` null and don't change anything about the recipe beyond the unit "
    "conversion."
)

def generate_order_message(name, ingredients, garnish, instructions, preferences=None, available_ingredients=None) -> OrderMessage:
    user_content = (
        f"{name}\n"
        f"Ingredients: {ingredients}\n"
        f"Garnish: {garnish or 'none'}\n"
        f"Instructions: {instructions or 'none'}"
    )
    if preferences:
        user_content += f"\nGuest preferences for this order: {preferences}"
        if available_ingredients:
            user_content += f"\nIngredients currently in stock at the bar: {', '.join(available_ingredients)}"
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        parallel_tool_calls=False
    )
    return OrderMessage.model_validate_json(response.choices[0].message.tool_calls[0].function.arguments)
