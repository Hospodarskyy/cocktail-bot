from .db import get_connection

def upsert_ingredient(name: str, quantity: float, unit: str | None = None, mode: str = "set", category: str | None = None):
    name = name.strip()
    if not name:
        raise ValueError("Ingredient name cannot be blank.")
    if mode not in ("set", "add", "subtract"):
        raise ValueError(f"Invalid mode: {mode}")

    conn = get_connection()
    cur = conn.cursor()

    if mode == "set":
        cur.execute("""
            INSERT INTO inventory (ingredient_name, quantity, unit, category)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT ((LOWER(ingredient_name))) DO UPDATE SET
                quantity = EXCLUDED.quantity,
                unit = EXCLUDED.unit,
                category = COALESCE(EXCLUDED.category, inventory.category),
                updated_at = NOW()
        """, (name, quantity, unit, category))
    elif mode == "add":
        cur.execute("""
            INSERT INTO inventory (ingredient_name, quantity, unit, category)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT ((LOWER(ingredient_name))) DO UPDATE SET
                quantity = inventory.quantity + EXCLUDED.quantity,
                unit = EXCLUDED.unit,
                category = COALESCE(EXCLUDED.category, inventory.category),
                updated_at = NOW()
        """, (name, quantity, unit, category))
    else:  # subtract
        cur.execute("""
            INSERT INTO inventory (ingredient_name, quantity, unit, category)
            VALUES (%s, 0, %s, %s)
            ON CONFLICT ((LOWER(ingredient_name))) DO UPDATE SET
                quantity = GREATEST(0, inventory.quantity - %s),
                unit = EXCLUDED.unit,
                category = COALESCE(EXCLUDED.category, inventory.category),
                updated_at = NOW()
        """, (name, unit, category, quantity))

    conn.commit()
    cur.close()
    conn.close()

def list_inventory(category: str | None = None):
    conn = get_connection()
    cur = conn.cursor()

    if category:
        cur.execute("""
            SELECT id, ingredient_name, quantity, unit, updated_at, category
            FROM inventory
            WHERE category = %s
            ORDER BY LOWER(ingredient_name)
        """, (category,))
    else:
        cur.execute("""
            SELECT id, ingredient_name, quantity, unit, updated_at, category
            FROM inventory
            ORDER BY category NULLS LAST, LOWER(ingredient_name)
        """)

    results = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": row[0], "name": row[1], "quantity": row[2], "unit": row[3],
            "updated_at": row[4].isoformat(), "category": row[5]
        }
        for row in results
    ]

def inventory_categories_summary():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(category, 'Uncategorized'), COUNT(*)
        FROM inventory
        GROUP BY category
        ORDER BY category NULLS LAST
    """)

    results = cur.fetchall()
    cur.close()
    conn.close()

    return [{"category": row[0], "count": row[1]} for row in results]

def remove_ingredient(name: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE inventory SET quantity = 0, updated_at = NOW()
        WHERE LOWER(ingredient_name) = LOWER(%s)
    """, (name,))

    found = cur.rowcount > 0

    conn.commit()
    cur.close()
    conn.close()

    if not found:
        raise ValueError(f"Ingredient '{name}' not found.")

def available_ingredient_terms():
    stock = list_inventory()
    return [s["name"].lower() for s in stock if s["quantity"] and s["quantity"] > 0]

def missing_ingredients(required_ingredients, available_terms=None):
    if available_terms is None:
        available_terms = available_ingredient_terms()

    missing = []
    for req in required_ingredients or []:
        req_lower = req.lower()
        if not any(req_lower in term or term in req_lower for term in available_terms):
            missing.append(req)
    return missing

def resolve_inventory_name(name: str, items: list[dict] | None = None) -> str | None:
    """Fuzzy-match a name (case-insensitive, bidirectional substring, same rule as missing_ingredients())
    against real inventory rows, returning the actual stored ingredient_name if one matches, else None."""
    if items is None:
        items = list_inventory()
    name_lower = name.lower()
    for item in items:
        item_lower = item["name"].lower()
        if name_lower in item_lower or item_lower in name_lower:
            return item["name"]
    return None

def decrement_for_order(ingredients: list[dict]) -> list[str]:
    """Subtract a completed order's structured ingredients ({"name","quantity","unit"} dicts) from inventory.
    Ingredients with no matching inventory row are skipped, never inserted as a new row under the LLM's
    phrasing — returns the list of ingredient names that couldn't be matched, for logging."""
    items = list_inventory()
    unmatched = []
    for ing in ingredients:
        matched_name = resolve_inventory_name(ing["name"], items)
        if matched_name is None:
            unmatched.append(ing["name"])
            continue
        try:
            upsert_ingredient(matched_name, ing["quantity"], ing.get("unit"), mode="subtract")
        except Exception:
            unmatched.append(ing["name"])
    return unmatched
