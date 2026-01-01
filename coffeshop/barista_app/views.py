from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from bot.models import (TelegramUser, Category, Order, OrderItem, MenuItem)
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required(login_url='/login/')
def order_panel(request):
    # Базовый QuerySet
    orders = Order.objects.select_related('user') \
                          .prefetch_related('items__item__category') \
                          .order_by('-created_at')

    # Получаем параметры из GET-запроса
    order_id = request.GET.get('order_id')
    status = request.GET.get('status')

    # Фильтрация
    if order_id:
        if order_id.isdigit():
            orders = orders.filter(id=int(order_id))
        # Можно добавить else: messages.warning(...), но пока просто игнорируем
    if status and status in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=status)

    # Список статусов для выпадающего списка
    status_choices = Order.STATUS_CHOICES

    return render(request, 'orderPanel.html', {
        'orders': orders,
        'status_choices': status_choices,
        'current_filters': {
            'order_id': order_id or '',
            'status': status or '',
        }
    })