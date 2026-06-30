from .db import get_connection
from .notifications import notify_admin

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

    cur.execute("""
        INSERT INTO orders (user_id, cocktail_id, preferences)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (user_id, cocktail_id, preferences))
    order_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    lines = [
        f"🍹 New order #{order_id}",
        f"Guest: {guest_name}",
        f"Cocktail: {name}" + (f" ({category})" if category else ""),
        f"Ingredients: {ingredients}",
    ]
    if garnish:
        lines.append(f"Garnish: {garnish}")
    if instructions:
        lines.append(f"Instructions: {instructions}")
    if preferences:
        lines.append(f"Guest preferences: {preferences}")

    reply_markup = {
        "inline_keyboard": [[
            {"text": "▶️ Start", "callback_data": f"orderstatus:in_progress:{order_id}"},
            {"text": "✕ Cancel", "callback_data": f"orderstatus:cancelled:{order_id}"}
        ]]
    }
    notify_admin("\n".join(lines), reply_markup)

    return {"order_id": order_id, "cocktail": name}

def update_order_status(order_id: int, status: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))

    conn.commit()
    cur.close()
    conn.close()

def list_recent_orders(limit: int = 20, statuses: list[str] | None = None):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT orders.id, users.name, cocktails.name, orders.preferences, orders.created_at, orders.status
        FROM orders
        JOIN users ON users.id = orders.user_id
        JOIN cocktails ON cocktails.id = orders.cocktail_id
    """
    params = []
    if statuses:
        query += " WHERE orders.status = ANY(%s)"
        params.append(statuses)
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
            "status": row[5]
        }
        for row in results
    ]
