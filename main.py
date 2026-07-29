from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from services.recommender import recommend, recommend_from_text, cocktail_summary, cocktails_in_category
from services.db import init_db, get_connection
from services.data_loader import load_hotaling_data
from services.dataset_fetch import ensure_dataset_downloaded
from services.flavor import generate_flavor_descriptions
from services.required_ingredients import generate_required_ingredients
from services.embedder import generate_embeddings
from services.users import onboard_user, get_user, list_recent_users, clear_preferences
from services.orders import (
    place_order, list_recent_orders, update_order_status, adapt_order_recipe,
    list_orders_for_user, popular_cocktails_for_user
)
from services.feedback import log_feedback
from services.profile_update import update_profile_from_order_placement
from services.inventory import upsert_ingredient, list_inventory, remove_ingredient, inventory_categories_summary
from services.inventory_categorize import generate_inventory_categories
from services.cocktail_category import generate_cocktail_categories
from services.cocktails import create_cocktail
from services.model_registry import reload_champion_model, get_champion_version

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cocktails")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    
    if count == 0:
        dataset_path = ensure_dataset_downloaded("data/cocktail-dataset.csv")
        load_hotaling_data(dataset_path)

    generate_flavor_descriptions()
    generate_required_ingredients()
    generate_cocktail_categories()
    generate_embeddings()
    generate_inventory_categories()

    yield

app = FastAPI(title="Cocktail Recommender API", lifespan=lifespan)

class OnboardRequest(BaseModel):
    user_id: int
    name: str
    preferences: str

class RecommendRequest(BaseModel):
    user_id: int
    top_k: int = 5
    exclude_ids: list[int] | None = None

class SessionRecommendRequest(BaseModel):
    preferences: str
    top_k: int = 5
    exclude_ids: list[int] | None = None

class OrderRequest(BaseModel):
    user_id: int
    cocktail_id: int
    preferences: str | None = None

class FeedbackRequest(BaseModel):
    user_id: int
    cocktail_id: int

class OrderStatusRequest(BaseModel):
    status: str

class InventoryUpsertRequest(BaseModel):
    name: str
    quantity: float
    unit: str | None = None
    mode: str = "set"
    category: str | None = None

class InventoryRemoveRequest(BaseModel):
    name: str

class CocktailCreateRequest(BaseModel):
    name: str
    ingredients: str
    garnish: str | None = None
    instructions: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/onboard")
def onboard(request: OnboardRequest):
    onboard_user(request.user_id, request.name, request.preferences)
    return {"status": "ok"}

@app.post("/recommend")
def get_recommendations(request: RecommendRequest):
    try:
        results = recommend(request.user_id, request.top_k, request.exclude_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"recommendations": results}

@app.post("/recommend/session")
def get_session_recommendations(request: SessionRecommendRequest):
    results = recommend_from_text(request.preferences, request.top_k, request.exclude_ids)
    return {"recommendations": results}

@app.post("/order")
def order(request: OrderRequest, background_tasks: BackgroundTasks):
    try:
        result = place_order(request.user_id, request.cocktail_id, request.preferences)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    background_tasks.add_task(update_profile_from_order_placement, request.user_id, request.cocktail_id, request.preferences)
    return result

@app.post("/feedback")
def feedback(request: FeedbackRequest):
    try:
        log_feedback(request.user_id, request.cocktail_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}

@app.get("/orders/recent")
def recent_orders(limit: int = 20, status: str | None = None, date: str | None = None):
    statuses = status.split(",") if status else None
    return {"orders": list_recent_orders(limit, statuses, date)}

@app.post("/orders/{order_id}/status")
def set_order_status(order_id: int, request: OrderStatusRequest):
    update_order_status(order_id, request.status)
    return {"status": "ok"}

@app.post("/orders/{order_id}/adapt")
def adapt_order(order_id: int):
    try:
        return adapt_order_recipe(order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/cocktails/summary")
def get_cocktail_summary():
    return cocktail_summary()

@app.get("/users/recent")
def get_recent_users(limit: int = 10):
    return {"users": list_recent_users(limit)}

@app.get("/users/{user_id}")
def get_user_endpoint(user_id: int):
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/inventory")
def get_inventory(category: str | None = None):
    return {"inventory": list_inventory(category)}

@app.get("/inventory/categories")
def get_inventory_categories():
    return {"categories": inventory_categories_summary()}

@app.post("/inventory")
def upsert_inventory(request: InventoryUpsertRequest):
    try:
        upsert_ingredient(request.name, request.quantity, request.unit, request.mode, request.category)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}

@app.post("/inventory/remove")
def remove_inventory(request: InventoryRemoveRequest):
    try:
        remove_ingredient(request.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}

@app.get("/users/{user_id}/orders")
def get_user_orders(user_id: int, limit: int = 5):
    return {"orders": list_orders_for_user(user_id, limit)}

@app.get("/users/{user_id}/popular")
def get_user_popular_cocktails(user_id: int, limit: int = 3):
    return {"cocktails": popular_cocktails_for_user(user_id, limit)}

@app.get("/cocktails/by-category")
def get_cocktails_by_category(category: str):
    return {"cocktails": cocktails_in_category(category)}

@app.post("/users/{user_id}/clear-preferences")
def clear_user_preferences(user_id: int):
    try:
        clear_preferences(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}

@app.post("/cocktails")
def add_cocktail(request: CocktailCreateRequest):
    cocktail_id = create_cocktail(request.name, request.ingredients, request.garnish, request.instructions)
    return {"cocktail_id": cocktail_id, "name": request.name}