# bot_app/admin.py
from django.contrib import admin
from .models import TelegramUser, Customer, Category, MenuItem, Cart, CartItem, Order, OrderItem
from django.utils.html import format_html

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'emoji', 'order')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_available', 'image_thumbnail']
    list_filter = ['category', 'is_available']
    readonly_fields = ['image_preview']

    def image_thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px;"/>', obj.image.url)
        return "-"
    image_thumbnail.short_description = "Превью"

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 300px;"/>', obj.image.url)
        return "-"
    image_preview.short_description = "Просмотр"

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'order_type', 'total_price', 'status')
    list_filter = ('order_type', 'status')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'created_at')
    list_filter = ('customer',)

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'item', 'quantity')
    list_filter = ('cart', 'item')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'item', 'quantity')
    list_filter = ('order', 'item')

# Зарегистрируйте остальные модели аналогично
admin.site.register(TelegramUser)
admin.site.register(Customer)