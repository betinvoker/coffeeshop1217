from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from bot.models import Category, MenuItem, Cart, CartItem, Order, OrderItem, Customer
from django.contrib.auth.models import User

@login_required
def menu_view(request):
    categories = Category.objects.prefetch_related('items').all()
    return render(request, 'web_app/menu.html', {'categories': categories})

@login_required
def add_to_cart(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id, is_available=True)
    
    # 🔑 Получаем или создаём Customer для request.user
    customer, _ = Customer.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.get_full_name() or request.user.username}
    )
    
    cart, _ = Cart.objects.get_or_create(customer=customer)  # ← customer, не user!
    cart_item, created = CartItem.objects.get_or_create(cart=cart, item=item)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    messages.success(request, f"{item.name} добавлен в корзину")
    return redirect('menu')

@login_required
def cart_view(request):
    customer, _ = Customer.objects.get_or_create(user=request.user)
    cart, _ = Cart.objects.get_or_create(customer=customer)
    return render(request, 'web_app/cart.html', {'cart': cart})

@login_required
def create_order(request):
    customer, _ = Customer.objects.get_or_create(user=request.user)
    cart = get_object_or_404(Cart, customer=customer)
    
    if not cart.items.exists():
        messages.error(request, "Корзина пуста")
        return redirect('cart')

    if request.method == 'POST':
        order_type = request.POST.get('order_type')
        address = request.POST.get('address') if order_type == 'delivery' else None

        with transaction.atomic():
            order = Order.objects.create(
                customer=customer,  # ← customer, не user!
                order_type=order_type,
                address=address,
                total_price=cart.total_price(),
                status='pending'
            )
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    item=item.item,
                    quantity=item.quantity
                )
            cart.items.all().delete()
        messages.success(request, f"Заказ #{order.id} создан!")
        return redirect('shop:order_success')

    return render(request, 'web_app/checkout.html', {'cart': cart})

@login_required
def order_success(request):
    return render(request, 'web_app/order_success.html')