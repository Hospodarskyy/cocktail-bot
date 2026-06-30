import os
from anthropic import Anthropic

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
MAX_TURNS = 4

_client = None

def get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client

TOOLS = [
    {
        "name": "ask_question",
        "description": "Ask the guest a single short, friendly leading question to learn their cocktail preferences, like a professional bartender would.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-4 short plausible answers the guest can tap as buttons. The guest can also type a free-text answer instead."
                }
            },
            "required": ["question", "options"]
        }
    },
    {
        "name": "finish",
        "description": "Call this once you have enough information to recommend a cocktail. Summarize the guest's taste preferences in one paragraph suitable for a semantic search engine.",
        "input_schema": {
            "type": "object",
            "properties": {
                "preferences_summary": {"type": "string"}
            },
            "required": ["preferences_summary"]
        }
    }
]

SYSTEM_PROMPT = (
    "You are a friendly professional bartender getting to know a guest so you can recommend a cocktail. "
    "Ask short, leading questions one at a time (spirit preference, sweet/sour/bitter, strong/light, mood/occasion), "
    "using the ask_question tool. Once you have a good sense of their taste, call finish with a one-paragraph "
    "summary of their preferences written for a semantic search engine over a cocktail database."
)

def _find_tool_use(content_blocks):
    for block in content_blocks:
        if block.type == "tool_use":
            return block
    return None

def next_turn(history, answer_text=None, force_finish=False):
    history = list(history)
    is_first_turn = not history

    if is_first_turn:
        history.append({"role": "user", "content": answer_text or "I'd like help finding a cocktail I'll enjoy."})
    else:
        last_tool_use = _find_tool_use(history[-1]["content"])
        history.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": last_tool_use.id, "content": answer_text}]
        })

    tool_choice = {"type": "tool", "name": "finish"} if force_finish else {"type": "any"}

    response = get_client().messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_choice=tool_choice,
        messages=history
    )

    history.append({"role": "assistant", "content": response.content})

    tool_use = _find_tool_use(response.content)
    if tool_use.name == "ask_question":
        result = {"type": "question", "question": tool_use.input["question"], "options": tool_use.input.get("options", [])}
    else:
        result = {"type": "done", "preferences_summary": tool_use.input["preferences_summary"]}

    return result, history
