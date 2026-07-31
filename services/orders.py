import html
import json
from .db import get_connection
from .notifications import notify_admin
from .inventory import available_ingredient_terms, missing_ingredients, decrement_for_order
from .recipe_adapt import adapt_recipe
from .format_recipe import format_ingredients_list, format_instructions_list
from .order_message import generate_order_message

def _format_ingredient_line(ing) -> str:
    quantity = f"{ing.quantity:g}"
    if ing.unit == "count":
        return f"{quantity} {ing.name}"
    return f"{quantity} {ing.unit} {ing.name}"

def place_order(user_id: int, cocktail_id: int, preferences: str | None = None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT name FROM users WHERE id = %s", (user_id,))
    user_row = cur.fetchone()
    if user_row is None:
        cur.close()
        conn.close()
        raise ValueError("User not found. Please complete onboarding first.")
    guest_name = user_row[0]

    cur.execute(
        "SELECT name, category, ingredients, garnish, instructions FROM cocktails WHERE id = %s",
        (cocktail_id,)
    )
    cocktail_row = cur.fetchone()
    if cocktail_row is None:
        cur.close()
        conn.close()
        raise ValueError("Cocktail not found.")
    name, category, ingredients, garnish, instructions = cocktail_row

    try:
        available_ingredients = available_ingredient_terms() if preferences else None
        message = generate_order_message(name, ingredients, garnish, instructions, preferences, available_ingredients)
        ingredients_text = "\n".join(f"- {_format_ingredient_line(ing)}" for ing in message.ingredients)
        instructions_text = "\n".join(f"{i}. {step}" for i, step in enumerate(message.instructions, start=1))
        story_text = message.story
        adjustments_text = message.adjustments if preferences else None
        ingredients_json = json.dumps([ing.model_dump() for ing in message.ingredients])
    except Exception as e:
        print(f"Order message generation failed, falling back to raw recipe formatting: {e}")
        ingredients_text = format_ingredients_list(ingredients)
        instructions_text = format_instructions_list(instructions)
        story_text = None
        adjustments_text = None
        ingredients_json = None

    cur.execute("""
        INSERT INTO orders (user_id, cocktail_id, preferences, ingredients_text, instructions_text, story_text, adjustments_text, ingredients_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (user_id, cocktail_id, preferences, ingredients_text, instructions_text, story_text, adjustments_text, ingredients_json))
    order_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    safe_guest_name = html.escape(guest_name)
    safe_preferences = html.escape(preferences) if preferences else None

    lines = [
        f"🍹 <b>New order #{order_id}</b>",
        f"Guest: {safe_guest_name}",
        f"Cocktail: <b>{name}</b>" + (f" ({category})" if category else ""),
    ]
    if story_text:
        lines.append(f"\n<i>{story_text}</i>")
    lines.append(f"\n<b>Ingredients</b>\n{ingredients_text}")
    if garnish:
        lines.append(f"\n<b>Garnish</b>\n{garnish}")
    if instructions_text:
        lines.append(f"\n<b>Instructions</b>\n{instructions_text}")
    if safe_preferences:
        lines.append(f"\n<b>Guest preferences</b>\n{safe_preferences}")
    if adjustments_text:
        lines.append(f"\n<i>Adjusted: {adjustments_text}</i>")

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "▶️ Start", "callback_data": f"orderstatus:in_progress:{order_id}"},
                {"text": "✕ Cancel", "callback_data": f"orderstatus:cancelled:{order_id}"}
            ],
            [
                {"text": "🔄 Adapt Recipe", "callback_data": f"adapt:{order_id}"}
            ]
        ]
    }
    notify_admin("\n".join(lines), reply_markup, parse_mode="HTML")

    return {"order_id": order_id, "cocktail": name}

def update_order_status(order_id: int, status: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT status, ingredients_json FROM orders WHERE id = %s", (order_id,))
    row = cur.fetchone()
    previous_status, ingredients_json = row if row else (None, None)

    cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))

    conn.commit()
    cur.close()
    conn.close()

    if status == "completed" and previous_status != "completed" and ingredients_json:
        try:
            unmatched = decrement_for_order(json.loads(ingredients_json))
            if unmatched:
                print(f"Order #{order_id} completed — no inventory match, not decremented: {', '.join(unmatched)}")
        except Exception as e:
            print(f"Inventory decrement failed for order #{order_id}: {e}")

def adapt_order_recipe(order_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT cocktails.name, cocktails.ingredients, cocktails.garnish, cocktails.instructions,
               cocktails.required_ingredients
        FROM orders
        JOIN cocktails ON cocktails.id = orders.cocktail_id
        WHERE orders.id = %s
    """, (order_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        raise ValueError("Order not found.")
    name, ingredients, garnish, instructions, required = row

    available_terms = available_ingredient_terms()
    missing = missing_ingredients(required, available_terms)
    if not missing:
        return {"cocktail": name, "missing": [], "adapted_ingredients": None, "changes": None}

    result = adapt_recipe(name, ingredients, garnish, instructions, missing, available_terms)
    return {"cocktail": name, "missing": missing, "adapted_ingredients": result.adapted_ingredients, "changes": result.changes}

def list_orders_for_user(user_id: int, limit: int = 5):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT orders.id, cocktails.name, orders.status, orders.created_at
        FROM orders
        JOIN cocktails ON cocktails.id = orders.cocktail_id
        WHERE orders.user_id = %s
        ORDER BY orders.created_at DESC
        LIMIT %s
    """, (user_id, limit))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {"order_id": row[0], "cocktail": row[1], "status": row[2], "created_at": row[3].isoformat()}
        for row in rows
    ]

def popular_cocktails_for_user(user_id: int, limit: int = 3):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT cocktails.id, cocktails.name, COUNT(*) AS order_count
        FROM orders
        JOIN cocktails ON cocktails.id = orders.cocktail_id
        WHERE orders.user_id = %s
        GROUP BY cocktails.id, cocktails.name
        ORDER BY order_count DESC
        LIMIT %s
    """, (user_id, limit))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [{"cocktail_id": row[0], "name": row[1], "order_count": row[2]} for row in rows]

def list_recent_orders(limit: int = 20, statuses: list[str] | None = None, date: str | None = None):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT orders.id, users.name, cocktails.name, orders.preferences, orders.created_at, orders.status,
               orders.ingredients_text, cocktails.garnish, orders.instructions_text, orders.story_text,
               orders.adjustments_text
        FROM orders
        JOIN users ON users.id = orders.user_id
        JOIN cocktails ON cocktails.id = orders.cocktail_id
    """
    conditions = []
    params = []
    if statuses:
        conditions.append("orders.status = ANY(%s)")
        params.append(statuses)
    if date:
        conditions.append("orders.created_at::date = %s")
        params.append(date)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY orders.created_at DESC LIMIT %s"
    params.append(limit)

    cur.execute(query, params)

    results = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "order_id": row[0],
            "guest_name": row[1],
            "cocktail": row[2],
            "preferences": row[3],
            "created_at": row[4].isoformat(),
            "status": row[5],
            "ingredients": row[6],
            "garnish": row[7],
            "instructions": row[8],
            "story": row[9],
            "adjustments": row[10]
        }
        for row in results
    ]
