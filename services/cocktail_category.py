from .db import get_connection

CATEGORIES = [
    "Gin", "Vodka", "Rum", "Whiskey", "Tequila & Mezcal",
    "Brandy & Cognac", "Amaro & Bitter Liqueurs", "Sparkling & Champagne", "Other"
]

# Keywords are deliberately narrow to each category's *defining* ingredient, not anything that merely
# appears as a modifier — e.g. "vermouth"/"sherry"/generic "liqueur" are common accents in classic
# spirit-forward drinks (Manhattan, Martini, Negroni) and would otherwise tag most of the catalog into
# a "wine" or "liqueur" bucket that doesn't reflect how the drink actually reads to a bartender.
SPIRIT_KEYWORDS = {
    "Gin": ["gin"],
    "Vodka": ["vodka"],
    "Rum": ["rum", "cachaca", "cachaça"],
    "Whiskey": ["whiskey", "whisky", "bourbon", "rye", "scotch"],
    "Tequila & Mezcal": ["tequila", "mezcal"],
    "Brandy & Cognac": ["brandy", "cognac", "armagnac", "calvados", "pisco"],
    "Amaro & Bitter Liqueurs": ["amaro", "campari", "aperol", "chartreuse", "fernet", "cynar", "suze"],
    "Sparkling & Champagne": ["champagne", "prosecco", "sparkling wine", "cava"],
}

def categorize_cocktail(required_ingredients):
    """Derive every matching base-spirit/style category from a cocktail's generalized ingredient list —
    deterministic keyword match, no LLM call needed since required_ingredients is already brand-stripped
    and generalized. A cocktail with multiple spirits (e.g. vodka + gin) belongs to every matching category.
    Falls back to ['Other'] if nothing matches."""
    terms = [t.lower() for t in (required_ingredients or [])]
    matches = [
        category for category, keywords in SPIRIT_KEYWORDS.items()
        if any(kw in term for term in terms for kw in keywords)
    ]
    return matches or ["Other"]

def generate_cocktail_categories():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, required_ingredients FROM cocktails WHERE categories IS NULL")
    rows = cur.fetchall()

    if not rows:
        cur.close()
        conn.close()
        return

    print(f"Categorizing {len(rows)} cocktails by base spirit...")
    for cocktail_id, required in rows:
        categories = categorize_cocktail(required)
        cur.execute("UPDATE cocktails SET categories = %s WHERE id = %s", (categories, cocktail_id))

    conn.commit()
    cur.close()
    conn.close()
    print("Done categorizing cocktails.")
