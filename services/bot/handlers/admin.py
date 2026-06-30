from telegram import Update
from telegram.ext import ContextTypes
from services.bot.api_client import recent_orders, update_order_status, cocktail_summary, recent_users
from services.bot.keyboards import admin_menu_keyboard, order_status_keyboard

MENU_TEXT = "Choose an action:"
STATUS_LABELS = {
    "pending": "🕐 Pending",
    "in_progress": "▶️ In progress",
    "completed": "✓ Completed",
    "cancelled": "✕ Cancelled"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hey, admin bot here. Your chat id is {update.effective_chat.id} — set it as ADMIN_CHAT_ID if you haven't already.\n\n{MENU_TEXT}",
        reply_markup=admin_menu_keyboard()
    )

def _order_text(o, include_status):
    text = f"#{o['order_id']} {o['cocktail']} for {o['guest_name']}"
    if o["preferences"]:
        text += f"\nPreferences: {o['preferences']}"
    if include_status:
        text += f"\nStatus: {STATUS_LABELS.get(o['status'], o['status'])}"
    return text

async def _send_orders_one_by_one(query, orders, empty_message, include_status):
    if not orders:
        await query.edit_message_text(empty_message, reply_markup=admin_menu_keyboard())
        return

    await query.edit_message_text(f"{len(orders)} order(s):")

    for o in orders:
        reply_markup = None if include_status else order_status_keyboard(o["order_id"], o["status"])
        await query.message.reply_text(_order_text(o, include_status), reply_markup=reply_markup)

    await query.message.reply_text(MENU_TEXT, reply_markup=admin_menu_keyboard())

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "orders":
        orders = recent_orders(limit=20, statuses=["pending", "in_progress"])
        await _send_orders_one_by_one(query, orders, "No active orders.", include_status=False)
        return
    elif action == "history":
        orders = recent_orders(limit=20, statuses=["completed", "cancelled"])
        await _send_orders_one_by_one(query, orders, "No past orders yet.", include_status=True)
        return
    elif action == "cocktails":
        summary = cocktail_summary()
        category_lines = [f"- {c['category']}: {c['count']}" for c in summary["categories"] if c["category"]]
        text = f"{summary['count']} cocktails loaded.\n" + "\n".join(category_lines)
    elif action == "users":
        users = recent_users(limit=10)
        if not users:
            text = "No guests onboarded yet."
        else:
            text = "\n".join(f"{u['user_id']} {u['name']} — {u['preferences']}" for u in users)
    elif action in ("refresh", "back"):
        await query.edit_message_text(MENU_TEXT, reply_markup=admin_menu_keyboard())
        return
    else:
        text = "Unknown action."

    await query.edit_message_text(text, reply_markup=admin_menu_keyboard())

async def handle_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, status, order_id = query.data.split(":")
    order_id = int(order_id)

    update_order_status(order_id, status)

    base_text = query.message.text.split("\n\nStatus:")[0]
    new_text = f"{base_text}\n\nStatus: {STATUS_LABELS.get(status, status)}"
    await query.edit_message_text(new_text, reply_markup=order_status_keyboard(order_id, status))
