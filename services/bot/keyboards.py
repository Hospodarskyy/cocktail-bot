from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def cocktail_keyboard(cocktail_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✓ Order", callback_data=f"order:{cocktail_id}"),
            InlineKeyboardButton("👎 Not for me", callback_data=f"skip:{cocktail_id}")
        ]
    ])

def order_preferences_keyboard(cocktail_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("No preferences", callback_data=f"confirm:{cocktail_id}"),
            InlineKeyboardButton("Write preferences", callback_data=f"writeprefs:{cocktail_id}")
        ]
    ])

def order_status_keyboard(order_id, status):
    if status == "pending":
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("▶️ Start", callback_data=f"orderstatus:in_progress:{order_id}"),
            InlineKeyboardButton("✕ Cancel", callback_data=f"orderstatus:cancelled:{order_id}")
        ]])
    if status == "in_progress":
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("✓ Complete", callback_data=f"orderstatus:completed:{order_id}"),
            InlineKeyboardButton("✕ Cancel", callback_data=f"orderstatus:cancelled:{order_id}")
        ]])
    return None

def admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 View Orders", callback_data="menu:orders")],
        [InlineKeyboardButton("🧾 Order History", callback_data="menu:history")],
        [InlineKeyboardButton("🍸 Cocktails", callback_data="menu:cocktails")],
        [InlineKeyboardButton("👥 Users", callback_data="menu:users")],
        [InlineKeyboardButton("🔄 Refresh Menu", callback_data="menu:refresh")]
    ])

def guest_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍹 Recommend me something", callback_data="guestmenu:recommend")],
        [InlineKeyboardButton("💬 Help me decide", callback_data="guestmenu:qa")],
        [InlineKeyboardButton("📋 Full menu", callback_data="guestmenu:fullmenu")]
    ])

def qa_options_keyboard(options):
    buttons = [[InlineKeyboardButton(option, callback_data=f"qa:{i}")] for i, option in enumerate(options)]
    return InlineKeyboardMarkup(buttons)
