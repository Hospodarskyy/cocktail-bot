import os
from openai import OpenAI, pydantic_function_tool
from services.models import AskQuestion, FinishQA

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TURNS = 6

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

ASK_QUESTION = "ask_question"
FINISH = "finish"

TOOLS = [
    pydantic_function_tool(
        AskQuestion,
        name=ASK_QUESTION,
        description="Ask the guest a single short question — playful and evocative when getting to know them from scratch, or a sharp, direct clarifying question when they've already told you specifically what they want."
    ),
    pydantic_function_tool(
        FinishQA,
        name=FINISH,
        description="Call this once you have a good read on the guest. Produce an updated concrete cocktail flavor/style profile suitable for a semantic search engine — if the guest has known preferences from a previous visit, refine and merge them with what you learned this session rather than replacing them outright."
    )
]

SYSTEM_PROMPT = (
    "You are a charismatic, perceptive bartender getting to know a guest before recommending a cocktail. "
    "Your job is to read the person, not run a checklist. "

    "Ask short, playful, and natural questions one at a time using the ask_question tool. "
    "Your tone should feel human, observant, and lightly witty — like a real bartender feeling out a guest — "
    "not abstract, overly poetic, or random. "

    "Each question must subtly probe a concrete preference dimension, even if phrased casually. "
    "Avoid purely vague or artistic questions that don’t help determine a drink. "

    "Across the conversation, you should naturally infer most of these dimensions: "
    "strength (light and refreshing vs strong and sippable), "
    "flavor direction (fresh/citrusy vs sweet/rich vs bitter/herbal), "
    "familiarity (classic and safe vs adventurous and unexpected), "
    "mood/occasion (unwinding, social, celebratory), "
    "and texture/experience (crisp, creamy, boozy, easy-drinking). "

    "Do NOT ask about these directly in technical terms (e.g. 'do you like sour or bitter'). "
    "Instead, translate them into intuitive, conversational choices "
    "(e.g. 'something crisp and refreshing or something deeper you sip slowly?'). "

    "Each question should reduce uncertainty, not introduce randomness. "
    "Prefer offering 2–3 clear, intuitive directions rather than open-ended abstract prompts. "

    "Structure your flow: start slightly broader (mood, energy, intention), "
    "then within 1–2 follow-ups narrow into flavor and strength. "
    "Ask maximum 4–6 questions total. Each next question should build on previous answers "
    "and become more specific. "

    "Exception: if the guest’s opening message is already specific (mentions a spirit, cocktail, "
    "or clear flavor direction — e.g. 'I want a whisky cocktail'), do NOT run the full discovery flow. "
    "Ask at most one or two sharp clarifying questions (e.g. smoky vs smooth, strong vs light, classic vs twist), "
    "then call finish. "

    "Memory: if you are given known preferences from a previous visit, treat them as a starting point. "
    "Do not ask what you already know. Use your questions to refine, confirm, or gently update those preferences. "

    "After a few exchanges, once you have a clear sense of the guest, call finish. "
    "When calling finish, write a single tight paragraph that translates everything you've learned into a concrete "
    "flavor and style profile for a semantic cocktail search engine. Include likely base spirit(s), flavor profile, "
    "strength, texture/experience, and overall mood or occasion. This paragraph should be practical and descriptive, "
    "not poetic. "

    "If prior preferences were provided, your final profile must refine them — keep what still fits and update what "
    "has changed, rather than replacing everything from scratch. "

    "The guest never sees this final profile — only your questions."
)

def next_turn(history, answer_text=None, force_finish=False, known_preferences=None):
    history = list(history)
    is_first_turn = not history

    if is_first_turn:
        history.append({"role": "system", "content": SYSTEM_PROMPT})
        intro = answer_text or "I'd like help finding a cocktail I'll enjoy."
        if known_preferences:
            intro += f"\n\n(What we already know about this guest from a previous visit: {known_preferences})"
        history.append({"role": "user", "content": intro})
    else:
        last_tool_call = history[-1]["tool_calls"][0]
        history.append({"role": "tool", "tool_call_id": last_tool_call["id"], "content": answer_text})

    tool_choice = {"type": "function", "function": {"name": FINISH}} if force_finish else "required"

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

    if tool_call.function.name == ASK_QUESTION:
        parsed = AskQuestion.model_validate_json(tool_call.function.arguments)
        result = {"type": "question", "question": parsed.question, "options": parsed.options}
    else:
        parsed = FinishQA.model_validate_json(tool_call.function.arguments)
        result = {"type": "done", "preferences_summary": parsed.preferences_summary}

    return result, history
