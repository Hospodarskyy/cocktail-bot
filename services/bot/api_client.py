import os
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def onboard(user_id, name, preferences):
    response = requests.post(f"{API_BASE_URL}/onboard", json={
        "user_id": user_id,
        "name": name,
        "preferences": preferences
    })
    response.raise_for_status()
    return response.json()

def recommend(user_id, top_k=5):
    response = requests.post(f"{API_BASE_URL}/recommend", json={
        "user_id": user_id,
        "top_k": top_k
    })
    response.raise_for_status()
    return response.json()["recommendations"]

def place_order(user_id, cocktail_id, preferences=None):
    response = requests.post(f"{API_BASE_URL}/order", json={
        "user_id": user_id,
        "cocktail_id": cocktail_id,
        "preferences": preferences
    })
    response.raise_for_status()
    return response.json()

def send_feedback(user_id, cocktail_id):
    response = requests.post(f"{API_BASE_URL}/feedback", json={
        "user_id": user_id,
        "cocktail_id": cocktail_id
    })
    response.raise_for_status()
    return response.json()

def recent_orders(limit=20, statuses=None):
    params = {"limit": limit}
    if statuses:
        params["status"] = ",".join(statuses)
    response = requests.get(f"{API_BASE_URL}/orders/recent", params=params)
    response.raise_for_status()
    return response.json()["orders"]

def update_order_status(order_id, status):
    response = requests.post(f"{API_BASE_URL}/orders/{order_id}/status", json={"status": status})
    response.raise_for_status()
    return response.json()

def cocktail_summary():
    response = requests.get(f"{API_BASE_URL}/cocktails/summary")
    response.raise_for_status()
    return response.json()

def recent_users(limit=10):
    response = requests.get(f"{API_BASE_URL}/users/recent", params={"limit": limit})
    response.raise_for_status()
    return response.json()["users"]
