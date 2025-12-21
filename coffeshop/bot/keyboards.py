from telegram import (
    ReplyKeyboardMarkup, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    KeyboardButton
)

def main_menu():
    keyboard = [
        [KeyboardButton("📋 Меню")],
        [KeyboardButton("🛒 Корзина"), KeyboardButton("📦 Мои заказы")],
        [KeyboardButton("📞 Контакты"), KeyboardButton("⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def categories_keyboard(categories):
    keyboard = []
    for i in range(0, len(categories), 2):
        row = categories[i:i+2]
        keyboard.append([
            InlineKeyboardButton(cat.name, callback_data=f"category_{cat.id}")
            for cat in row
        ])
    keyboard.append([InlineKeyboardButton("🛒 Корзина", callback_data="cart")])
    return InlineKeyboardMarkup(keyboard)

def products_keyboard(products, cart_items=None):
    cart_dict = {item.product_id: item.quantity for item in cart_items} if cart_items else {}
    
    keyboard = []
    for product in products:
        quantity = cart_dict.get(product.id, 0)
        row = [
            InlineKeyboardButton(f"➖", callback_data=f"decrease_{product.id}"),
            InlineKeyboardButton(f"{product.name} ({quantity})", 
                               callback_data=f"product_{product.id}"),
            InlineKeyboardButton(f"➕", callback_data=f"increase_{product.id}")
        ]
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_categories"),
        InlineKeyboardButton("🛒 Корзина", callback_data="cart")
    ])
    return InlineKeyboardMarkup(keyboard)

def cart_keyboard(cart_items):
    keyboard = []
    for item in cart_items:
        # Добавляем кнопку удаления товара
        keyboard.append([
            InlineKeyboardButton(f"❌ Удалить", callback_data=f"remove_{item.id}"),
            InlineKeyboardButton(f"➖", callback_data=f"cart_decrease_{item.id}"),
            InlineKeyboardButton(f"{item.quantity} шт", callback_data=f"show_{item.product.id}"),
            InlineKeyboardButton(f"➕", callback_data=f"cart_increase_{item.id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout"),
        InlineKeyboardButton("📋 Меню", callback_data="menu")
    ])
    keyboard.append([
        InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart")
    ])
    return InlineKeyboardMarkup(keyboard)

def order_confirmation_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_order"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def phone_keyboard():
    """Клавиатура для запроса телефона (для инлайн-сообщений)"""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📱 Поделиться номером телефона", 
            callback_data="request_phone"
        )
    ]])

def phone_reply_keyboard():
    """Reply-клавиатура для запроса телефона"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )