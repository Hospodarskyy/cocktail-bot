import os
from openai import OpenAI, pydantic_function_tool
from services.models import AskCocktailDetail, CocktailDraft

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TURNS = 5

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

ASK = "ask_for_missing_info"
RECORD = "record_cocktail"

TOOLS = [
    pydantic_function_tool(
        AskCocktailDetail, name=ASK,
        description="Ask the admin one short question to get a missing or unclear piece of the recipe."
    ),
    pydantic_function_tool(
        CocktailDraft, name=RECORD,
        description="Record the extracted cocktail recipe once there's enough to save it."
    )
]

SYSTEM_PROMPT = (
    "You are helping a bar admin add a new cocktail recipe to the catalog from free-form text. Extract the "
    "cocktail's name, ingredients (with amounts, in whatever units the admin used), garnish (if mentioned), "
    "and preparation instructions. If the name, ingredients, or instructions are missing or too vague to be "
    "usable, ask one short, specific follow-up question for the single most important missing piece — never "
    "ask about garnish, it's optional and should just be left out if not mentioned. Once you have enough for "
    "a usable recipe, call record_cocktail."
)

def next_turn(history, answer_text=None, force_finish=False):
    history = list(history)
    is_first_turn = not history

    if is_first_turn:
        history.append({"role": "system", "content": SYSTEM_PROMPT})
        history.append({"role": "user", "content": answer_text})
    else:
        last_tool_call = history[-1]["tool_calls"][0]
        history.append({"role": "tool", "tool_call_id": last_tool_call["id"], "content": answer_text})

    tool_choice = {"type": "function", "function": {"name": RECORD}} if force_finish else "required"

    response = get_client().chat.completions.create(
        model=MODEL,
        messages=history,
        tools=TOOLS,
        tool_choice=tool_choice,
        parallel_tool_calls=False
    )

    message = response.choices[0].message
    history.append({
        "role": "assistant",
        "content": message.content,
        "tool_calls": [tc.model_dump() for tc in message.tool_calls]
    })

    tool_call = message.tool_calls[0]
    if tool_call.function.name == ASK:
        parsed = AskCocktailDetail.model_validate_json(tool_call.function.arguments)
        result = {"type": "question", "question": parsed.question}
    else:
        parsed = CocktailDraft.model_validate_json(tool_call.function.arguments)
        result = {"type": "done", "cocktail": parsed}

    return result, history
