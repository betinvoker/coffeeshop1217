# bot_app/admin.py
from django.contrib import admin
from .models import TelegramUser, Category, MenuItem, Cart, CartItem, Order, OrderItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'emoji', 'order')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available')
    list_filter = ('category', 'is_available')
    search_fields = ('name',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'order_type', 'total_price', 'status')
    list_filter = ('order_type', 'status')

# Зарегистрируйте остальные модели аналогично
admin.site.register(TelegramUser)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(OrderItem)