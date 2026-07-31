import os
from openai import OpenAI
from .db import get_connection
from .users import get_user, onboard_user

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

SYSTEM_PROMPT = (
    "You maintain a guest's cocktail taste profile for a recommendation engine. You'll be given their current "
    "profile paragraph and a cocktail they just ordered (with its flavor description), plus any preferences they "
    "noted for that specific order. Write an updated one-paragraph profile that incorporates this order as a real "
    "signal of their taste — reinforce what this order confirms, and adjust anything it contradicts. Keep it "
    "concrete and written for a semantic search engine over a cocktail database, the way the current profile is."
)

def update_profile_from_order(current_preferences, cocktail_name, cocktail_flavor_description, order_preferences):
    order_note = f"\n\nNote for this order: {order_preferences}" if order_preferences else ""
    user_content = (
        f"Current profile: {current_preferences}\n\n"
        f"Just ordered: {cocktail_name} — {cocktail_flavor_description}"
        f"{order_note}"
    )
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]
    )
    return response.choices[0].message.content.strip()

def update_profile_from_order_placement(user_id: int, cocktail_id: int, order_preferences: str | None):
    user = get_user(user_id)
    if user is None or not user["preferences"]:
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, flavor_description FROM cocktails WHERE id = %s", (cocktail_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return
    cocktail_name, flavor_description = row

    try:
        updated = update_profile_from_order(user["preferences"], cocktail_name, flavor_description or "", order_preferences)
        onboard_user(user_id, user["name"], updated)
    except Exception as e:
        print(f"Profile update from order failed, leaving profile unchanged: {e}")
