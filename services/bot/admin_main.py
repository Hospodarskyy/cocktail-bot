import os
from dotenv import load_dotenv
load_dotenv()

from telegram import BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from services.bot.handlers import admin
from services.bot.handlers.auth import admin_only

COMMANDS = [
    BotCommand("start", "Show the admin menu"),
    BotCommand("orders", "View active orders"),
    BotCommand("history", "View past orders"),
    BotCommand("cocktails", "Cocktail catalog summary"),
    BotCommand("users", "Recently onboarded guests"),
    BotCommand("inventory", "View or update ingredient stock"),
]

async def _post_init(app):
    await app.bot.set_my_commands(COMMANDS)

def main():
    token = os.getenv("ADMIN_BOT_TOKEN")
    app = Application.builder().token(token).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", admin_only(admin.start)))
    app.add_handler(CommandHandler("orders", admin_only(admin.cmd_orders)))
    app.add_handler(CommandHandler("history", admin_only(admin.cmd_history)))
    app.add_handler(CommandHandler("cocktails", admin_only(admin.cmd_cocktails)))
    app.add_handler(CommandHandler("users", admin_only(admin.cmd_users)))
    app.add_handler(CommandHandler("inventory", admin_only(admin.cmd_inventory)))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_history_day), pattern=r"^historyday:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_order_status), pattern=r"^orderstatus:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_adapt_recipe), pattern=r"^adapt:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_inventory_action), pattern=r"^inv:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_inventory_add_new), pattern=r"^invaddnew$"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_inventory_pick), pattern=r"^invpick:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_inventory_page), pattern=r"^invpage:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_inventory_remove_pick), pattern=r"^invrmpick:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_inventory_remove_page), pattern=r"^invrmpage:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_guest_page), pattern=r"^guestpage:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_guest_list_back), pattern=r"^guestlist$"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_guest_pick), pattern=r"^guestpick:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_guest_manage), pattern=r"^guestmanage:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_guest_clear), pattern=r"^userclear:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_inventory_category_pick), pattern=r"^invcat:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_inventory_remove_category_pick), pattern=r"^invrmcat:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_manual_order_guest_pick), pattern=r"^manordguest:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_manual_order_guest_page), pattern=r"^manordguestpage:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_manual_order_category_pick), pattern=r"^manordcat:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_manual_order_cocktail_pick), pattern=r"^manordpick:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_manual_order_page), pattern=r"^manordpage:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_manual_order_confirm), pattern=r"^manordconfirm:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_manual_order_writeprefs), pattern=r"^manordwriteprefs:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_cocktail_category_list_back), pattern=r"^cocktailcatlist$"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_cocktail_category_pick), pattern=r"^cocktailcat:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_cocktail_page), pattern=r"^cocktailpage:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_cocktail_view), pattern=r"^cocktailview:"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_cocktail_add_start), pattern=r"^cocktailadd$"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_cocktail_save), pattern=r"^cocktailsave$"))
    app.add_handler(CallbackQueryHandler(admin_only(admin.handle_cocktail_discard), pattern=r"^cocktaildiscard$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_only(admin.handle_text)))

    print("Admin bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
