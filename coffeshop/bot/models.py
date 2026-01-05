from django.db import models
from django.contrib.auth.models import User

class TelegramUser(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return f"User {self.chat_id}"

class Customer(models.Model):
    # Может быть связан с User (веб) ИЛИ с TelegramUser (бот)
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE)
    telegram_user = models.OneToOneField(TelegramUser, null=True, blank=True, on_delete=models.CASCADE)
    
    # Общая информация
    phone = models.CharField(max_length=20, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        if self.user:
            return f"Web: {self.user.username}"
        if self.telegram_user:
            return f"TG: {self.telegram_user.name or self.telegram_user.chat_id}"
        return "Unknown"
    
class Category(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField("Слаг", max_length=100, unique=True, blank=True)
    emoji = models.CharField("Эмодзи", max_length=10, blank=True, help_text="Например: ☕, 🍰")
    order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.emoji} {self.name}" if self.emoji else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class MenuItem(models.Model):
    name = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField("Цена", max_digits=6, decimal_places=2)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Категория"
    )
    image = models.ImageField(
        "Изображение",
        upload_to='menu_items/',      # сохраняется в MEDIA_ROOT/menu_items/
        blank=True,
        null=True,
        help_text="Рекомендуемый размер: 400x400px"
    )
    is_available = models.BooleanField("Доступен", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Позиция меню"
        verbose_name_plural = "Позиции меню"
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.category.name})"
    
    @property
    def image_url(self):
        """Возвращает URL изображения или None"""
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return None

class Cart(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Корзина клиента"
        verbose_name_plural = "Корзины клиентов"
        ordering = ['customer']

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        verbose_name = "Элементы корзины клиента"
        verbose_name_plural = "Элементы корзин клиентов"
        ordering = ['cart', 'item']

    def total_price(self):
        return self.item.price * self.quantity

class Order(models.Model):
    DELIVERY = 'delivery'
    PICKUP = 'pickup'
    ORDER_TYPES = [
        (DELIVERY, 'Доставка'),
        (PICKUP, 'Самовывоз'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтверждён'),
        ('completed', 'Выполнен'),
        ('canceled', 'Отменён'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=10, choices=ORDER_TYPES)
    address = models.CharField(max_length=255, blank=True, null=True)
    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    class Meta:
        verbose_name = "Заказ клиента"
        verbose_name_plural = "Заказы клиентов"
        ordering = ['customer', 'order_type', 'address', 'total_price', 'status']
    
    def __str__(self):
        return f"Order #{self.id} - {self.get_order_type_display()}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Элемент заказа клиента"
        verbose_name_plural = "Элементы заказов клиентов"
        ordering = ['order', 'item']