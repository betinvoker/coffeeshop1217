import hashlib
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.contrib import messages
from bot.models import Customer, TelegramUser, Category, MenuItem, Cart, CartItem, Order, OrderItem

@staff_member_required(login_url='/login/')
def order_panel(request):
    orders = Order.objects.select_related(
        'customer',
        'customer__user',           # если заказ от веб-пользователя
        'customer__telegram_user'   # если заказ от Telegram)
        ).prefetch_related('items__item__category').order_by('-created_at')

    # Фильтрация
    order_id = request.GET.get('order_id')
    status = request.GET.get('status')

    if order_id and order_id.isdigit():
        orders = orders.filter(id=int(order_id))
    elif status and status in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=status)

    # ✅ Группировка по секциям
    pending_orders = orders.filter(status='pending')          # Ожидает
    active_orders = orders.filter(status__in=['confirmed'])   # В работе (только "Подтверждён")
    completed_orders = orders.filter(status__in=['completed', 'canceled'])  # Готов / Отменён

    return render(request, 'barista_app/orderPanel.html', {
        'pending_orders': pending_orders,
        'active_orders': active_orders,
        'completed_orders': completed_orders,
        'status_choices': Order.STATUS_CHOICES,
        'current_filters': {
            'order_id': order_id or '',
            'status': status or '',
        }
    })

@staff_member_required
def update_status(request, order_id, status):
    order = get_object_or_404(Order, id=order_id)
    if status in dict(Order.STATUS_CHOICES):
        order.status = status
        order.save()
    return redirect('barista_app:order_panel')

@staff_member_required
def accept_order(request):
    categories = Category.objects.prefetch_related('items').filter(
        items__is_available=True
    ).distinct().order_by('order', 'name')

    # Получаем корзину из сессии
    cart = request.session.get('barista_cart', [])
    cart_items = []
    total = 0
    for item_data in cart:
        try:
            item = MenuItem.objects.get(id=item_data['id'])
            qty = item_data['quantity']
            cart_items.append({'item': item, 'quantity': qty, 'total_price': item.price * qty})
            total += item.price * qty
        except MenuItem.DoesNotExist:
            continue

    return render(request, 'barista_app/acceptOrder.html', {
        'categories': categories,
        'cart_items': cart_items,
        'cart_total': total,
    })

@staff_member_required
def cart_add(request):
    if request.method == "POST":
        item_id = request.POST.get('item_id')
        try:
            item = MenuItem.objects.get(id=item_id, is_available=True)
        except (MenuItem.DoesNotExist, ValueError):
            pass
        else:
            cart = request.session.get('barista_cart', [])
            for entry in cart:
                if entry['id'] == item.id:
                    entry['quantity'] += 1
                    break
            else:
                cart.append({'id': item.id, 'quantity': 1})
            request.session['barista_cart'] = cart
            request.session.modified = True
    return redirect('barista_app:accept_order')

@staff_member_required
def cart_update(request):
    if request.method == "POST":
        item_id = request.POST.get('item_id')
        quantity = request.POST.get('quantity')
        try:
            item_id = int(item_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            return redirect('barista_app:accept_order')

        cart = request.session.get('barista_cart', [])
        if quantity <= 0:
            cart = [entry for entry in cart if entry['id'] != item_id]
        else:
            for entry in cart:
                if entry['id'] == item_id:
                    entry['quantity'] = quantity
                    break
            else:
                cart.append({'id': item_id, 'quantity': quantity})
        request.session['barista_cart'] = cart
        request.session.modified = True
    return redirect('barista_app:accept_order')

@staff_member_required
def cart_clear(request):
    if request.method == "POST":
        request.session['barista_cart'] = []
        request.session.modified = True
    return redirect('barista_app:accept_order')

@staff_member_required
@transaction.atomic
def create_order(request):
    if request.method == "POST":
        phone = request.POST.get('phone', '').strip()
        order_type = request.POST.get('order_type')
        address = request.POST.get('address', '').strip() if order_type == 'delivery' else None

        if not phone:
            messages.error(request, "Телефон обязателен")
            return redirect('barista_app:accept_order')

        # Генерируем уникальный chat_id на основе телефона (хеш)
        hash_id = int(hashlib.md5(phone.encode()).hexdigest()[:12], 16)
        # Делаем его отрицательным, чтобы отличать от настоящих Telegram ID
        fake_chat_id = -abs(hash_id)

        # Находим или создаём клиента
        telegram_user, created = TelegramUser.objects.get_or_create(
            phone=phone,
            defaults={
                'name': 'Клиент',
                'chat_id': fake_chat_id
            }
        )

        customer, _ = Customer.objects.get_or_create(
            telegram_user=telegram_user,
            defaults={'name': 'Клиент', 'phone': phone}
        )

        # Берём корзину из сессии
        cart = request.session.get('barista_cart', [])
        if not cart:
            messages.error(request, "Корзина пуста")
            return redirect('barista_app:accept_order')

        # Считаем итог и собираем позиции
        total = 0
        items_data = []
        for entry in cart:
            try:
                item = MenuItem.objects.get(id=entry['id'])
                qty = entry['quantity']
                items_data.append((item, qty))
                total += item.price * qty
            except MenuItem.DoesNotExist:
                continue

        if not items_data:
            messages.error(request, "Нет доступных позиций")
            return redirect('barista_app:accept_order')

        # Создаём заказ
        order = Order.objects.create(
            customer=customer,
            order_type=order_type,
            address=address,
            total_price=total,
            status='pending'
        )

        # Добавляем позиции
        for item, qty in items_data:
            OrderItem.objects.create(
                order=order,
                item=item,
                quantity=qty
            )

        # Очищаем корзину
        request.session['barista_cart'] = []
        request.session.modified = True

        messages.success(request, f"Заказ #{order.id} успешно создан!")
        return redirect('barista_app:order_panel')

    return redirect('barista_app:accept_order')