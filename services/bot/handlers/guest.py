from telegram import Update
from telegram.ext import ContextTypes
from services.bot.api_client import onboard, recommend, place_order, send_feedback
from services.bot.keyboards import cocktail_keyboard, order_preferences_keyboard, guest_menu_keyboard, qa_options_keyboard
from services.bot import llm_openai as llm

MENU_TEXT = "What would you like to do?"
DEFAULT_PREFERENCES = "no strong preferences, open to suggestions"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(f"Welcome to the bar! {MENU_TEXT}", reply_markup=guest_menu_keyboard())

async def _confirm_order(reply_to):
    await reply_to("Order sent to the bar! 🍸")
    await reply_to("Anything else to order?", reply_markup=guest_menu_keyboard())

async def _send_recommendations(reply_to, user_id):
    results = recommend(user_id, top_k=5)
    for cocktail in results:
        text = f"🍹 {cocktail['name']}\n{cocktail['ingredients']}"
        await reply_to(text, reply_markup=cocktail_keyboard(cocktail["id"]))
    await reply_to(MENU_TEXT, reply_markup=guest_menu_keyboard())

async def handle_guest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "recommend":
        user_id = update.effective_chat.id
        try:
            await _send_recommendations(query.message.reply_text, user_id)
        except Exception:
            name = update.effective_user.first_name
            onboard(user_id, name, DEFAULT_PREFERENCES)
            await _send_recommendations(query.message.reply_text, user_id)

    elif action == "qa":
        context.user_data["qa_history"] = []
        context.user_data["qa_turns"] = 0
        context.user_data["awaiting"] = "qa"
        user_id = update.effective_chat.id
        name = update.effective_user.first_name
        await _ask_next_question(query.message.reply_text, context, user_id, name, answer_text=None)

    elif action == "fullmenu":
        await query.message.reply_text("The full menu is coming soon!", reply_markup=guest_menu_keyboard())

async def _ask_next_question(reply_to, context, user_id, name, answer_text):
    force_finish = context.user_data["qa_turns"] >= llm.MAX_TURNS
    result, history = llm.next_turn(context.user_data["qa_history"], answer_text=answer_text, force_finish=force_finish)
    context.user_data["qa_history"] = history
    context.user_data["qa_turns"] += 1

    if result["type"] == "question":
        context.user_data["qa_options"] = result["options"]
        await reply_to(result["question"], reply_markup=qa_options_keyboard(result["options"]))
    else:
        context.user_data.pop("awaiting", None)
        context.user_data.pop("qa_history", None)
        context.user_data.pop("qa_options", None)
        onboard(user_id, name, result["preferences_summary"])
        await reply_to("Great, I've got a good sense of what you like!")
        await _send_recommendations(reply_to, user_id)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, cocktail_id = query.data.split(":")
    cocktail_id = int(cocktail_id)
    user_id = update.effective_chat.id

    if action == "skip":
        send_feedback(user_id, cocktail_id)
        await query.message.reply_text("Got it, noted as not for you.", reply_markup=guest_menu_keyboard())

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
    awaiting = context.user_data.get("awaiting")
    user_id = update.effective_chat.id
    text = update.message.text

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
        context.user_data["qa_history"] = []
        context.user_data["qa_turns"] = 0
        context.user_data["awaiting"] = "qa"
        await _ask_next_question(update.message.reply_text, context, user_id, name, text)
