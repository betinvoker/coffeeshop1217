import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import logging
from asgiref.sync import async_to_sync
from .bot_config import setup_bot

logger = logging.getLogger(__name__)

# Создаем приложение бота
application = setup_bot()

@csrf_exempt
@require_POST
def telegram_webhook(request):
    """Webhook для Telegram"""
    try:
        # Получаем данные от Telegram
        update_data = json.loads(request.body.decode('utf-8'))
        
        # Обрабатываем обновление
        async_to_sync(application.process_update)(update_data)
        
        return JsonResponse({'status': 'ok'})
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON received")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)