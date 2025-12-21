from django.core.management.base import BaseCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from django.conf import settings
from bot.handlers import *
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class Command(BaseCommand):
    help = 'Запуск Telegram бота'

    def handle(self, *args, **options):
        application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

        # Обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("menu", show_menu))
        application.add_handler(CommandHandler("cart", show_cart))

        # Обработчики сообщений
        application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^📋 Меню$'), show_menu))
        application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^🛒 Корзина$'), show_cart))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(MessageHandler(filters.TEXT, handle_address))

        # Обработчики callback-запросов
        application.add_handler(CallbackQueryHandler(handle_callback_query))

        # Запуск бота
        self.stdout.write(self.style.SUCCESS('Бот запущен...'))
        application.run_polling(allowed_updates=Update.ALL_TYPES)