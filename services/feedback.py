from .db import get_connection

def log_feedback(user_id: int, cocktail_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM users WHERE id = %s", (user_id,))
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        raise ValueError("User not found. Please complete onboarding first.")

    cur.execute("SELECT 1 FROM cocktails WHERE id = %s", (cocktail_id,))
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        raise ValueError("Cocktail not found.")

    cur.execute("""
        INSERT INTO feedback (user_id, cocktail_id)
        VALUES (%s, %s)
    """, (user_id, cocktail_id))

    conn.commit()
    cur.close()
    conn.close()
