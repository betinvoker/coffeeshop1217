from telegram import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

def main_menu():
    """Главное меню"""
    return ReplyKeyboardMarkup(
        [
            ['☕ Меню', '🛒 Корзина'],
            ['ℹ️ О кофейне', '📱 Контакты'],
            ['🎁 Акции', '📋 Мои заказы']
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def categories_keyboard(categories):
    """Клавиатура категорий"""
    keyboard = []
    row = []
    
    for category in categories:
        row.append(InlineKeyboardButton(
            category.name, 
            callback_data=f"category_{category.id}"
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def products_keyboard(products, cart_items=None, page=0, items_per_page=6):
    """Клавиатура товаров с пагинацией"""
    cart_items_dict = {}
    if cart_items:
        for item in cart_items:
            cart_items_dict[item.product.id] = item.quantity
    
    # Пагинация
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    paginated_products = products[start_idx:end_idx]
    
    keyboard = []
    
    for product in paginated_products:
        quantity = cart_items_dict.get(product.id, 0)
        
        product_text = f"{product.name} - {product.get_formatted_price()}"
        if quantity > 0:
            product_text = f"✅ {product_text} (x{quantity})"
        
        keyboard.append([
            InlineKeyboardButton(
                product_text,
                callback_data=f"product_{product.id}"
            )
        ])
        
        if quantity > 0:
            keyboard.append([
                InlineKeyboardButton("➖", callback_data=f"decrease_{product.id}"),
                InlineKeyboardButton(f"{quantity}", callback_data=f"info_{product.id}"),
                InlineKeyboardButton("➕", callback_data=f"increase_{product.id}"),
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("➕ Добавить", callback_data=f"increase_{product.id}")
            ])
    
    # Пагинация
    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(
            InlineKeyboardButton("◀️", callback_data=f"page_{page-1}")
        )
    
    if end_idx < len(products):
        pagination_buttons.append(
            InlineKeyboardButton("▶️", callback_data=f"page_{page+1}")
        )
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    
    keyboard.append([
        InlineKeyboardButton("◀️ К категориям", callback_data="back_categories"),
        InlineKeyboardButton("🛒 Корзина", callback_data="cart")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def product_detail_keyboard(product_id, quantity=0):
    """Клавиатура для детального просмотра товара"""
    keyboard = []
    
    if quantity > 0:
        keyboard.append([
            InlineKeyboardButton("➖", callback_data=f"detail_decrease_{product_id}"),
            InlineKeyboardButton(f"{quantity} шт.", callback_data=f"info_{product_id}"),
            InlineKeyboardButton("➕", callback_data=f"detail_increase_{product_id}"),
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("➕ Добавить в корзину", callback_data=f"detail_increase_{product_id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_products"),
        InlineKeyboardButton("🛒 В корзину", callback_data="cart")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def sizes_keyboard(product_id):
    """Клавиатура выбора размера"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("S", callback_data=f"size_{product_id}_S"),
            InlineKeyboardButton("M", callback_data=f"size_{product_id}_M"),
        ],
        [
            InlineKeyboardButton("L", callback_data=f"size_{product_id}_L"),
            InlineKeyboardButton("XL", callback_data=f"size_{product_id}_XL"),
        ],
        [
            InlineKeyboardButton("◀️ Без размера", callback_data=f"no_size_{product_id}"),
        ]
    ])

def cart_keyboard(cart_items):
    """Клавиатура корзины"""
    keyboard = []
    
    for item in cart_items:
        product_name = item.product.name
        if item.size:
            size_display = dict(ProductSize.SIZE_CHOICES).get(item.size, item.size)
            product_name = f"{product_name} ({size_display})"
        
        item_text = f"{product_name} x{item.quantity} - {item.get_total_price()} ₽"
        
        keyboard.append([
            InlineKeyboardButton(item_text, callback_data=f"view_item_{item.id}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("➖", callback_data=f"cart_decrease_{item.id}"),
            InlineKeyboardButton("✏️", callback_data=f"edit_item_{item.id}"),
            InlineKeyboardButton("➕", callback_data=f"cart_increase_{item.id}"),
            InlineKeyboardButton("🗑️", callback_data=f"remove_{item.id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🧹 Очистить корзину", callback_data="clear_cart")
    ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout"),
        InlineKeyboardButton("🛍️ Продолжить покупки", callback_data="back_categories")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def order_type_keyboard():
    """Клавиатура выбора типа заказа"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("☕ В кофейне", callback_data="order_type_in_cafe"),
            InlineKeyboardButton("🚶 С собой", callback_data="order_type_takeaway")
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="cart")
        ]
    ])

def table_numbers_keyboard():
    """Клавиатура выбора стола"""
    buttons = []
    row = []
    
    for i in range(1, 11):
        row.append(InlineKeyboardButton(str(i), callback_data=f"table_{i}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_order_type")
    ])
    
    return InlineKeyboardMarkup(buttons)

def confirm_order_keyboard():
    """Клавиатура подтверждения заказа"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить заказ", callback_data="confirm_order"),
            InlineKeyboardButton("❌ Отменить", callback_data="cancel_order")
        ]
    ])

def contact_keyboard():
    """Клавиатура контактов"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📍 На карте", callback_data="show_location"),
            InlineKeyboardButton("📞 Позвонить", callback_data="call_us")
        ],
        [
            InlineKeyboardButton("📱 Telegram", callback_data="telegram_channel"),
            InlineKeyboardButton("📷 Instagram", callback_data="instagram")
        ]
    ])

def my_orders_keyboard(orders):
    """Клавиатура моих заказов"""
    keyboard = []
    
    for order in orders[:5]:  # Показываем последние 5 заказов
        status_display = dict(Order.STATUS_CHOICES).get(order.status, order.status)
        order_text = f"#{order.id} - {status_display} - {order.total_price} ₽"
        
        keyboard.append([
            InlineKeyboardButton(order_text, callback_data=f"view_order_{order.id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def back_to_menu_keyboard():
    """Клавиатура возврата в меню"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")]
    ])

def request_contact_keyboard():
    """Клавиатура запроса контакта"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def promotions_keyboard(promotions):
    """Клавиатура акций"""
    keyboard = []
    
    for promotion in promotions[:5]:  # Показываем последние 5 акций
        keyboard.append([
            InlineKeyboardButton(promotion.title, callback_data=f"promotion_{promotion.id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)