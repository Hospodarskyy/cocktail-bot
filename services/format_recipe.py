import re

def format_ingredients_list(ingredients: str | None) -> str:
    if not ingredients:
        return ""
    items = [i.strip() for i in ingredients.split(",") if i.strip()]
    return "\n".join(f"- {item}" for item in items)

def format_instructions_list(instructions: str | None) -> str:
    if not instructions:
        return ""
    steps = [s.strip() for s in re.split(r"(?<=[.!?])\s+", instructions) if s.strip()]
    return "\n".join(f"{i}. {step}" for i, step in enumerate(steps, start=1))
