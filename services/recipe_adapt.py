import os
from openai import OpenAI, pydantic_function_tool
from .models import AdaptedRecipe

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

TOOL_NAME = "record_adapted_recipe"
TOOLS = [pydantic_function_tool(
    AdaptedRecipe,
    name=TOOL_NAME,
    description="Record an adapted version of the recipe substituting for ingredients that are out of stock."
)]

SYSTEM_PROMPT = (
    "You are an expert bartender adapting a cocktail recipe because some ingredients are out of stock. Given the "
    "original recipe and which ingredients are missing, rewrite the ingredients list substituting each missing "
    "ingredient with the closest reasonable alternative (similar spirit category, sweetness, bitterness, or "
    "flavor role), adjusting quantities if the substitute is stronger/weaker or has a different intensity. Leave "
    "every ingredient that isn't missing unchanged. If a list of ingredients currently in stock at the bar is "
    "given, you MUST pick each substitute from that stock list when a reasonable one exists there — never "
    "suggest something that isn't in stock when an in-stock alternative would work. Only reach for something "
    "not in the stock list if nothing on it is a sensible substitute, and say so plainly in the summary (e.g. "
    "'not in stock — needs sourcing') so the bartender isn't caught by surprise. Summarize what you changed in "
    "one short, plain sentence."
)

def adapt_recipe(name, ingredients, garnish, instructions, missing_terms, available_ingredients=None) -> AdaptedRecipe:
    user_content = (
        f"{name}\n"
        f"Original ingredients: {ingredients}\n"
        f"Garnish: {garnish or 'none'}\n"
        f"Instructions: {instructions or 'none'}\n"
        f"Missing ingredients: {', '.join(missing_terms)}"
    )
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
    return AdaptedRecipe.model_validate_json(response.choices[0].message.tool_calls[0].function.arguments)
