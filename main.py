from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.recommender import recommend, cocktail_summary
from services.db import init_db, get_connection
from services.data_loader import load_hotaling_data
from services.embedder import generate_embeddings
from services.users import onboard_user, list_recent_users
from services.orders import place_order, list_recent_orders, update_order_status
from services.feedback import log_feedback

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
        load_hotaling_data("data/cocktail-dataset.csv")
        generate_embeddings()
    
    yield

app = FastAPI(title="Cocktail Recommender API", lifespan=lifespan)

class OnboardRequest(BaseModel):
    user_id: int
    name: str
    preferences: str

class RecommendRequest(BaseModel):
    user_id: int
    top_k: int = 5

class OrderRequest(BaseModel):
    user_id: int
    cocktail_id: int
    preferences: str | None = None

class FeedbackRequest(BaseModel):
    user_id: int
    cocktail_id: int

class OrderStatusRequest(BaseModel):
    status: str

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
        results = recommend(request.user_id, request.top_k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"recommendations": results}

@app.post("/order")
def order(request: OrderRequest):
    try:
        return place_order(request.user_id, request.cocktail_id, request.preferences)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/feedback")
def feedback(request: FeedbackRequest):
    try:
        log_feedback(request.user_id, request.cocktail_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}

@app.get("/orders/recent")
def recent_orders(limit: int = 20, status: str | None = None):
    statuses = status.split(",") if status else None
    return {"orders": list_recent_orders(limit, statuses)}

@app.post("/orders/{order_id}/status")
def set_order_status(order_id: int, request: OrderStatusRequest):
    update_order_status(order_id, request.status)
    return {"status": "ok"}

@app.get("/cocktails/summary")
def get_cocktail_summary():
    return cocktail_summary()

@app.get("/users/recent")
def get_recent_users(limit: int = 10):
    return {"users": list_recent_users(limit)}