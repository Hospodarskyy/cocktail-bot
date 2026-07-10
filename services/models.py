from typing import Literal, Optional
from pydantic import BaseModel, Field

Unit = Literal["ml", "count"]
InventoryMode = Literal["set", "add", "subtract"]

INVENTORY_CATEGORIES = [
    "Base Spirits", "Liqueurs", "Bitters", "Juices",
    "Syrups & Sweeteners", "Garnishes", "Mixers", "Other"
]

JIGGER_RULES = (
    "When converting oz to ml, use standard bartending jigger increments, not the precise 29.5735 ml/oz "
    "conversion factor — bar jiggers are marked in round numbers: 0.25 oz = 7.5 ml, 0.5 oz = 15 ml, "
    "0.75 oz = 22.5 ml, 1 oz = 30 ml, 1.5 oz = 45 ml, 2 oz = 60 ml. For any other amount, round to the "
    "nearest 2.5 ml so it's actually measurable with a jigger — never output an unrounded decimal like 14.79 ml."
)

UNIT_RULES = (
    "For liquids (spirits, liqueurs, juices, syrups, mixers, bitters), always express quantity in "
    "milliliters (unit='ml'), converting from whatever the admin wrote: a standard liquor bottle is "
    "~750ml, a handle is ~1750ml, a fifth is ~750ml, 1 liter/L = 1000ml. " + JIGGER_RULES + " A case of "
    "N bottles = N times the bottle size. If the exact container size is ambiguous, use the most common "
    "standard size and briefly say so in `note`. For discrete/countable items (fruit, garnishes, jars, "
    "non-liquid goods), use unit='count' and just the plain number — no conversion."
)

MODE_RULES = (
    "Whether this quantity replaces current stock ('set', the default — plain statements like 'vodka: 500ml' "
    "or 'set vodka to 500ml'), adds to current stock ('add' — phrasing like 'add 2 litres of orange juice', "
    "'received a delivery of...', 'got more...', 'restocked...'), or subtracts from current stock ('subtract' "
    "— phrasing like 'used up 300ml', 'remove 2 limes', 'we're out of 1 bottle of...'). Set to null if the "
    "phrasing is a plain statement of amount with no add/remove intent — it defaults to 'set'."
)

# --- services/bot/inventory_llm.py ---

class InventoryUpdateItem(BaseModel):
    name: str
    quantity: float
    unit: Unit
    mode: Optional[InventoryMode] = Field(default=None, description=MODE_RULES)
    note: Optional[str] = Field(default=None, description="Any assumption made while converting units, e.g. 'assumed 750ml/bottle'. Null if there was none.")

class InventoryUpdateBatch(BaseModel):
    ingredients: list[InventoryUpdateItem] = Field(description="One structured entry per ingredient mentioned in the admin's stock update.")

class InventoryQuantity(BaseModel):
    quantity: float
    unit: Unit
    mode: Optional[InventoryMode] = Field(default=None, description=MODE_RULES)
    note: Optional[str] = Field(default=None, description="Any assumption made while converting units, e.g. 'assumed 750ml/bottle'. Null if there was none.")

# --- services/inventory_categorize.py ---

class InventoryCategory(BaseModel):
    category: Literal[*INVENTORY_CATEGORIES]

# --- services/required_ingredients.py ---

class RequiredIngredients(BaseModel):
    ingredients: list[str] = Field(
        description="Short, generalized ingredient terms (e.g. 'gin', 'lime juice', 'orange bitters') — strip "
                     "brand names, keep the base spirit/liqueur/mixer category. Exclude always-available basics "
                     "like ice and water."
    )

# --- services/recipe_adapt.py ---

class AdaptedRecipe(BaseModel):
    adapted_ingredients: str = Field(
        description="The full ingredients list, in the same style/format as the original, with substitutions "
                     "made for anything unavailable. Keep amounts for unaffected ingredients unchanged."
    )
    changes: str = Field(description="One short sentence summarizing what was substituted and why.")

# --- services/recommend_llm.py ---

class CocktailPick(BaseModel):
    id: int
    vibe: str = Field(
        description="1-2 sentence description of how this cocktail feels and why it fits this guest's "
                     "mood/taste right now. Warm, evocative, written directly for the guest. No history or "
                     "trivia — just the vibe."
    )

class CocktailSelection(BaseModel):
    cocktails: list[CocktailPick] = Field(description="Chosen cocktails, best match first.")

# --- services/order_message.py ---

class OrderIngredient(BaseModel):
    name: str
    quantity: float
    unit: Unit = Field(
        description="Convert any liquid pour measurement (oz, cl, dashes of syrup, etc.) to milliliters, since "
                     "that's how the bar tracks stock. " + JIGGER_RULES + " Non-liquid/non-volumetric items "
                     "(e.g. an egg white, a pinch of salt) should use 'count' with a plain number."
    )

class OrderMessage(BaseModel):
    ingredients: list[OrderIngredient] = Field(description="Ingredients in preparation order, unit-normalized.")
    instructions: list[str] = Field(description="Each preparation step as one short imperative sentence, in order.")
    story: str = Field(
        description="2-4 sentence story about this cocktail's history, origin, or the myth/legend behind its "
                     "creation — bartender trivia to read while making the drink. If no real documented history "
                     "is well known, write a short evocative piece in the spirit of classic cocktail lore rather "
                     "than inventing specific false facts presented as certain history."
    )
    adjustments: Optional[str] = Field(
        default=None,
        description="Only if the guest gave order preferences: one short sentence summarizing how the "
                     "ingredients/instructions were adjusted to honor them. Null if there were no guest "
                     "preferences to adjust for."
    )

# --- services/bot/llm_openai.py ---

class AskQuestion(BaseModel):
    question: str
    options: list[str] = Field(
        description="3-4 short, playful, in-character answers the guest can tap as buttons (not literal spirit "
                     "names). The guest can also type a free-text answer instead."
    )

class FinishQA(BaseModel):
    preferences_summary: str

# --- services/bot/cocktail_intake.py ---

class AskCocktailDetail(BaseModel):
    question: str = Field(description="One short, specific question about the single most important missing piece of the recipe (name, ingredients, or instructions). Never ask about garnish — it's optional.")

class CocktailDraft(BaseModel):
    name: str
    ingredients: str = Field(description="Full ingredients list with amounts, in whatever units the admin used, as one string (comma or newline separated, matching how it was given).")
    garnish: Optional[str] = Field(default=None, description="Garnish, if any was mentioned. Null if not mentioned.")
    instructions: str = Field(description="Preparation steps, as given or lightly cleaned up into clear steps.")
