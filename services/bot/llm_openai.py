import os
import json
from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TURNS = 4

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ask_question",
            "description": "Ask the guest a single short, friendly leading question to learn their cocktail preferences, like a professional bartender would.",
            "parameters": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call this once you have enough information to recommend a cocktail. Summarize the guest's taste preferences in one paragraph suitable for a semantic search engine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preferences_summary": {"type": "string"}
                },
                "required": ["preferences_summary"]
            }
        }
    }
]

SYSTEM_PROMPT = (
    "You are a friendly professional bartender getting to know a guest so you can recommend a cocktail. "
    "Ask short, leading questions one at a time (spirit preference, sweet/sour/bitter, strong/light, mood/occasion), "
    "using the ask_question tool. Once you have a good sense of their taste, call finish with a one-paragraph "
    "summary of their preferences written for a semantic search engine."
)

def next_turn(history, answer_text=None, force_finish=False):
    history = list(history)
    is_first_turn = not history

    if is_first_turn:
        history.append({"role": "system", "content": SYSTEM_PROMPT})
        history.append({"role": "user", "content": answer_text or "I'd like help finding a cocktail I'll enjoy."})
    else:
        last_tool_call = history[-1]["tool_calls"][0]
        history.append({"role": "tool", "tool_call_id": last_tool_call["id"], "content": answer_text})

    tool_choice = {"type": "function", "function": {"name": "finish"}} if force_finish else "required"

    response = get_client().chat.completions.create(
        model=MODEL,
        messages=history,
        tools=TOOLS,
        tool_choice=tool_choice
    )

    message = response.choices[0].message
    history.append({
        "role": "assistant",
        "content": message.content,
        "tool_calls": [tc.model_dump() for tc in message.tool_calls]
    })

    tool_call = message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)

    if tool_call.function.name == "ask_question":
        result = {"type": "question", "question": args["question"], "options": args.get("options", [])}
    else:
        result = {"type": "done", "preferences_summary": args["preferences_summary"]}

    return result, history
