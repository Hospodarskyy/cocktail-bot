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
        "description": "Ask the guest a single short question — playful and evocative when getting to know them from scratch, or a sharp, direct clarifying question when they've already told you specifically what they want.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-4 short, playful, in-character answers the guest can tap as buttons (not literal spirit names). The guest can also type a free-text answer instead."
                }
            },
            "required": ["question", "options"]
        }
    },
    {
        "name": "finish",
        "description": "Call this once you have a good read on the guest. Produce an updated concrete cocktail flavor/style profile suitable for a semantic search engine — if the guest has known preferences from a previous visit, refine and merge them with what you learned this session rather than replacing them outright.",
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
    "You are a charismatic, perceptive bartender getting to know a guest before recommending a cocktail. "
    "Your job is to read the person, not run a checklist. Ask short, playful, evocative questions one at a time "
    "using the ask_question tool — about their mood tonight, their personality, the kind of night they're having, "
    "a vibe or an analogy (e.g. 'if tonight had a soundtrack, what would it be?' or 'are you here to unwind or to "
    "make some noise?'). Avoid asking directly about spirits or sweet/sour/bitter — let their answers reveal that "
    "indirectly, and use each answer to inform a sharper, more specific follow-up question in the same playful tone. "
    "Exception: if the guest's opening message is already specific and direct (names a spirit, a cocktail, or a "
    "clear flavor direction — e.g. 'I want a whisky cocktail'), don't run the full mood-discovery flow. Ask at "
    "most one or two sharp, direct clarifying questions that build on what they already said (e.g. peaty/smoky vs "
    "smooth/sweet, strong vs light, on the rocks vs up) and then call finish — respect that they already told you "
    "what they want instead of making them play twenty questions. "
    "If you're told what's already known about this guest from a previous visit, treat it as a starting point, not "
    "a blank slate — don't ask about things you already know, and use your questions to refine or update it instead. "
    "After a few exchanges, once you have a real sense of who they are, call finish — this is where you, not the "
    "guest, translate everything you've learned into a concrete one-paragraph flavor/style profile (spirit, "
    "sweetness/bitterness/sourness, strength, mood) written for a semantic search engine over a cocktail database. "
    "If prior preferences were provided, the profile you write should be a refinement of them, keeping what's still "
    "true and updating what's changed — not a from-scratch replacement based only on this session. "
    "The guest never sees this translation, only the playful questions."
)

def _find_tool_use(content_blocks):
    for block in content_blocks:
        if block.type == "tool_use":
            return block
    return None

def next_turn(history, answer_text=None, force_finish=False, known_preferences=None):
    history = list(history)
    is_first_turn = not history

    if is_first_turn:
        intro = answer_text or "I'd like help finding a cocktail I'll enjoy."
        if known_preferences:
            intro += f"\n\n(What we already know about this guest from a previous visit: {known_preferences})"
        history.append({"role": "user", "content": intro})
    else:
        last_tool_use = _find_tool_use(history[-1]["content"])
        history.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": last_tool_use.id, "content": answer_text}]
        })

    tool_choice = (
        {"type": "tool", "name": "finish", "disable_parallel_tool_use": True}
        if force_finish else
        {"type": "any", "disable_parallel_tool_use": True}
    )

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
