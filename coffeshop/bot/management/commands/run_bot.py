import asyncio
import signal
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram.ext import Application
from telegram import Update
from bot.handlers import register_handlers  # Импорт обработчиков
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)
logging.getLogger("httpx").setLevel(logging.WARNING)

class Command(BaseCommand):
    help = 'Запуск Telegram бота для кофейни'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.application = None
        self.loop = None

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Запуск Telegram бота...'))
        
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(self.style.ERROR('Не установлен TELEGRAM_BOT_TOKEN в настройках!'))
            return

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self.start_bot())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n🛑 Бот останавливается...'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'❌ Критическая ошибка: {e}'))
        finally:
            self.loop.close()
            self.stdout.write(self.style.SUCCESS('✅ Бот остановлен'))

    async def start_bot(self):
        self.application = (
            Application.builder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .build()
        )

        register_handlers(self.application)

        # Инициализация
        await self.application.initialize()

        try:
            # Start polling
            await self.application.start()
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )

            self.stdout.write(self.style.SUCCESS(f'✅ Бот @{self.application.bot.username} успешно запущен!'))
            self.stdout.write(self.style.NOTICE('Нажмите Ctrl+C для остановки'))

            # Wait until shutdown
            stop_event = asyncio.Event()
            signal.signal(signal.SIGINT, lambda *_: stop_event.set())
            await stop_event.wait()

        finally:
            # Остановка — даже при исключении
            await self.shutdown()

    async def shutdown(self):
        if self.application:
            try:
                if self.application.updater.running:
                    await self.application.updater.stop()
                if self.application.running:
                    await self.application.stop()
                await self.application.shutdown()
                self.stdout.write(self.style.SUCCESS('🔌 Соединение с Telegram закрыто'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Ошибка при остановке: {e}'))