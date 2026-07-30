from telegram import Update
from telegram.ext import ContextTypes
from services.bot.api_client import onboard, recommend, recommend_session, place_order, send_feedback, get_user
from services.bot.keyboards import (
    cocktail_keyboard, order_preferences_keyboard, guest_reply_keyboard, qa_options_keyboard,
    GUEST_BUTTON_RECOMMEND, GUEST_BUTTON_QA, GUEST_BUTTON_FULLMENU
)
from services.bot import llm_openai as llm
from services.format_recipe import format_ingredients_list
from services.image_service import get_or_generate_image

MENU_TEXT = "What would you like to do?"
DEFAULT_PREFERENCES = "no strong preferences, open to suggestions"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(f"Welcome to the bar! {MENU_TEXT}", reply_markup=guest_reply_keyboard())

async def _confirm_order(reply_to):
    await reply_to("Order sent to the bar! 🍸 Anything else to order?")

async def _send_recommendations(reply_to, context, user_id, session_preferences=None):
    shown = context.user_data.setdefault("shown_cocktail_ids", set())
    if session_preferences:
        results = recommend_session(session_preferences, top_k=5, exclude_ids=list(shown))
    else:
        results = recommend(user_id, top_k=5, exclude_ids=list(shown))

    if not results:
        await reply_to("Sorry, nothing matches what's currently in stock — check back after a restock!")
        return

    # reply_to is a bound method (update.message.reply_text) — .__self__ gets
    # us back to the underlying Message object so we can also call
    # .reply_photo on it, without threading a second parameter through every
    # caller of _send_recommendations.
    message = reply_to.__self__

    for cocktail in results:
        shown.add(cocktail["id"])
        ingredients_text = format_ingredients_list(cocktail["ingredients"])
        image_url = get_or_generate_image(cocktail["id"], cocktail["name"], ingredients_text)
        await message.reply_photo(
            photo=image_url,
            caption=f"🍹 {cocktail['name']}",
            reply_markup=cocktail_keyboard(cocktail["id"]),
        )

async def handle_recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    user_id = update.effective_chat.id
    try:
        await _send_recommendations(update.message.reply_text, context, user_id)
    except Exception:
        name = update.effective_user.first_name
        onboard(user_id, name, DEFAULT_PREFERENCES)
        await _send_recommendations(update.message.reply_text, context, user_id)

async def _start_qa(reply_to, context, user_id, name, first_answer):
    context.user_data["qa_history"] = []
    context.user_data["qa_turns"] = 0
    context.user_data["awaiting"] = "qa"
    existing = get_user(user_id)
    context.user_data["known_preferences"] = existing["preferences"] if existing else None
    context.user_data["is_first_entry"] = existing is None
    await _ask_next_question(reply_to, context, user_id, name, first_answer)

async def handle_qa_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    name = update.effective_user.first_name
    await _start_qa(update.message.reply_text, context, user_id, name, first_answer=None)

async def handle_fullmenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)
    await update.message.reply_text("The full menu is coming soon!")

GUEST_BUTTON_HANDLERS = {
    GUEST_BUTTON_RECOMMEND: handle_recommend,
    GUEST_BUTTON_QA: handle_qa_start,
    GUEST_BUTTON_FULLMENU: handle_fullmenu,
}

async def _ask_next_question(reply_to, context, user_id, name, answer_text):
    force_finish = context.user_data["qa_turns"] >= llm.MAX_TURNS
    known_preferences = context.user_data.get("known_preferences")
    result, history = llm.next_turn(
        context.user_data["qa_history"], answer_text=answer_text, force_finish=force_finish,
        known_preferences=known_preferences
    )
    context.user_data["qa_history"] = history
    context.user_data["qa_turns"] += 1

    if result["type"] == "question":
        context.user_data["qa_options"] = result["options"]
        await reply_to(result["question"], reply_markup=qa_options_keyboard(result["options"]))
    else:
        is_first_entry = context.user_data.get("is_first_entry", True)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("qa_history", None)
        context.user_data.pop("qa_options", None)
        context.user_data.pop("known_preferences", None)
        context.user_data.pop("is_first_entry", None)
        summary = result["preferences_summary"]

        if is_first_entry:
            onboard(user_id, name, summary)
            await reply_to("Great, I've got a good sense of what you like!")
            await _send_recommendations(reply_to, context, user_id)
        else:
            await reply_to("Got it — here's what I'd suggest for right now!")
            await _send_recommendations(reply_to, context, user_id, session_preferences=summary)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, cocktail_id = query.data.split(":")
    cocktail_id = int(cocktail_id)
    user_id = update.effective_chat.id

    if action == "skip":
        send_feedback(user_id, cocktail_id)
        await query.message.reply_text("Got it, noted as not for you.")

    elif action == "order":
        await query.message.reply_text("Any preferences for this order?", reply_markup=order_preferences_keyboard(cocktail_id))

    elif action == "confirm":
        place_order(user_id, cocktail_id)
        await _confirm_order(query.message.reply_text)

    elif action == "writeprefs":
        context.user_data["awaiting"] = "order_preferences"
        context.user_data["pending_cocktail_id"] = cocktail_id
        await query.message.reply_text("Type your preferences (e.g. \"not too bitter\").")

async def handle_qa_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split(":")[1])
    answer_text = context.user_data["qa_options"][index]
    user_id = update.effective_chat.id
    name = update.effective_user.first_name
    await _ask_next_question(query.message.reply_text, context, user_id, name, answer_text)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    button_handler = GUEST_BUTTON_HANDLERS.get(text)
    if button_handler:
        await button_handler(update, context)
        return

    awaiting = context.user_data.get("awaiting")
    user_id = update.effective_chat.id

    if awaiting == "qa":
        name = update.effective_user.first_name
        await _ask_next_question(update.message.reply_text, context, user_id, name, text)

    elif awaiting == "order_preferences":
        cocktail_id = context.user_data.pop("pending_cocktail_id", None)
        context.user_data.pop("awaiting", None)
        place_order(user_id, cocktail_id, text)
        await _confirm_order(update.message.reply_text)

    else:
        name = update.effective_user.first_name
        await _start_qa(update.message.reply_text, context, user_id, name, text)