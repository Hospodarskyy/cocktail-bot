import pandas as pd
from .db import get_connection

def load_hotaling_data(csv_path: str):
    df = pd.read_csv(csv_path)

    df = df.dropna(subset=["Cocktail Name", "Ingredients"])
    df = df.fillna("")

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO cocktails (name, category, ingredients, garnish, instructions)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            row["Cocktail Name"],
            row.get("Bar/Company", ""),
            row["Ingredients"],
            row.get("Garnish", ""),
            row.get("Preparation", "")
        ))
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {inserted} cocktails")

if __name__ == "__main__":
    csv_path = "data/cocktail-dataset.csv"
    load_hotaling_data(csv_path)
