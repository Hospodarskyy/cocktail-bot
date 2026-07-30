import os

import boto3
import requests
from openai import OpenAI

from .db import get_connection

IMAGES_BUCKET = os.getenv("IMAGES_BUCKET", "cocktail-mlops-images-oles")
IMAGES_PREFIX = "cocktail-images"
SEEDREAM_MODEL = "seedream-4-5-251128"
IMAGE_SIZE = "1440x2560"  # 9:16, meets seedream-4.5's minimum pixel requirement
GLASS_CLASSIFIER_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_seedream_client = None
_openai_client = None

VALID_GLASS_TYPES = [
    "highball", "collins", "rocks (old fashioned)", "coupe", "martini",
    "hurricane", "copper mug", "champagne flute", "nick and nora", "shot",
]

GLASS_CLASSIFIER_SYSTEM_PROMPT = (
    "You are a bartender. Given a cocktail's name and ingredients, respond with "
    "ONLY the single most appropriate glass type for serving it, chosen exactly "
    "from this list (respond with just the phrase, nothing else): "
    + ", ".join(VALID_GLASS_TYPES)
)


def _get_seedream_client():
    global _seedream_client
    if _seedream_client is None:
        _seedream_client = OpenAI(
            api_key=os.getenv("ARK_API_KEY"),
            base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
            timeout=180.0,
        )
    return _seedream_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


def _infer_glass_type(cocktail_name: str, ingredients: str) -> str:
    """
    Classifies the specific glass type rather than leaving it to the image
    model's own judgment — a vague "a glass appropriate to this cocktail"
    instruction made Seedream default to the same glass shape for every
    cocktail, since it isn't actually reasoning about serving conventions,
    just pattern-matching to a generic "cocktail glass" concept.
    """
    response = _get_openai_client().chat.completions.create(
        model=GLASS_CLASSIFIER_MODEL,
        messages=[
            {"role": "system", "content": GLASS_CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": f"{cocktail_name} — {ingredients}"},
        ],
    )
    glass_type = response.choices[0].message.content.strip().lower()

    # Guard against the model returning something outside the fixed list
    # (free-form drift) — fall back to a safe, common default rather than
    # feeding an unpredictable phrase into the image prompt.
    if glass_type not in VALID_GLASS_TYPES:
        glass_type = "rocks (old fashioned)"

    return glass_type


def _build_prompt(cocktail_name: str, ingredients: str, glass_type: str) -> str:
    input_text = f"{cocktail_name} — {ingredients}"

    return f"""Cocktail: {input_text}

---

Using the above as the cocktail's name, recipe, and ingredients, generate a
full-bleed vertical (9:16 portrait) illustration that fills the entire frame
edge-to-edge — the dark charcoal/black background itself IS the image, not a
card or poster floating on a plain surface. No borders, no frame, no background
behind a card — the whole canvas is the scene.

In the upper two-thirds of the composition, an illustration of a {glass_type}
glass (this specific glass shape, not a generic tall glass), containing a
liquid whose color matches its main ingredients, garnished appropriately based
on the ingredients listed, ice cubes visible where appropriate for this glass
type, thin elegant white outline sketch style for the glass, soft realistic
lighting on the liquid and garnish only.

In the lower third, bold clean sans-serif title text reading the cocktail's
name in capital letters, in white, large and prominent.

Below the title, the ingredient list with their exact measurements exactly as
given in the input above, each on its own line in thin white text (e.g.
"1.5 oz Gin", ".75 oz Simple Syrup", ".75 oz Lime Juice").

Below the ingredient list, a short one-sentence description of the cocktail's
taste and character in muted gold text, inferred from its ingredients and
recipe (e.g. "Vibrant and botanical, with a crisp citrus edge").

A row of small thin-line icons near the ingredient list (glass icon, ice icon,
and one or two icons matching the fruit/herb ingredients present), consistent
minimalist line-art style.

Overall style: high-end cocktail bar menu design, elegant typography,
consistent illustrated (not photographic) rendering, dark background filling
the entire frame with no visible edges or margins, gold and white color accents
only, no other colors in text or icons, clean negative space. All text in
English only. No watermarks, no logos, no card outline, no frame, no border,
no plain background behind a floating object."""


def _generate_and_upload(cocktail_id: int, cocktail_name: str, ingredients: str) -> str:
    """Calls Seedream, downloads the (short-lived) result, and re-uploads it
    to our own S3 bucket so we control the URL's lifetime — the presigned
    TOS link Seedream returns expires after 24 hours, so we never store
    that link itself, only what it points to."""
    glass_type = _infer_glass_type(cocktail_name, ingredients)

    client = _get_seedream_client()
    response = client.images.generate(
        model=SEEDREAM_MODEL,
        prompt=_build_prompt(cocktail_name, ingredients, glass_type),
        size=IMAGE_SIZE,
    )
    temp_url = response.data[0].url

    image_bytes = requests.get(temp_url, timeout=30).content

    s3 = boto3.client("s3")
    key = f"{IMAGES_PREFIX}/{cocktail_id}.jpeg"
    s3.put_object(
        Bucket=IMAGES_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )

    return f"https://{IMAGES_BUCKET}.s3.amazonaws.com/{key}"


def get_or_generate_image(cocktail_id: int, cocktail_name: str, ingredients: str) -> str:
    """Returns a durable image URL for this cocktail, generating and caching
    it on first request. Every call after the first is a single DB read —
    no repeat Seedream call, no repeat cost, matching the same caching
    principle already used for cocktail story generation."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT image_url FROM cocktails WHERE id = %s", (cocktail_id,))
    row = cur.fetchone()
    if row and row[0]:
        cur.close()
        conn.close()
        return row[0]

    image_url = _generate_and_upload(cocktail_id, cocktail_name, ingredients)

    cur.execute("UPDATE cocktails SET image_url = %s WHERE id = %s", (image_url, cocktail_id))
    conn.commit()
    cur.close()
    conn.close()

    return image_url