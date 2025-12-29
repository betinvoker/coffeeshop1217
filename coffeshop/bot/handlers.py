import os 
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from telegram.error import BadRequest
from telegram.constants import ParseMode
from asgiref.sync import sync_to_async
from .models import TelegramUser, Category, MenuItem, Cart, CartItem, Order, OrderItem

logger = logging.getLogger(__name__)

# Константы состояний
ORDER_TYPE, ADDRESS = range(2)

@sync_to_async
def get_or_create_user(chat_id, username=None):
    user, _ = TelegramUser.objects.get_or_create(chat_id=chat_id)
    if username and not user.name:
        user.name = username
        user.save()
    return user

@sync_to_async
def get_menu_item(item_id):
    return MenuItem.objects.select_related('category').get(id=item_id)

@sync_to_async
def get_all_categories():
    return list(Category.objects.filter(items__isnull=False).distinct())

@sync_to_async
def get_items_by_category(slug):
    return list(MenuItem.objects.filter(category__slug=slug, is_available=True))

@sync_to_async
def get_user_orders(user):
    return list(
        Order.objects
        .filter(user=user)
        .prefetch_related('items__item')  # опционально: для деталей
        .order_by('-created_at')[:10]  # последние 10 заказов
    )

@sync_to_async
def add_item_to_cart_db(user, item_id):
    logger.info(f"Добавление товара {item_id} в корзину пользователя {user.chat_id}")
    try:
        # ✅ select_related здесь — безопасно, т.к. внутри sync_to_async
        item = MenuItem.objects.select_related('category').get(id=item_id)
        cart, _ = Cart.objects.get_or_create(user=user)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, item=item, defaults={'quantity': 1}
        )
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        logger.info(f"Товар '{item.name}' добавлен. Количество: {cart_item.quantity}")
        return item.name
    except Exception as e:
        logger.error(f"Ошибка при добавлении в корзину: {e}")
        raise

async def decrease_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        item_id = int(query.data.split('_', 1)[1])
    except (ValueError, IndexError):
        await query.answer("❌ Ошибка ID", show_alert=True)
        return

    chat_id = update.effective_chat.id
    user = await get_or_create_user(chat_id)

    try:
        cart_item = await sync_to_async(
            CartItem.objects.select_related('item').get
        )(id=item_id, cart__user=user)

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            await sync_to_async(cart_item.save)()
        else:
            await sync_to_async(cart_item.delete)()

        # Перезагружаем и показываем корзину
        await show_cart(update, context)

    except CartItem.DoesNotExist:
        await query.answer("❌ Товар уже удалён.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка уменьшения количества: {e}")
        await query.answer("⚠️ Не удалось изменить количество.", show_alert=True)

async def remove_from_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        item_id = int(query.data.split('_', 1)[1])
    except (ValueError, IndexError):
        await query.answer("❌ Некорректный ID", show_alert=True)
        return

    chat_id = update.effective_chat.id
    user = await get_or_create_user(chat_id)

    try:
        deleted, _ = await sync_to_async(
            CartItem.objects.filter(id=item_id, cart__user=user).delete)()

        if deleted == 0:
            await query.answer("❌ Товар не найден.", show_alert=True)
        else:
            await show_cart(update, context)  # ← обновить корзину
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        await query.answer("⚠️ Не удалось удалить товар.", show_alert=True)

@sync_to_async
def get_user_cart(user):
    try:
        # ❗ Используем select_related('item'), чтобы избежать N+1 и ленивой загрузки
        cart = Cart.objects.select_related('user').get(user=user)
        items = list(cart.items.select_related('item').all())  # ← select_related('item')!
        return cart, items
    except Cart.DoesNotExist:
        return None, []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await get_or_create_user(chat_id, update.effective_user.username)

    categories = await get_all_categories()
    keyboard = [
        [InlineKeyboardButton(f"{cat.emoji} {cat.name}", callback_data=f'menu_{cat.slug}')]
        for cat in categories
    ]
    keyboard += [
        [InlineKeyboardButton("🛒 Корзина", callback_data='cart')],
        [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("ℹ️ О кофейне", callback_data='info')],
    ]

    text = "🌟 Добро пожаловать в *Coffee House Bot*!\n\nВыберите категорию:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        # От callback query — редактируем или отправляем новое
        try:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # ← всегда отвечаем на callback

    slug = query.data.split('_', 1)[1]
    items = await get_items_by_category(slug)

    if not items:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='start')]]
        # ❌ НЕ редактируем — а отправляем новое сообщение
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="В этой категории пока нет доступных товаров.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"{i.name} — {i.price}₽", callback_data=f'item_{i.id}')]
        for i in items
    ]
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='start')])

    # ✅ Отправляем НОВОЕ сообщение вместо редактирования
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📜 Меню: *{next((c.name for c in await get_all_categories() if c.slug == slug), slug)}*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

    # ✅ Опционально: удалить старое сообщение (но осторожно!)
    try:
        await query.message.delete()
    except BadRequest as e:
        if "Message can't be deleted" not in str(e):
            logger.warning(f"Не удалось удалить старое сообщение: {e}")

async def show_item_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # обязательно — чтобы "часики" пропали

    item_id = int(query.data.split('_')[1])
    item = await sync_to_async(MenuItem.objects.select_related('category').get)(id=item_id)

    # Формируем подпись
    caption = f"*{item.name}*\n\n"
    if item.description:
        caption += f"{item.description[:900]}\n\n"
    caption += f"Цена: *{item.price}₽*"

    keyboard = [
        [InlineKeyboardButton("➕ Добавить в корзину", callback_data=f'add_{item.id}')],
        [InlineKeyboardButton("🔙 Назад к меню", callback_data=f'menu_{item.category.slug}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    chat_id = update.effective_chat.id

    try:
        # ✅ Проверяем изображение
        if item.image and os.path.exists(item.image.path):
            # 📸 Отправляем НОВОЕ сообщение с фото (не редактируем и не удаляем старое!)
            with open(item.image.path, 'rb') as photo_file:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_file,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            # ✅ Опционально: отредактировать старое сообщение → "Подробнее → фото отправлено выше"
            try:
                await query.edit_message_text(
                    "📸 *Фото товара отправлено выше 👆*",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад", callback_data=f'menu_{item.category.slug}')
                    ]]),
                    parse_mode=ParseMode.MARKDOWN
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning(f"Не удалось обновить старое сообщение: {e}")
            return

        # 📝 Если фото нет — редактируем как раньше
        await query.edit_message_text(
            caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.error(f"Ошибка при отправке товара {item_id}: {e}")
        # Отправляем текстом в любом случае
        fallback = f"⚠️ Ошибка загрузки фото.\n\n{caption}"
        await context.bot.send_message(
            chat_id=chat_id,
            text=fallback,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    item_id = int(query.data.split('_')[1])
    chat_id = update.effective_chat.id
    user = await get_or_create_user(chat_id)
    
    # Добавляем в корзину и получаем имя товара
    item_name = await add_item_to_cart_db(user, item_id)
    
    keyboard = [
        [InlineKeyboardButton("🛒 В корзину", callback_data='cart')],
        [InlineKeyboardButton("➕ Ещё один", callback_data=f'add_{item_id}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='start')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"✅ *{item_name}* добавлен в корзину!"
    
    # ✅ ИСПОЛЬЗУЕМ safe_edit_or_send вместо query.edit_message_text
    await safe_edit_or_send(
        query,
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    user = await get_or_create_user(chat_id)
    cart, items = await get_user_cart(user)
    
    # === СЛУЧАЙ 1: корзина пуста ===
    if not items:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='start')]]
        try:
            await safe_edit_or_send(
                query,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                # Игнорируем — сообщение уже актуально
                logger.debug("Ignored 'Message is not modified' error")
            else:
                raise  # поднимаем остальные ошибки

    # === СЛУЧАЙ 2: есть товары — формируем продвинутую клавиатуру ===
    message = "🛒 *Ваша корзина:*\n\n"
    total = 0
    keyboard = []

    for item in items:
        item_total = item.item.price * item.quantity
        total += item_total
        message += f"• {item.item.name} ×{item.quantity} = {item_total}₽\n"

        # === Кнопки управления ПОД каждым товаром ===
        item_text = f"{item.item.name} ×{item.quantity}"
        keyboard.append([InlineKeyboardButton(item_text, callback_data="noop")])

        # Кнопки: [➖] [число] [➕] и [🗑️], если нужно
        btn_row = []
        # Кнопка уменьшения или удаления
        if item.quantity > 1:
            btn_row.append(InlineKeyboardButton("➖", callback_data=f"decrease_{item.id}"))
        else:
            btn_row.append(InlineKeyboardButton("🗑️", callback_data=f"remove_{item.id}"))
        
        btn_row.append(InlineKeyboardButton(str(item.quantity), callback_data="noop"))
        btn_row.append(InlineKeyboardButton("➕", callback_data=f"add_{item.item.id}"))
        
        keyboard.append(btn_row)

    message += f"\n*Итого: {total}₽*"

    # Общие кнопки
    keyboard.append([InlineKeyboardButton("🧹 Очистить корзину", callback_data="clear_cart")])
    keyboard.append([
        InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout"),
        InlineKeyboardButton("🔙 Назад", callback_data="start")
    ])

    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    user = await get_or_create_user(chat_id)
    orders = await get_user_orders(user)

    if not orders:
        text = "📭 У вас пока нет заказов.\n\nСделайте первый заказ — мы приготовим его с любовью! ☕"
        keyboard = []
        for order in orders[:5]:  # показываем кнопки только для первых 5 (чтобы не перегружать)
            status_short = {'pending': '⏳', 'confirmed': '✅', 'completed': '✔️', 'canceled': '❌'}.get(order.status, '❓')
            btn_text = f"{status_short} Заказ #{order.id} — {order.total_price}₽"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'order_{order.id}')])

        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='start')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Формируем список заказов
    text = "📋 *Ваши заказы:*\n\n"
    for order in orders:
        # Статус (можно добавить в модель Order.choices, но пока просто текст)
        status_map = {
            'pending': '⏳ Обрабатывается',
            'confirmed': '✅ Подтверждён',
            'completed': '📦 Выполнен',
            'canceled': '❌ Отменён',
        }
        status = status_map.get(order.status, order.status)

        text += (
            f"• *Заказ #{order.id}*\n"
            f"  💰 {order.total_price}₽ | {status}\n"
            f"  📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )

    keyboard = [
        [InlineKeyboardButton("🔍 Подробности заказа", callback_data='order_details_info')],
        [InlineKeyboardButton("🔙 Назад", callback_data='start')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def show_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        order_id = int(query.data.split('_', 1)[1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Неверный ID заказа.")
        return

    chat_id = update.effective_chat.id
    user = await get_or_create_user(chat_id)

    try:
        # Получаем заказ с проверкой принадлежности
        order = await sync_to_async(
            Order.objects.select_related('user')
            .prefetch_related('items__item')
            .get
        )(id=order_id, user=user)
    except Order.DoesNotExist:
        await query.edit_message_text("🔒 Заказ не найден или не принадлежит вам.")
        return

    # Формируем детали
    status_map = {
        'pending': '⏳ Обрабатывается',
        'confirmed': '✅ Подтверждён менеджером',
        'completed': '📦 Заказ выполнен',
        'canceled': '❌ Отменён',
    }
    status = status_map.get(order.status, order.status)

    text = f"📦 *Заказ #{order.id}*\n\n"
    text += f"**Статус:** {status}\n"
    text += f"**Сумма:** {order.total_price}₽\n"
    text += f"**Дата:** {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"

    if order.order_type == 'delivery':
        text += f"**Тип:** Доставка\n"
        if order.address:
            text += f"**Адрес:** {order.address}\n"
    else:
        text += f"**Тип:** Самовывоз\n"

    text += "\n**Состав заказа:**\n"
    for item in order.items.all():
        text += f"• {item.item.name} ×{item.quantity} — {item.item.price}₽\n"

    keyboard = [[InlineKeyboardButton("🔙 Назад к заказам", callback_data='my_orders')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # просто закрываем "часики", ничего не делаем

async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🏠 Доставка", callback_data='delivery')],
        [InlineKeyboardButton("🏪 Самовывоз", callback_data='pickup')],
        [InlineKeyboardButton("🔙 Назад", callback_data='cart')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ✅ Безопасная отправка
    await safe_edit_or_send(
        query,
        "🚚 *Выберите способ получения заказа:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return ORDER_TYPE

async def order_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['order_type'] = query.data
    
    if query.data == 'delivery':
        # ✅ Отправляем запрос адреса как НОВОЕ сообщение (не редактируем!)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🏠 *Введите адрес доставки:*",
            parse_mode="Markdown"
        )
        return ADDRESS
    else:
        # Для самовывоза — сразу создаём заказ
        return await create_order(update, context)

async def address_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['address'] = update.message.text
    return await create_order(update, context)

@sync_to_async
def create_order_in_db(user, order_type, address, items):
    total = sum(item.item.price * item.quantity for item in items)
    
    order = Order.objects.create(
        user=user,
        order_type=order_type,
        address=address if order_type == 'delivery' else None,
        total_price=total
    )
    
    for item in items:
        OrderItem.objects.create(
            order=order,
            item=item.item,
            quantity=item.quantity
        )
    
    # Очистка корзины
    Cart.objects.filter(user=user).delete()
    
    return order

async def create_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = await get_or_create_user(chat_id)
    cart, items = await get_user_cart(user)
    
    if not items:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Ваша корзина пуста! Сначала добавьте товары.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В меню", callback_data='start')
            ]])
        )
        return ConversationHandler.END
    
    order_type = context.user_data['order_type']
    address = context.user_data.get('address', '')
    
    order = await create_order_in_db(user, order_type, address, items)
    
    # Формирование сообщения о заказе
    order_type_text = "Доставка" if order_type == 'delivery' else "Самовывоз"
    message = (
        f"✅ *Заказ #{order.id} успешно оформлен!*\n\n"
        f"*Тип заказа:* {order_type_text}\n"
    )
    
    if address:
        message += f"*Адрес:* {address}\n"
    
    message += (
        f"*Сумма:* {order.total_price}₽\n\n"
        "⏳ В ближайшее время с вами свяжется оператор для подтверждения заказа.\n\n"
        "Благодарим за выбор Coffee House! 😊"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 В главное меню", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        query = update.callback_query
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    return ConversationHandler.END

async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    info = (
        "ℹ️ *О нашей кофейне*\n\n"
        "☕ *Coffee House* — место, где рождается настроение!\n\n"
        "📍 *Адрес:* ул. Ароматная, 42\n"
        "🕒 *Режим работы:*\n"
        "   Пн-Пт: 8:00 - 22:00\n"
        "   Сб-Вс: 9:00 - 23:00\n\n"
        "📞 *Телефон:* +7 (XXX) XXX-XX-XX\n"
        "🌐 *Сайт:* coffeehouse.example.com"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        info,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def safe_edit_or_send(query: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except BadRequest as e:
        error_msg = str(e).lower()
        # 1. Нет текста (медиа-сообщение)
        if "there is no text in the message to edit" in error_msg:
            await query.get_bot().send_message(
                chat_id=query.message.chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            try:
                await query.message.delete()
            except BadRequest:
                pass
        # 2. Сообщение не изменилось → просто игнорируем
        elif "message is not modified" in error_msg:
            # ✅ Ничего не делаем — сообщение уже актуально
            logger.debug("Ignored 'Message is not modified'")
        else:
            raise  # поднимаем другие ошибки

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    user = await get_or_create_user(chat_id)
    
    try:
        await sync_to_async(Cart.objects.filter(user=user).delete)()
        message = "✅ Корзина успешно очищена!"
    except Exception as e:
        logger.error(f"Ошибка при очистке корзины: {e}")
        message = "❌ Не удалось очистить корзину. Попробуйте позже."

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # ✅ Безопасная отправка
    await safe_edit_or_send(
        query,
        message,
        reply_markup=reply_markup
    )

def register_handlers(application):
    """Регистрация всех обработчиков бота"""
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    
    # Обработчики кнопок меню
    application.add_handler(CallbackQueryHandler(start, pattern='^start$'))
    application.add_handler(CallbackQueryHandler(show_menu, pattern='^menu_'))
    application.add_handler(CallbackQueryHandler(show_item_details, pattern='^item_\\d+$'))
    application.add_handler(CallbackQueryHandler(add_to_cart, pattern='^add_\\d+$'))
    application.add_handler(CallbackQueryHandler(show_cart, pattern='^cart$'))
    application.add_handler(CallbackQueryHandler(show_info, pattern='^info$'))
    application.add_handler(CallbackQueryHandler(clear_cart, pattern='^clear_cart$'))
    application.add_handler(CallbackQueryHandler(show_my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(show_order_details, pattern=r'^order_\d+$'))
    application.add_handler(CallbackQueryHandler(decrease_quantity, pattern=r'^decrease_\d+$'))
    application.add_handler(CallbackQueryHandler(remove_from_cart, pattern=r'^remove_\d+$'))
    application.add_handler(CallbackQueryHandler(noop, pattern='^noop$'))

    # Диалог оформления заказа
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(checkout_start, pattern='^checkout$')],
        states={
            ORDER_TYPE: [CallbackQueryHandler(order_type_selected, pattern='^(delivery|pickup)$')],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_received)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
        per_chat=True,
        per_message=False
    )
    
    application.add_handler(conv_handler)