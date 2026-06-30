import os
from dotenv import load_dotenv
load_dotenv()

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from services.bot.handlers import guest

def main():
    token = os.getenv("GUEST_BOT_TOKEN")
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", guest.start))
    app.add_handler(CallbackQueryHandler(guest.handle_guest_menu, pattern=r"^guestmenu:"))
    app.add_handler(CallbackQueryHandler(guest.handle_qa_answer, pattern=r"^qa:"))
    app.add_handler(CallbackQueryHandler(guest.handle_callback, pattern=r"^(order|skip|confirm|writeprefs):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guest.handle_text))

    print("Guest bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
