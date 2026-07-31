import html
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.bot.api_client import (
    recent_orders, update_order_status, cocktail_summary, recent_users,
    list_inventory, upsert_inventory_item, remove_inventory_item, adapt_order,
    user_orders, user_popular_cocktails, clear_user_preferences, get_user, inventory_categories,
    cocktails_by_category, place_order, create_cocktail
)
from services.bot.keyboards import (
    admin_reply_keyboard, order_status_keyboard, inventory_action_keyboard, inventory_list_keyboard,
    category_picker_keyboard, guest_summary_keyboard, guest_detail_keyboard, manual_order_preferences_keyboard,
    history_nav_keyboard, cocktail_confirm_keyboard,
    ADMIN_BUTTON_ORDERS, ADMIN_BUTTON_HISTORY, ADMIN_BUTTON_COCKTAILS, ADMIN_BUTTON_USERS,
    ADMIN_BUTTON_INVENTORY, ADMIN_BUTTON_MANUAL_ORDER
)
from services.bot import inventory_llm, cocktail_intake
from services import inventory_categorize
from services.format_recipe import format_ingredients_list

MENU_TEXT = "Use the buttons below to manage the bar."
STATUS_LABELS = {
    "pending": "🕐 Pending",
    "in_progress": "▶️ In progress",
    "completed": "✓ Completed",
    "cancelled": "✕ Cancelled"
}

async def _reply(context: ContextTypes.DEFAULT_TYPE, sendable, text, **kwargs):
    """Send a reply and track it as a menu message, so a later main-menu tap can sweep it away."""
    message = await sendable.reply_text(text, **kwargs)
    context.user_data.setdefault("menu_message_ids", []).append(message.message_id)
    return message

async def _clear_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete every message tracked since the last main-menu view, so each menu button starts with a clean sheet."""
    message_ids = context.user_data.pop("menu_message_ids", [])
    chat_id = update.effective_chat.id
    for message_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _clear_menu(update, context)
    await _reply(
        context, update.message,
        f"Hey, admin bot here. Your chat id is {update.effective_chat.id} — set it as ADMIN_CHAT_ID if you haven't already.\n\n{MENU_TEXT}",
        reply_markup=admin_reply_keyboard()
    )

def _order_text(o, include_status):
    guest_name = html.escape(o["guest_name"])
    text = f"#{o['order_id']} <b>{o['cocktail']}</b> for {guest_name}"
    if o.get("story"):
        text += f"\n<i>{o['story']}</i>"
    if o.get("ingredients"):
        text += f"\n<b>Ingredients</b>\n{o['ingredients']}"
    if o.get("garnish"):
        text += f"\n<b>Garnish</b>\n{o['garnish']}"
    if o.get("instructions"):
        text += f"\n<b>Instructions</b>\n{o['instructions']}"
    if o["preferences"]:
        text += f"\n<b>Preferences</b>\n{html.escape(o['preferences'])}"
    if o.get("adjustments"):
        text += f"\n<i>Adjusted: {o['adjustments']}</i>"
    if include_status:
        text += f"\nStatus: {STATUS_LABELS.get(o['status'], o['status'])}"
    return text

async def _send_orders(sendable, context, orders, empty_message, include_status):
    if not orders:
        return await _reply(context, sendable, empty_message, reply_markup=admin_reply_keyboard())

    await _reply(context, sendable, f"{len(orders)} order(s):", reply_markup=admin_reply_keyboard())

    last_message = None
    for o in orders:
        reply_markup = None if include_status else order_status_keyboard(o["order_id"], o["status"])
        last_message = await _reply(context, sendable, _order_text(o, include_status), reply_markup=reply_markup, parse_mode="HTML")
    return last_message

def _cocktails_text():
    summary = cocktail_summary()
    category_lines = [f"- {c['category']}: {c['count']}" for c in summary["categories"] if c["category"]]
    return f"{summary['count']} cocktails loaded.\n" + "\n".join(category_lines)

def _guest_summary_text(user, orders, popular):
    lines = [user["name"], "", "Last orders:"]
    if orders:
        lines += [f"- #{o['order_id']} {o['cocktail']} ({o['status']})" for o in orders]
    else:
        lines.append("- none yet")

    lines.append("\nTop cocktails:")
    if popular:
        lines += [f"- {c['name']} ({c['order_count']} orders)" for c in popular]
    else:
        lines.append("- none yet")

    return "\n".join(lines)

def _items_for_category(category):
    if category == "Uncategorized":
        return [i for i in list_inventory() if not i.get("category")]
    return list_inventory(category)

def _inventory_text():
    summary = inventory_categories()
    if not summary:
        return "No ingredients tracked yet."

    lines = []
    for c in summary:
        items = _items_for_category(c["category"])
        if not items:
            continue
        lines.append(f"\n<b>{c['category']}</b>")
        for i in items:
            if i["unit"] == "count":
                lines.append(f"- {i['name']}: {i['quantity']}")
            else:
                lines.append(f"- {i['name']}: {i['quantity']} {i['unit']}")

    text = "\n".join(lines).strip()
    return text or "No ingredients tracked yet."

def _parse_ingredient_names(text):
    return [line.strip() for line in text.splitlines() if line.strip()]

async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    await _clear_menu(update, context)
    orders = recent_orders(limit=20, statuses=["pending", "in_progress"])
    await _send_orders(update.message, context, orders, "No active orders.", include_status=False)

async def _show_history_day(sendable, context, day: date):
    day_str = day.isoformat()
    is_today = day == date.today()
    label = "Today" if is_today else day_str

    orders = recent_orders(limit=50, statuses=["completed", "cancelled"], date=day_str)
    last_message = await _send_orders(sendable, context, orders, f"No past orders on {label}.", include_status=True)

    prev_date = day - timedelta(days=1)
    next_date = None if is_today else day + timedelta(days=1)
    await last_message.edit_reply_markup(reply_markup=history_nav_keyboard(prev_date, next_date))

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    await _clear_menu(update, context)
    await _show_history_day(update.message, context, date.today())

async def handle_history_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _clear_menu(update, context)
    day = date.fromisoformat(query.data.split(":", 1)[1])
    await _show_history_day(query.message, context, day)

ADD_COCKTAIL_BUTTON_ROW = [[InlineKeyboardButton("➕ Add cocktail", callback_data="cocktailadd")]]
BACK_TO_CATEGORIES_ROW = [[InlineKeyboardButton("◀ Back to categories", callback_data="cocktailcatlist")]]

def _cocktail_category_content():
    categories = cocktail_summary()["categories"]
    keyboard = category_picker_keyboard(categories, pick_prefix="cocktailcat", extra_rows=ADD_COCKTAIL_BUTTON_ROW)
    return "Browse by category:", keyboard

async def cmd_cocktails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    context.user_data.pop("cocktail_intake_history", None)
    context.user_data.pop("cocktail_intake_turns", None)
    context.user_data.pop("cocktail_draft", None)
    await _clear_menu(update, context)
    await _reply(context, update.message, _cocktails_text(), reply_markup=admin_reply_keyboard())
    text, keyboard = _cocktail_category_content()
    await _reply(context, update.message, text, reply_markup=keyboard)

async def handle_cocktail_category_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]
    cocktails = cocktails_by_category(category)
    items = [{"id": c["id"], "name": c["name"]} for c in cocktails]
    keyboard = inventory_list_keyboard(items, pick_prefix="cocktailview", page_prefix=f"cocktailpage:{category}", extra_rows=BACK_TO_CATEGORIES_ROW)
    await query.edit_message_text(f"{category}:", reply_markup=keyboard)

async def handle_cocktail_category_list_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, keyboard = _cocktail_category_content()
    await query.edit_message_text(text, reply_markup=keyboard)

async def handle_cocktail_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category, page = query.data.split(":")
    page = int(page)
    cocktails = cocktails_by_category(category)
    items = [{"id": c["id"], "name": c["name"]} for c in cocktails]
    keyboard = inventory_list_keyboard(items, page, pick_prefix="cocktailview", page_prefix=f"cocktailpage:{category}", extra_rows=BACK_TO_CATEGORIES_ROW)
    await query.edit_message_reply_markup(reply_markup=keyboard)

async def handle_cocktail_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Just acknowledges the tap for now — no recipe detail view yet.
    query = update.callback_query
    await query.answer()

async def handle_cocktail_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "cocktail_intake"
    context.user_data["cocktail_intake_history"] = []
    context.user_data["cocktail_intake_turns"] = 0
    await _reply(
        context, query.message,
        "Paste the recipe — name, ingredients, garnish, instructions, whatever you've got. "
        "I'll ask if anything's missing."
    )

def _cocktail_draft_text(draft):
    lines = [f"New cocktail: {draft.name}", f"\nIngredients:\n{draft.ingredients}"]
    if draft.garnish:
        lines.append(f"\nGarnish: {draft.garnish}")
    lines.append(f"\nInstructions:\n{draft.instructions}")
    lines.append("\nSave this recipe?")
    return "\n".join(lines)

async def _handle_cocktail_intake_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = context.user_data.get("cocktail_intake_history", [])
    turns = context.user_data.get("cocktail_intake_turns", 0)
    force_finish = turns >= cocktail_intake.MAX_TURNS

    try:
        result, history = cocktail_intake.next_turn(history, update.message.text, force_finish=force_finish)
    except Exception as e:
        context.user_data.pop("awaiting", None)
        context.user_data.pop("cocktail_intake_history", None)
        context.user_data.pop("cocktail_intake_turns", None)
        await _reply(context, update.message, f"Couldn't process that recipe: {e}", reply_markup=admin_reply_keyboard())
        return

    if result["type"] == "question":
        context.user_data["cocktail_intake_history"] = history
        context.user_data["cocktail_intake_turns"] = turns + 1
        await _reply(context, update.message, result["question"])
        return

    context.user_data.pop("awaiting", None)
    context.user_data.pop("cocktail_intake_history", None)
    context.user_data.pop("cocktail_intake_turns", None)
    context.user_data["cocktail_draft"] = result["cocktail"]
    await _reply(context, update.message, _cocktail_draft_text(result["cocktail"]), reply_markup=cocktail_confirm_keyboard())

async def handle_cocktail_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.pop("cocktail_draft", None)
    if draft is None:
        await query.edit_message_text("Lost track of that recipe — please start over with Add cocktail.")
        return
    try:
        create_cocktail(draft.name, draft.ingredients, draft.garnish, draft.instructions)
        await query.edit_message_text(f"Added \"{draft.name}\" to the catalog.")
    except Exception as e:
        await query.edit_message_text(f"Couldn't save: {e}")

async def handle_cocktail_discard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("cocktail_draft", None)
    await query.edit_message_text("Discarded.")

def _guest_list_content():
    users = recent_users(limit=100)
    items = [{"id": u["user_id"], "name": f"{u['name']} ({u['user_id']})"} for u in users]
    if not items:
        return "No guests onboarded yet.", None
    keyboard = inventory_list_keyboard(items, pick_prefix="guestpick", page_prefix="guestpage")
    return "Select a guest:", keyboard

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    await _clear_menu(update, context)
    await _reply(context, update.message, "👥 Users", reply_markup=admin_reply_keyboard())
    text, keyboard = _guest_list_content()
    await _reply(context, update.message, text, reply_markup=keyboard)

async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    await _clear_menu(update, context)
    await _reply(context, update.message, "📦 Inventory", reply_markup=admin_reply_keyboard())
    await _reply(context, update.message, "What would you like to do?", reply_markup=inventory_action_keyboard())

async def cmd_manual_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    context.user_data.pop("manual_order_guest_id", None)
    context.user_data.pop("manual_order_cocktail_id", None)
    await _clear_menu(update, context)
    await _reply(context, update.message, "🧾 New order", reply_markup=admin_reply_keyboard())
    users = recent_users(limit=100)
    items = [{"id": u["user_id"], "name": f"{u['name']} ({u['user_id']})"} for u in users]
    if not items:
        await _reply(context, update.message, "No guests onboarded yet.")
        return
    keyboard = inventory_list_keyboard(items, pick_prefix="manordguest", page_prefix="manordguestpage")
    await _reply(context, update.message, "Who's this order for?", reply_markup=keyboard)

BUTTON_HANDLERS = {
    ADMIN_BUTTON_ORDERS: cmd_orders,
    ADMIN_BUTTON_HISTORY: cmd_history,
    ADMIN_BUTTON_COCKTAILS: cmd_cocktails,
    ADMIN_BUTTON_USERS: cmd_users,
    ADMIN_BUTTON_INVENTORY: cmd_inventory,
    ADMIN_BUTTON_MANUAL_ORDER: cmd_manual_order,
}

ADD_NEW_BUTTON_ROW = [[InlineKeyboardButton("➕ Add new ingredient", callback_data="invaddnew")]]

async def handle_inventory_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "view":
        await _reply(context, query.message, _inventory_text(), parse_mode="HTML")
    elif action == "update":
        context.user_data["awaiting"] = "inventory_update"
        text = (
            "Send a stock update as free text, e.g. \"2 bottles of vodka\" or \"500ml fresh lime juice\" "
            "to set an amount, or \"add 2L of orange juice\" to top up existing stock.\n\n"
            "Or pick a category below to browse and update a specific ingredient, or add a brand new one:"
        )
        keyboard = category_picker_keyboard(inventory_categories(), pick_prefix="invcat", extra_rows=ADD_NEW_BUTTON_ROW)
        await _reply(context, query.message, text, reply_markup=keyboard)
    elif action == "remove":
        context.user_data["awaiting"] = "inventory_remove"
        categories = inventory_categories()
        text = "Send the name(s) to remove, one per line, or pick a category below to browse:"
        keyboard = category_picker_keyboard(categories, pick_prefix="invrmcat") if categories else None
        await _reply(context, query.message, text, reply_markup=keyboard)

async def handle_inventory_add_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "inventory_update"
    await _reply(
        context, query.message,
        "What ingredient and how much? e.g. \"2 bottles of vodka\" or \"500ml fresh lime juice\"."
    )

async def handle_inventory_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ingredient_id = int(query.data.split(":")[1])

    items = list_inventory()
    match = next((i for i in items if i["id"] == ingredient_id), None)
    if match is None:
        await _reply(context, query.message, "That ingredient isn't in the list anymore.")
        return

    context.user_data["awaiting"] = "inventory_update_single"
    context.user_data["pending_ingredient"] = match["name"]
    await _reply(context, query.message, f"What's the new amount for {match['name']}?")

async def handle_inventory_category_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]
    items = _items_for_category(category)
    keyboard = inventory_list_keyboard(items, pick_prefix="invpick", page_prefix=f"invpage:{category}", extra_rows=ADD_NEW_BUTTON_ROW)
    await _reply(context, query.message, f"{category}:", reply_markup=keyboard)

async def handle_inventory_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category, page = query.data.split(":")
    page = int(page)
    items = _items_for_category(category)
    keyboard = inventory_list_keyboard(items, page, pick_prefix="invpick", page_prefix=f"invpage:{category}", extra_rows=ADD_NEW_BUTTON_ROW)
    await query.edit_message_reply_markup(reply_markup=keyboard)

async def handle_inventory_remove_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ingredient_id = int(query.data.split(":")[1])

    items = list_inventory()
    match = next((i for i in items if i["id"] == ingredient_id), None)
    if match is None:
        await _reply(context, query.message, "That ingredient isn't in the list anymore.")
        return

    try:
        remove_inventory_item(match["name"])
        await _reply(context, query.message, f"Removed {match['name']}.")
    except Exception as e:
        await _reply(context, query.message, f"Couldn't remove {match['name']}: {e}")

async def handle_inventory_remove_category_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]
    items = _items_for_category(category)
    keyboard = inventory_list_keyboard(items, pick_prefix="invrmpick", page_prefix=f"invrmpage:{category}")
    await _reply(context, query.message, f"{category}:", reply_markup=keyboard)

async def handle_inventory_remove_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category, page = query.data.split(":")
    page = int(page)
    items = _items_for_category(category)
    keyboard = inventory_list_keyboard(items, page, pick_prefix="invrmpick", page_prefix=f"invrmpage:{category}")
    await query.edit_message_reply_markup(reply_markup=keyboard)

def _format_update_line(name, quantity, unit, note=None, mode="set"):
    amount = f"+{quantity}" if mode == "add" else f"-{quantity}" if mode == "subtract" else str(quantity)
    line = f"{name}: {amount} {unit}"
    if note:
        line += f" ({note})"
    return line

def _resolve_category(name, existing_items):
    match = next((i for i in existing_items if i["name"].lower() == name.lower()), None)
    if match and match.get("category"):
        return match["category"]
    try:
        return inventory_categorize.categorize_ingredient(name)
    except Exception:
        return None

async def _handle_inventory_update_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)

    try:
        parsed = inventory_llm.parse_inventory_updates(update.message.text)
    except Exception as e:
        await _reply(context, update.message, f"Couldn't understand that update: {e}", reply_markup=admin_reply_keyboard())
        return

    existing_items = list_inventory()
    saved_lines = []
    failed_lines = []
    for item in parsed:
        try:
            mode = item.mode or "set"
            category = _resolve_category(item.name, existing_items)
            upsert_inventory_item(item.name, item.quantity, item.unit, mode, category)
            saved_lines.append(_format_update_line(item.name, item.quantity, item.unit, item.note, mode))
        except Exception:
            failed_lines.append(item.name)

    lines = [f"Updated {len(saved_lines)} ingredient(s):"] + [f"- {l}" for l in saved_lines]
    if failed_lines:
        lines.append("Couldn't save: " + ", ".join(failed_lines))
    await _reply(context, update.message, "\n".join(lines), reply_markup=admin_reply_keyboard())

async def _handle_inventory_update_single_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    name = context.user_data.pop("pending_ingredient", None)
    if not name:
        return

    try:
        parsed = inventory_llm.parse_quantity(name, update.message.text)
        mode = parsed.mode or "set"
        category = _resolve_category(name, list_inventory())
        upsert_inventory_item(name, parsed.quantity, parsed.unit, mode, category)
        await _reply(
            context, update.message,
            "Updated " + _format_update_line(name, parsed.quantity, parsed.unit, parsed.note, mode),
            reply_markup=admin_reply_keyboard()
        )
    except Exception as e:
        await _reply(context, update.message, f"Couldn't update {name}: {e}", reply_markup=admin_reply_keyboard())

async def _handle_inventory_remove_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    names = _parse_ingredient_names(update.message.text)

    removed = []
    not_found = []
    for name in names:
        try:
            remove_inventory_item(name)
            removed.append(name)
        except Exception:
            not_found.append(name)

    lines = []
    if removed:
        lines.append(f"Removed {len(removed)}: " + ", ".join(removed))
    if not_found:
        lines.append("Not found: " + ", ".join(not_found))
    if not lines:
        lines.append("Nothing to remove.")
    await _reply(context, update.message, "\n".join(lines), reply_markup=admin_reply_keyboard())

async def handle_guest_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[1])
    users = recent_users(limit=100)
    items = [{"id": u["user_id"], "name": f"{u['name']} ({u['user_id']})"} for u in users]
    keyboard = inventory_list_keyboard(items, page, pick_prefix="guestpick", page_prefix="guestpage")
    await query.edit_message_reply_markup(reply_markup=keyboard)

async def handle_guest_list_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, keyboard = _guest_list_content()
    await query.edit_message_text(text, reply_markup=keyboard)

async def handle_guest_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split(":")[1])
    user = get_user(user_id)
    if user is None:
        await query.edit_message_text("That guest isn't in the list anymore.")
        return
    orders = user_orders(user_id, limit=5)
    popular = user_popular_cocktails(user_id, limit=3)
    text = _guest_summary_text(user, orders, popular)
    await query.edit_message_text(text, reply_markup=guest_summary_keyboard(user_id))

async def handle_guest_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split(":")[1])
    user = get_user(user_id)
    if user is None:
        await query.edit_message_text("That guest isn't in the list anymore.")
        return
    text = f"{user['name']}\nPreferences: {user['preferences'] or '(none)'}"
    await query.edit_message_text(text, reply_markup=guest_detail_keyboard(user_id))

async def handle_guest_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split(":")[1])
    try:
        clear_user_preferences(user_id)
        user = get_user(user_id)
        name = user["name"] if user else "that guest"
        await query.edit_message_text(f"{name}\nPreferences: (none)", reply_markup=guest_detail_keyboard(user_id))
    except Exception as e:
        await query.edit_message_text(f"Couldn't clear preferences: {e}", reply_markup=guest_detail_keyboard(user_id))

async def handle_manual_order_guest_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split(":")[1])
    context.user_data["manual_order_guest_id"] = user_id
    categories = cocktail_summary()["categories"]
    keyboard = category_picker_keyboard(categories, pick_prefix="manordcat")
    await _reply(context, query.message, "Which category?", reply_markup=keyboard)

async def handle_manual_order_guest_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[1])
    users = recent_users(limit=100)
    items = [{"id": u["user_id"], "name": f"{u['name']} ({u['user_id']})"} for u in users]
    keyboard = inventory_list_keyboard(items, page, pick_prefix="manordguest", page_prefix="manordguestpage")
    await query.edit_message_reply_markup(reply_markup=keyboard)

async def handle_manual_order_category_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]
    cocktails = cocktails_by_category(category)
    items = [{"id": c["id"], "name": c["name"]} for c in cocktails]
    keyboard = inventory_list_keyboard(items, pick_prefix="manordpick", page_prefix=f"manordpage:{category}")
    await _reply(context, query.message, f"{category}:", reply_markup=keyboard)

async def handle_manual_order_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category, page = query.data.split(":")
    page = int(page)
    cocktails = cocktails_by_category(category)
    items = [{"id": c["id"], "name": c["name"]} for c in cocktails]
    keyboard = inventory_list_keyboard(items, page, pick_prefix="manordpick", page_prefix=f"manordpage:{category}")
    await query.edit_message_reply_markup(reply_markup=keyboard)

async def handle_manual_order_cocktail_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cocktail_id = int(query.data.split(":")[1])
    context.user_data["manual_order_cocktail_id"] = cocktail_id
    await _reply(
        context, query.message,
        "Any preferences for this order?",
        reply_markup=manual_order_preferences_keyboard(cocktail_id)
    )

async def _place_manual_order(update_or_query, context, cocktail_id, preferences):
    guest_id = context.user_data.pop("manual_order_guest_id", None)
    context.user_data.pop("manual_order_cocktail_id", None)
    if guest_id is None:
        await _reply(context, update_or_query.message, "Lost track of who this order was for — please start over with New order.")
        return
    try:
        result = place_order(guest_id, cocktail_id, preferences)
        await _reply(context, update_or_query.message, f"Order placed: {result['cocktail']}.")
    except Exception as e:
        await _reply(context, update_or_query.message, f"Couldn't place order: {e}")

async def handle_manual_order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cocktail_id = int(query.data.split(":")[1])
    await _place_manual_order(query, context, cocktail_id, None)

async def handle_manual_order_writeprefs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cocktail_id = int(query.data.split(":")[1])
    context.user_data["awaiting"] = "manual_order_preferences"
    context.user_data["manual_order_cocktail_id"] = cocktail_id
    await _reply(context, query.message, "What preferences should I note for this order?")

async def _handle_manual_order_preferences_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    cocktail_id = context.user_data.get("manual_order_cocktail_id")
    if cocktail_id is None:
        await _reply(context, update.message, "Lost track of that order — please start over with New order.", reply_markup=admin_reply_keyboard())
        return
    await _place_manual_order(update, context, cocktail_id, update.message.text)
    await _reply(context, update.message, MENU_TEXT, reply_markup=admin_reply_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handler = BUTTON_HANDLERS.get(update.message.text)
    if handler:
        await handler(update, context)
        return

    awaiting = context.user_data.get("awaiting")

    if awaiting == "inventory_update":
        await _handle_inventory_update_text(update, context)
    elif awaiting == "inventory_update_single":
        await _handle_inventory_update_single_text(update, context)
    elif awaiting == "inventory_remove":
        await _handle_inventory_remove_text(update, context)
    elif awaiting == "manual_order_preferences":
        await _handle_manual_order_preferences_text(update, context)
    elif awaiting == "cocktail_intake":
        await _handle_cocktail_intake_text(update, context)

async def handle_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, status, order_id = query.data.split(":")
    order_id = int(order_id)

    update_order_status(order_id, status)

    if status in ("completed", "cancelled"):
        try:
            await query.message.delete()
            return
        except Exception:
            pass  # fall through to editing with a status line if deletion isn't possible

    base_text = query.message.text.split("\nStatus:")[0]
    new_text = f"{base_text}\nStatus: {STATUS_LABELS.get(status, status)}"
    reply_markup = None if status in ("completed", "cancelled") else order_status_keyboard(order_id, status)
    await query.edit_message_text(new_text, reply_markup=reply_markup, parse_mode="HTML")

async def handle_adapt_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])

    try:
        result = adapt_order(order_id)
    except Exception as e:
        await query.message.reply_text(f"Couldn't adapt recipe: {e}")
        return

    if not result["missing"]:
        await query.message.reply_text(f"{result['cocktail']} is fully in stock — no substitution needed.")
        return

    text = (
        f"🔄 Adapted {result['cocktail']} (missing: {', '.join(result['missing'])}):\n"
        f"{format_ingredients_list(result['adapted_ingredients'])}\n\n{result['changes']}"
    )
    await query.message.reply_text(text)
