import os
from openai import OpenAI, pydantic_function_tool
from .models import CocktailSelection, CocktailPick

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

TOOL_NAME = "select_cocktails"
TOOLS = [pydantic_function_tool(
    CocktailSelection,
    name=TOOL_NAME,
    description="Select and rank the best-fitting cocktails for this guest from the candidate shortlist, with a short personalized vibe blurb for each pick."
)]

SYSTEM_PROMPT = (
    "You are an expert bartender picking cocktails for a specific guest from a shortlist that was already "
    "narrowed down by flavor similarity. Read the guest's preferences and select the ones that truly fit "
    "their mood and taste, ranked best match first. If several candidates are near-duplicates of each other "
    "(same base spirits and build, or clearly variants of the same drink), only keep the single best one — "
    "prefer a diverse, well-matched set over near-identical picks. For each pick, also write a short vibe blurb "
    "connecting the drink to this guest specifically."
)

def select_cocktails(preferences_text, candidates, top_k) -> list[CocktailPick]:
    listing = "\n".join(
        f"id={c['id']} | {c['name']} | {c['flavor_description'] or c['ingredients']}"
        for c in candidates
    )
    user_content = (
        f"Guest preferences: {preferences_text}\n\n"
        f"Pick the best {top_k} from these candidates:\n{listing}"
    )

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

    selection = CocktailSelection.model_validate_json(response.choices[0].message.tool_calls[0].function.arguments)
    return selection.cocktails
