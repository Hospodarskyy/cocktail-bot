from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from services.recommender import recommend
from services.db import init_db
from services.db import init_db, get_connection
from services.data_loader import load_hotaling_data
from services.embedder import generate_embeddings

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

class RecommendRequest(BaseModel):
    preferences: str
    top_k: int = 5

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/recommend")
def get_recommendations(request: RecommendRequest):
    results = recommend(request.preferences, request.top_k)
    return {"recommendations": results}