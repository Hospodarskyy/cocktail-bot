import os
from dotenv import load_dotenv
load_dotenv()

from telegram import BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from services.bot.handlers import guest

COMMANDS = [
    BotCommand("start", "Show the main menu"),
    BotCommand("recommend", "Get cocktail recommendations"),
    BotCommand("qa", "Help me decide"),
    BotCommand("menu", "Full menu"),
]

async def _post_init(app):
    await app.bot.set_my_commands(COMMANDS)

def main():
    token = os.getenv("GUEST_BOT_TOKEN")
    app = Application.builder().token(token).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", guest.start))
    app.add_handler(CommandHandler("recommend", guest.handle_recommend))
    app.add_handler(CommandHandler("qa", guest.handle_qa_start))
    app.add_handler(CommandHandler("menu", guest.handle_fullmenu))
    app.add_handler(CallbackQueryHandler(guest.handle_qa_answer, pattern=r"^qa:"))
    app.add_handler(CallbackQueryHandler(guest.handle_callback, pattern=r"^(order|skip|confirm|writeprefs):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guest.handle_text))

    print("Guest bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
