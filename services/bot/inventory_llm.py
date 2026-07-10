import os
from openai import OpenAI, pydantic_function_tool
from services.models import InventoryUpdateBatch, InventoryUpdateItem, InventoryQuantity, UNIT_RULES, MODE_RULES

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

BATCH_TOOL_NAME = "record_ingredients"
BATCH_TOOLS = [pydantic_function_tool(
    InventoryUpdateBatch,
    name=BATCH_TOOL_NAME,
    description="Record one structured entry per ingredient mentioned in the admin's stock update."
)]

BATCH_SYSTEM_PROMPT = (
    "You convert a bar admin's free-text stock update into structured inventory records, one per ingredient "
    "mentioned. " + UNIT_RULES + " " + MODE_RULES
)

SINGLE_TOOL_NAME = "record_quantity"
SINGLE_TOOLS = [pydantic_function_tool(
    InventoryQuantity,
    name=SINGLE_TOOL_NAME,
    description="Record the structured quantity the admin just gave for a specific, already-known ingredient."
)]

SINGLE_SYSTEM_PROMPT = (
    "You convert a bar admin's free-text answer about how much of a specific, already-named ingredient they "
    "have into a structured quantity. Only extract the amount — the ingredient name is already known. "
    + UNIT_RULES + " " + MODE_RULES
)

def parse_inventory_updates(text: str) -> list[InventoryUpdateItem]:
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": BATCH_SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        tools=BATCH_TOOLS,
        tool_choice={"type": "function", "function": {"name": BATCH_TOOL_NAME}},
        parallel_tool_calls=False
    )
    result = InventoryUpdateBatch.model_validate_json(response.choices[0].message.tool_calls[0].function.arguments)
    return result.ingredients

def parse_quantity(name: str, text: str) -> InventoryQuantity:
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SINGLE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Ingredient: {name}\nAdmin's answer: {text}"}
        ],
        tools=SINGLE_TOOLS,
        tool_choice={"type": "function", "function": {"name": SINGLE_TOOL_NAME}},
        parallel_tool_calls=False
    )
    return InventoryQuantity.model_validate_json(response.choices[0].message.tool_calls[0].function.arguments)
