import os

def get_allowed_ids() -> set[int]:
    raw = os.getenv("ADMIN_USER_IDS", "")
    return {int(x.strip()) for x in raw.split(",") if x.strip()}

def is_allowed(user_id: int) -> bool:
    allowed = get_allowed_ids()
    return True if not allowed else user_id in allowed

REJECTION_MESSAGE = "This bot is private. Contact the host if you believe this is a mistake."

async def guard(update, context) -> bool:
    """Returns True if allowed, sends a rejection and returns False otherwise."""
    user_id = update.effective_user.id
    if is_allowed(user_id):
        return True
    if update.callback_query:
        await update.callback_query.answer(REJECTION_MESSAGE, show_alert=True)
    elif update.message:
        await update.message.reply_text(REJECTION_MESSAGE)
    return False

def admin_only(handler):
    async def wrapped(update, context):
        if not await guard(update, context):
            return
        return await handler(update, context)
    return wrapped
