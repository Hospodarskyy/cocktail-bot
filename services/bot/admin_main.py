import os
from dotenv import load_dotenv
load_dotenv()

from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from services.bot.handlers import admin

def main():
    token = os.getenv("ADMIN_BOT_TOKEN")
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", admin.start))
    app.add_handler(CallbackQueryHandler(admin.handle_menu, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(admin.handle_order_status, pattern=r"^orderstatus:"))

    print("Admin bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
