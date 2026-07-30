from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

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

def manual_order_preferences_keyboard(cocktail_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("No preferences", callback_data=f"manordconfirm:{cocktail_id}"),
            InlineKeyboardButton("Write preferences", callback_data=f"manordwriteprefs:{cocktail_id}")
        ]
    ])

def history_nav_keyboard(prev_date, next_date=None):
    row = [InlineKeyboardButton(f"◀ {prev_date.strftime('%b %d')}", callback_data=f"historyday:{prev_date.isoformat()}")]
    if next_date:
        row.append(InlineKeyboardButton(f"{next_date.strftime('%b %d')} ▶", callback_data=f"historyday:{next_date.isoformat()}"))
    return InlineKeyboardMarkup([row])

def order_status_keyboard(order_id, status):
    adapt_row = [InlineKeyboardButton("🔄 Adapt Recipe", callback_data=f"adapt:{order_id}")]
    if status == "pending":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▶️ Start", callback_data=f"orderstatus:in_progress:{order_id}"),
                InlineKeyboardButton("✕ Cancel", callback_data=f"orderstatus:cancelled:{order_id}")
            ],
            adapt_row
        ])
    if status == "in_progress":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✓ Complete", callback_data=f"orderstatus:completed:{order_id}"),
                InlineKeyboardButton("✕ Cancel", callback_data=f"orderstatus:cancelled:{order_id}")
            ],
            adapt_row
        ])
    return None

ADMIN_BUTTON_ORDERS = "📋 Orders"
ADMIN_BUTTON_HISTORY = "🧾 History"
ADMIN_BUTTON_COCKTAILS = "🍸 Cocktails"
ADMIN_BUTTON_USERS = "👥 Users"
ADMIN_BUTTON_INVENTORY = "📦 Inventory"
ADMIN_BUTTON_MANUAL_ORDER = "🧾 New order"

def admin_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            [ADMIN_BUTTON_ORDERS, ADMIN_BUTTON_HISTORY],
            [ADMIN_BUTTON_COCKTAILS, ADMIN_BUTTON_USERS],
            [ADMIN_BUTTON_INVENTORY, ADMIN_BUTTON_MANUAL_ORDER]
        ],
        resize_keyboard=True,
        is_persistent=True
    )

def inventory_action_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 View stock", callback_data="inv:view")],
        [InlineKeyboardButton("✏️ Update stock", callback_data="inv:update")],
        [InlineKeyboardButton("🗑 Remove ingredient", callback_data="inv:remove")]
    ])

def category_picker_keyboard(categories, pick_prefix, extra_rows=None):
    rows = [
        [InlineKeyboardButton(f"{c['category']} ({c['count']})", callback_data=f"{pick_prefix}:{c['category']}")]
        for c in categories
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return InlineKeyboardMarkup(rows)

def guest_summary_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Manage guest", callback_data=f"guestmanage:{user_id}")],
        [InlineKeyboardButton("◀ Back to guest list", callback_data="guestlist")]
    ])

def guest_detail_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear preferences", callback_data=f"userclear:{user_id}")],
        [InlineKeyboardButton("◀ Back", callback_data=f"guestpick:{user_id}")]
    ])

def cocktail_confirm_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Save", callback_data="cocktailsave"),
            InlineKeyboardButton("❌ Discard", callback_data="cocktaildiscard")
        ]
    ])

INVENTORY_PAGE_SIZE = 8

def inventory_list_keyboard(items, page=0, pick_prefix="invpick", page_prefix="invpage", extra_rows=None):
    start = page * INVENTORY_PAGE_SIZE
    page_items = items[start:start + INVENTORY_PAGE_SIZE]

    rows = [[InlineKeyboardButton(i["name"], callback_data=f"{pick_prefix}:{i['id']}")] for i in page_items]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"{page_prefix}:{page - 1}"))
    if start + INVENTORY_PAGE_SIZE < len(items):
        nav.append(InlineKeyboardButton("Next ▶", callback_data=f"{page_prefix}:{page + 1}"))
    if nav:
        rows.append(nav)

    if extra_rows:
        rows.extend(extra_rows)

    return InlineKeyboardMarkup(rows)

GUEST_BUTTON_RECOMMEND = "🍹 Recommend me something"
GUEST_BUTTON_QA = "💬 Help me decide"
GUEST_BUTTON_FULLMENU = "📋 Full menu"

def guest_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            [GUEST_BUTTON_RECOMMEND],
            [GUEST_BUTTON_QA, GUEST_BUTTON_FULLMENU]
        ],
        resize_keyboard=True,
        is_persistent=True
    )

def qa_options_keyboard(options):
    buttons = [[InlineKeyboardButton(option, callback_data=f"qa:{i}")] for i, option in enumerate(options)]
    return InlineKeyboardMarkup(buttons)

def show_more_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Show more", callback_data="showmore")]
    ])