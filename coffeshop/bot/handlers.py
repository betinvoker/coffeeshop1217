from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from .models import *
from .keyboards import *
import logging
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# Асинхронные обертки для ORM запросов
@sync_to_async
def get_or_create_user(user_id, username, first_name, last_name):
    """Создание или получение пользователя"""
    return TelegramUser.objects.get_or_create(
        user_id=user_id,
        defaults={
            'username': username,
            'first_name': first_name,
            'last_name': last_name
        }
    )

@sync_to_async
def get_categories():
    """Получение всех категорий"""
    return list(Category.objects.all().order_by('order'))

@sync_to_async
def get_category_by_id(category_id):
    """Получение категории по ID"""
    return Category.objects.get(id=category_id)

@sync_to_async
def get_products_by_category(category):
    """Получение товаров категории"""
    return list(Product.objects.filter(category=category, is_available=True))

@sync_to_async
def get_user_cart(user):
    """Получение или создание корзины пользователя"""
    cart, created = Cart.objects.get_or_create(user=user, is_active=True)
    return cart

@sync_to_async
def get_cart_items_by_products(cart, products):
    """Получение элементов корзины для товаров"""
    return list(CartItem.objects.filter(cart=cart, product__in=products))

@sync_to_async
def get_cart_items(cart):
    """Получение всех элементов корзины"""
    return list(cart.items.all())

@sync_to_async
def get_cart_by_user(user):
    """Получение активной корзины пользователя"""
    return Cart.objects.filter(user=user, is_active=True).first()

@sync_to_async
def update_cart_item_quantity(cart_item_id, action):
    """Обновление количества товара в корзине"""
    try:
        cart_item = CartItem.objects.select_related('product', 'cart').get(id=cart_item_id)
        
        if action == 'increase':
            cart_item.quantity += 1
            cart_item.save()
        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
            else:
                # Если количество = 1 и нажали "уменьшить" - удаляем товар
                cart_item.delete()
                return None
        return cart_item
    except CartItem.DoesNotExist:
        return None

@sync_to_async
def remove_cart_item(cart_item_id):
    """Удаление товара из корзины"""
    try:
        cart_item = CartItem.objects.get(id=cart_item_id)
        cart_item.delete()
        return True
    except CartItem.DoesNotExist:
        return False

@sync_to_async
def clear_cart(user):
    """Очистка всей корзины пользователя"""
    try:
        cart = Cart.objects.filter(user=user, is_active=True).first()
        if cart:
            cart.items.all().delete()
            return True
    except Exception as e:
        logger.error(f"Error clearing cart: {e}")
        return False
    
@sync_to_async
def get_cart_item_by_id(cart_item_id):
    """Получение элемента корзины по ID"""
    try:
        return CartItem.objects.select_related('product', 'cart').get(id=cart_item_id)
    except CartItem.DoesNotExist:
        return None

@sync_to_async
def get_cart_with_items(user):
    """Получение корзины с элементами"""
    try:
        user = TelegramUser.objects.get(user_id=user)
        cart = Cart.objects.filter(user=user, is_active=True).first()
        if cart:
            # Презагружаем элементы корзины
            list(cart.items.all())  # Это вызовет запрос
        return cart
    except TelegramUser.DoesNotExist:
        return None

@sync_to_async
def get_cart_items_with_products(cart):
    """Получение элементов корзины с предзагруженными товарами"""
    if not cart:
        return []
    return list(CartItem.objects.filter(cart=cart).select_related('product'))

@sync_to_async
def cart_has_items(cart):
    """Проверка наличия товаров в корзине (асинхронная версия)"""
    if not cart:
        return False
    return CartItem.objects.filter(cart=cart).exists()

@sync_to_async
def get_cart_total_price(cart):
    """Получение общей суммы корзины"""
    if not cart:
        return 0
    from django.db.models import Sum
    result = CartItem.objects.filter(cart=cart).aggregate(
        total=Sum('product__price') * Sum('quantity')
    )
    return result['total'] or 0

@sync_to_async
def get_cart_items_with_all_relations(cart):
    """Получение элементов корзины со всеми связями"""
    return list(CartItem.objects.filter(cart=cart).select_related('product', 'product__category'))

@sync_to_async
def get_cart_with_items_and_products(user):
    """Получение корзины с элементами и товарами"""
    cart = Cart.objects.filter(user=user, is_active=True).first()
    if cart:
        # Предзагружаем товары для элементов корзины
        cart.items_with_products = list(CartItem.objects.filter(cart=cart).select_related('product'))
    return cart

@sync_to_async
def get_cart_total_price_safe(cart):
    """Безопасное получение общей суммы корзины"""
    if not cart:
        return 0
    
    # Используем агрегацию для расчета суммы одним запросом
    from django.db.models import Sum, F
    result = CartItem.objects.filter(cart=cart).aggregate(
        total=Sum(F('product__price') * F('quantity'))
    )
    return result['total'] or 0

@sync_to_async
def get_cart_items_total(cart):
    """Получение элементов корзины с расчетом суммы"""
    if not cart:
        return []
    
    # Получаем элементы с предзагруженными товарами
    items = CartItem.objects.filter(cart=cart).select_related('product')
    
    # Создаем список с рассчитанными суммами
    result = []
    for item in items:
        item.total_price = item.product.price * item.quantity
        result.append(item)
    
    return result

async def handle_cart_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий с товарами в корзине (только для корзины)"""
    query = update.callback_query
    await query.answer()
    
    # Определяем тип действия
    if query.data.startswith('cart_increase_'):
        cart_item_id = int(query.data.split('_')[2])
        action = 'increase'
        cart_item = await update_cart_item_quantity(cart_item_id, action)
        
    elif query.data.startswith('cart_decrease_'):
        cart_item_id = int(query.data.split('_')[2])
        action = 'decrease'
        cart_item = await update_cart_item_quantity(cart_item_id, action)
        
    elif query.data.startswith('remove_'):
        cart_item_id = int(query.data.split('_')[1])
        success = await remove_cart_item(cart_item_id)
        if success:
            await query.answer("Товар удален из корзины ✅")
        else:
            await query.answer("Ошибка при удалении товара ❌")
            
    elif query.data == 'clear_cart':
        user = await get_user_by_id_or_create(
            user_id=query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            last_name=query.from_user.last_name
        )
        success = await clear_cart(user)
        if success:
            await query.answer("Корзина очищена ✅")
            # Показываем пустую корзину
            text = "🛒 Ваша корзина пуста"
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Меню", callback_data="menu")
            ]])
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            return
        else:
            await query.answer("Ошибка при очистке корзины ❌")
            return
    
    # Обновляем отображение корзины
    await show_cart(update, context)

@sync_to_async
def get_product_by_id(product_id):
    """Получение товара по ID"""
    return Product.objects.get(id=int(product_id))

@sync_to_async
def get_products_by_category_id(category_id):
    """Получение товаров по ID категории"""
    return list(Product.objects.filter(category_id=category_id, is_available=True))

@sync_to_async
def update_user_phone(user, phone):
    """Обновление телефона пользователя"""
    user.phone = phone
    user.save()
    return user

@sync_to_async
def create_order(user, cart, address, phone, total_price):
    """Создание заказа"""
    order = Order.objects.create(
        user=user,
        cart=cart,
        total_price=total_price,  # Используем переданную сумму
        address=address,
        phone=phone,
        status='new'
    )
    # Деактивируем корзину
    cart.is_active = False
    cart.save()
    return order

@sync_to_async
def get_user_by_id(user_id):
    """Получение пользователя по ID"""
    return TelegramUser.objects.get(user_id=user_id)

@sync_to_async
def get_active_cart_by_user_id(user_id):
    """Получение активной корзины пользователя по ID (асинхронная)"""
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        return Cart.objects.filter(user=user, is_active=True).first()
    except TelegramUser.DoesNotExist:
        return None
    
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_user, created = await get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    welcome_text = f"""
    👋 Привет, {user.first_name}!

    Добро пожаловать в наш сервис доставки еды!

    🍔 <b>Основные команды:</b>
    • /start - Главное меню
    • /menu - Просмотр меню
    • /cart - Просмотр корзины
    • /orders - Мои заказы

    Выберите действие из меню ниже 👇
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu()
    )

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = await get_categories()
    
    if not categories:
        # Проверяем, откуда пришел запрос
        if update.callback_query:
            await update.callback_query.edit_message_text("Меню временно недоступно 😔")
        else:
            await update.message.reply_text("Меню временно недоступно 😔")
        return
    
    text = "🍽 <b>Наше меню</b>\n\nВыберите категорию:"
    
    # Проверяем, откуда пришел запрос
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=categories_keyboard(categories)
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=categories_keyboard(categories)
        )

async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[1])
    category = await get_category_by_id(category_id)
    
    # Используем новую функцию с ID категории
    products = await get_products_by_category_id(category_id)
    
    if not products:
        await query.edit_message_text(
            f"В категории '{category.name}' пока нет товаров 😔",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_categories")
            ]])
        )
        return
    
    # Получаем или создаем пользователя
    user = await get_user_by_id_or_create(
        user_id=query.from_user.id,
        username=query.from_user.username,
        first_name=query.from_user.first_name,
        last_name=query.from_user.last_name
    )
    cart = await get_user_cart(user)
    cart_items = await get_cart_items_by_products(cart, products)
    
    text = f"<b>{category.name}</b>\n\n{category.description or ''}"
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=products_keyboard(products, cart_items)
    )

@sync_to_async
def get_product_with_category(product_id):
    """Получение товара с категорией по ID"""
    return Product.objects.select_related('category').get(id=int(product_id))

@sync_to_async 
def get_category_for_product(product):
    """Получение категории для товара"""
    # Этот метод загружает связанную категорию, если она еще не загружена
    return product.category

@sync_to_async
def get_products_by_category(category):
    """Получение товаров категории"""
    # Используем category.id вместо объекта category для безопасности
    return list(Product.objects.filter(category_id=category.id, is_available=True))

@sync_to_async
def get_cart_items_with_products_from_user(user):
    """Получение элементов корзины с товарами по пользователю"""
    cart = Cart.objects.filter(user=user, is_active=True).first()
    if not cart:
        return []
    return list(CartItem.objects.filter(cart=cart).select_related('product'))

@sync_to_async
def get_cart_items_with_products_data(user_id):
    """Получение данных элементов корзины с товарами"""
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        cart = Cart.objects.filter(user=user, is_active=True).first()
        if not cart:
            return []
        
        # Получаем данные одним запросом с join
        from django.db.models import F, Sum
        cart_items = CartItem.objects.filter(cart=cart).select_related('product').values(
            'id',
            'quantity',
            product_name=F('product__name'),
            total_price=F('product__price') * F('quantity')
        )
        return list(cart_items)
    except TelegramUser.DoesNotExist:
        return []

@sync_to_async
def handle_cart_action_simple(cart, product, action):
    """Обработка действий с корзиной из меню (добавление/удаление товаров)"""
    if action == 'increase':
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': 1}
        )
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        return cart_item
    
    elif action == 'decrease':
        try:
            cart_item = CartItem.objects.get(cart=cart, product=product)
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
            else:
                cart_item.delete()
                return None
            return cart_item
        except CartItem.DoesNotExist:
            return None

async def handle_product_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Получаем или создаем пользователя
    user = await get_user_by_id_or_create(
        user_id=query.from_user.id,
        username=query.from_user.username,
        first_name=query.from_user.first_name,
        last_name=query.from_user.last_name
    )
    cart = await get_user_cart(user)
    
    action, product_id = query.data.split('_')
    
    # Получаем товар с категорией
    product = await get_product_with_category(product_id)
    
    # Это функция для изменения количества в меню
    await handle_cart_action_simple(cart, product, action)
    
    # Получаем категорию товара
    category = await get_category_for_product(product)
    
    # Получаем товары по ID категории
    products = await get_products_by_category_id(category.id)
    
    # Получаем элементы корзины
    cart_items = await get_cart_items_by_products(cart, products)
    
    text = f"<b>{category.name}</b>"
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=products_keyboard(products, cart_items)
    )

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать корзину с товарами"""
    # Получаем или создаем пользователя
    user = await get_user_by_id_or_create(
        user_id=update.effective_user.id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name
    )
    
    # Получаем элементы корзины с предзагруженными товарами
    cart_items = await get_cart_items_with_products_from_user(user)
    
    if not cart_items:
        text = "🛒 Ваша корзина пуста"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Меню", callback_data="menu")
        ]])
    else:
        items_text = ""
        total_price = 0
        
        for item in cart_items:
            # Рассчитываем сумму для каждого элемента
            item_total = item.product.price * item.quantity
            items_text += f"• {item.product.name} x{item.quantity} = {item_total} ₽\n"
            total_price += item_total
        
        text = f"""
🛒 <b>Ваша корзина</b>

{items_text}
<b>Итого: {total_price} ₽</b>

<i>Используйте кнопки ниже для управления товарами:</i>
"""
        keyboard = cart_keyboard(cart_items)
    
    # Универсальная отправка сообщения
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Получаем или создаем пользователя
    user = await get_user_by_id_or_create(
        user_id=query.from_user.id,
        username=query.from_user.username,
        first_name=query.from_user.first_name,
        last_name=query.from_user.last_name
    )
    
    # Получаем активную корзину
    cart = await get_cart_by_user(user)
    
    # Проверяем наличие товаров в корзине
    has_items = await cart_has_items(cart) if cart else False
    
    if not has_items:
        await query.edit_message_text(
            "❌ Ваша корзина пуста! Сначала добавьте товары в корзину.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 В меню", callback_data="menu")
            ]])
        )
        return
    
    # Сохраняем ID корзины
    context.user_data['checkout_cart_id'] = cart.id
    
    if not user.phone:
        # Используем INLINE клавиатуру для запроса телефона
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "📱 Поделиться номером телефона", 
                callback_data="request_phone"
            )
        ]])
        
        await query.edit_message_text(
            "Для оформления заказа нам нужен ваш номер телефона 📱\n\n"
            "Пожалуйста, нажмите кнопку ниже:",
            reply_markup=keyboard
        )
    else:
        context.user_data['checkout_step'] = 'address'
        await query.edit_message_text(
            f"📞 Ваш телефон: {user.phone}\n\n"
            "Пожалуйста, введите адрес доставки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад в корзину", callback_data="cart")
            ]])
        )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка полученного контакта"""
    # Получаем или создаем пользователя
    user = await get_user_by_id_or_create(
        user_id=update.effective_user.id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name
    )
    
    contact = update.message.contact
    user = await update_user_phone(user, contact.phone_number)
    
    # Удаляем reply-клавиатуру
    await update.message.reply_text(
        "✅ Номер телефона сохранен!",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Проверяем, находимся ли мы в процессе оформления заказа
    checkout_step = context.user_data.get('checkout_step')
    
    if checkout_step == 'request_phone':
        # Если был запрос телефона при оформлении заказа, продолжаем оформление
        context.user_data['checkout_step'] = 'address'
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📞 <b>Ваш телефон:</b> {user.phone}\n\n"
                 "Теперь введите адрес доставки:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад в корзину", callback_data="cart")
            ]])
        )
    else:
        # Проверяем наличие активной корзины и товаров в ней
        cart = await get_active_cart_by_user_id(update.effective_user.id)
        
        if cart:
            # Проверяем наличие товаров в корзине (асинхронно)
            has_items = await cart_has_items(cart)
            if has_items:
                # Если есть товары, предлагаем продолжить оформление
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="📞 Номер телефона сохранен!\n\n"
                         "У вас есть товары в корзине. Хотите оформить заказ?",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout"),
                            InlineKeyboardButton("🛒 Посмотреть корзину", callback_data="cart")
                        ]
                    ])
                )
                return
        
        # Если нет активной корзины или она пуста
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📞 Номер телефона сохранен!\n\n"
                 "Теперь вы можете добавлять товары в корзину и оформлять заказы.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Меню", callback_data="menu"),
                InlineKeyboardButton("🛒 Корзина", callback_data="cart")
            ]])
        )

@sync_to_async
def get_user_by_id_or_create(user_id, username=None, first_name=None, last_name=None):
    """Получение пользователя по ID или создание, если не существует"""
    try:
        return TelegramUser.objects.get(user_id=user_id)
    except TelegramUser.DoesNotExist:
        return TelegramUser.objects.create(
            user_id=user_id,
            username=username or "",
            first_name=first_name or "",
            last_name=last_name or ""
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user = update.effective_user
    
    # Если пользователь пишет боту в первый раз, создаем запись
    telegram_user, created = await get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    ) 
    
    # Проверяем, находится ли пользователь в процессе оформления заказа
    checkout_step = context.user_data.get('checkout_step')
    
    if checkout_step == 'address':
        await handle_address(update, context)
        return
    
    # Проверяем, если пользователь отправил текст, который может быть адресом
    # и у него есть активная корзина, начинаем оформление
    cart = await get_active_cart_by_user_id(user.id)
    
    if cart:
        # Проверяем наличие товаров в корзине
        has_items = await cart_has_items(cart)
        if has_items:
            # Предлагаем начать оформление заказа
            total_price = await get_cart_total_price(cart)
            await update.message.reply_text(
                f"У вас есть товары в корзине на сумму {total_price} ₽\n\n"
                "Хотите оформить заказ?",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout"),
                        InlineKeyboardButton("🛒 Посмотреть корзину", callback_data="cart")
                    ],
                    [
                        InlineKeyboardButton("📋 Продолжить покупки", callback_data="menu")
                    ]
                ])
            )
            return
    
    # Если это не адрес для оформления заказа и нет активной корзины, показываем стартовое сообщение
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для заказа еды. Используйте команды:\n"
        "/start - Главное меню\n"
        "/menu - Посмотреть меню\n"
        "/cart - Корзина",
        reply_markup=main_menu()
    )

async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "◀️ Назад":
        await show_cart(update, context)
        return
    
    address = update.message.text
    
    # Получаем или создаем пользователя
    user = await get_user_by_id_or_create(
        user_id=update.effective_user.id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name
    )
    
    # Проверяем, есть ли сохраненный ID корзины в context.user_data
    cart_id = context.user_data.get('checkout_cart_id')
    
    if cart_id:
        # Если есть сохраненный ID, используем его
        cart = await sync_to_async(Cart.objects.get)(id=cart_id)
    else:
        # Если нет сохраненного ID, ищем активную корзину пользователя
        cart = await get_active_cart_by_user_id(update.effective_user.id)
        
        # Используем асинхронную проверку наличия товаров
        if not cart:
            await update.message.reply_text(
                "❌ У вас нет активной корзины. Сначала добавьте товары в корзину.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 В меню", callback_data="menu")
                ]])
            )
            return
        
        # Проверяем наличие товаров в корзине
        cart_items = await get_cart_items_with_products(cart)
        if not cart_items:
            await update.message.reply_text(
                "❌ Ваша корзина пуста. Добавьте товары перед оформлением заказа.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 В меню", callback_data="menu")
                ]])
            )
            return
        
        # Сохраняем ID корзины для последующих шагов
        context.user_data['checkout_cart_id'] = cart.id
    
    # Сохраняем адрес
    context.user_data['address'] = address
    
    # Получаем элементы корзины
    cart_items = await get_cart_items_with_products(cart)
    
    # Проверяем, есть ли товары в корзине
    if not cart_items:
        await update.message.reply_text(
            "❌ Ваша корзина пуста. Добавьте товары перед оформлением заказа.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 В меню", callback_data="menu")
            ]])
        )
        return
    
    # Показываем подтверждение заказа
    items_text = "\n".join([
        f"• {item.product.name} x{item.quantity} - {item.total_price} ₽"
        for item in cart_items
    ])
    
    # Получаем телефон пользователя
    phone = user.phone or "Не указан"
    
    # Получаем общую сумму корзины
    total_price = sum(item.total_price for item in cart_items)
    
    text = f"""
✅ <b>Подтверждение заказа</b>

<b>Товары:</b>
{items_text}

<b>Адрес доставки:</b> {address}
<b>Телефон:</b> {phone}
<b>Итого: {total_price} ₽</b>

Подтвердить заказ?
"""
    
    # Устанавливаем шаг оформления заказа
    context.user_data['checkout_step'] = 'confirmation'
    
    # Удаляем клавиатуру "Назад" если она есть
    reply_markup = order_confirmation_keyboard()
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Получаем или создаем пользователя
    user = await get_user_by_id_or_create(
        user_id=query.from_user.id,
        username=query.from_user.username,
        first_name=query.from_user.first_name,
        last_name=query.from_user.last_name
    )
    
    cart = await sync_to_async(Cart.objects.get)(id=context.user_data['checkout_cart_id'])
    
    # Получаем элементы корзины для расчета общей суммы
    cart_items = await get_cart_items_with_products(cart)
    
    # Рассчитываем общую сумму вручную
    total_price = sum(item.total_price for item in cart_items)
    
    # Создаем заказ
    order = await create_order(
        user=user,
        cart=cart,
        address=context.user_data['address'],
        phone=user.phone,
        total_price=total_price
    )
    
    # Отправляем подтверждение
    await query.edit_message_text(
        f"🎉 <b>Заказ #{order.id} оформлен!</b>\n\n"
        f"Мы начали готовить ваш заказ. Ожидайте доставку по адресу:\n"
        f"{order.address}\n\n"
        f"Статус заказа можно отслеживать в разделе 'Мои заказы'",
        parse_mode=ParseMode.HTML
    )
    
    # Очищаем данные
    context.user_data.clear()

async def request_phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Отправляем сообщение с ReplyKeyboardMarkup для запроса контакта
    await query.edit_message_text(
        "Пожалуйста, нажмите кнопку ниже, чтобы поделиться номером телефона:"
    )
    
    # Отправляем новое сообщение с кнопкой запроса контакта
    # (нельзя использовать reply_markup в edit_message_text для ReplyKeyboard)
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    # Отправляем новое сообщение с кнопкой
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Нажмите кнопку, чтобы поделиться номером:",
        reply_markup=keyboard
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех callback запросов"""
    query = update.callback_query
    data = query.data
    
    if data == 'menu' or data == 'back_categories':
        await show_menu(update, context)
    elif data.startswith('category_'):
        await show_category(update, context)
    elif data.startswith('increase_') or data.startswith('decrease_'):
        # Это действия в меню (добавление/удаление из корзины)
        await handle_product_action(update, context)
    elif data == 'cart':
        await show_cart(update, context)
    elif data == 'checkout':
        await checkout_start(update, context)
    elif data == 'request_phone':
        await request_phone_handler(update, context)
    elif data == 'confirm_order':
        await confirm_order(update, context)
    elif data == 'cancel_order':
        await query.edit_message_text("Заказ отменен")
        await show_cart(update, context)
    # Добавляем обработчики для действий в корзине
    elif data.startswith('cart_increase_') or \
         data.startswith('cart_decrease_') or \
         data.startswith('remove_') or \
         data == 'clear_cart':
        # Это действия внутри самой корзины
        await handle_cart_action(update, context)