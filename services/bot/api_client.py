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

def recommend(user_id, top_k=5, exclude_ids=None):
    payload = {"user_id": user_id, "top_k": top_k}
    if exclude_ids:
        payload["exclude_ids"] = list(exclude_ids)
    response = requests.post(f"{API_BASE_URL}/recommend", json=payload)
    response.raise_for_status()
    return response.json()["recommendations"]

def recommend_session(preferences, top_k=5, exclude_ids=None):
    payload = {"preferences": preferences, "top_k": top_k}
    if exclude_ids:
        payload["exclude_ids"] = list(exclude_ids)
    response = requests.post(f"{API_BASE_URL}/recommend/session", json=payload)
    response.raise_for_status()
    return response.json()["recommendations"]

def get_user(user_id):
    response = requests.get(f"{API_BASE_URL}/users/{user_id}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

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

def recent_orders(limit=20, statuses=None, date=None):
    params = {"limit": limit}
    if statuses:
        params["status"] = ",".join(statuses)
    if date:
        params["date"] = date
    response = requests.get(f"{API_BASE_URL}/orders/recent", params=params)
    response.raise_for_status()
    return response.json()["orders"]

def update_order_status(order_id, status):
    response = requests.post(f"{API_BASE_URL}/orders/{order_id}/status", json={"status": status})
    response.raise_for_status()
    return response.json()

def adapt_order(order_id):
    response = requests.post(f"{API_BASE_URL}/orders/{order_id}/adapt")
    response.raise_for_status()
    return response.json()

def cocktail_summary():
    response = requests.get(f"{API_BASE_URL}/cocktails/summary")
    response.raise_for_status()
    return response.json()

def user_orders(user_id, limit=5):
    response = requests.get(f"{API_BASE_URL}/users/{user_id}/orders", params={"limit": limit})
    response.raise_for_status()
    return response.json()["orders"]

def user_popular_cocktails(user_id, limit=3):
    response = requests.get(f"{API_BASE_URL}/users/{user_id}/popular", params={"limit": limit})
    response.raise_for_status()
    return response.json()["cocktails"]

def cocktails_by_category(category):
    response = requests.get(f"{API_BASE_URL}/cocktails/by-category", params={"category": category})
    response.raise_for_status()
    return response.json()["cocktails"]

def recent_users(limit=10):
    response = requests.get(f"{API_BASE_URL}/users/recent", params={"limit": limit})
    response.raise_for_status()
    return response.json()["users"]

def clear_user_preferences(user_id):
    response = requests.post(f"{API_BASE_URL}/users/{user_id}/clear-preferences")
    response.raise_for_status()
    return response.json()

def list_inventory(category=None):
    params = {"category": category} if category else {}
    response = requests.get(f"{API_BASE_URL}/inventory", params=params)
    response.raise_for_status()
    return response.json()["inventory"]

def inventory_categories():
    response = requests.get(f"{API_BASE_URL}/inventory/categories")
    response.raise_for_status()
    return response.json()["categories"]

def upsert_inventory_item(name, quantity, unit=None, mode="set", category=None):
    response = requests.post(f"{API_BASE_URL}/inventory", json={
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "mode": mode,
        "category": category
    })
    response.raise_for_status()
    return response.json()

def remove_inventory_item(name):
    response = requests.post(f"{API_BASE_URL}/inventory/remove", json={"name": name})
    response.raise_for_status()
    return response.json()

def create_cocktail(name, ingredients, garnish, instructions):
    response = requests.post(f"{API_BASE_URL}/cocktails", json={
        "name": name,
        "ingredients": ingredients,
        "garnish": garnish,
        "instructions": instructions
    })
    response.raise_for_status()
    return response.json()
