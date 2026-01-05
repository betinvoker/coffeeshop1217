from django.urls import path
from . import views

app_name = 'web_app'

urlpatterns = [
    path('', views.menu_view, name='menu'),
    path('add-to-cart/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart'),
    path('order/', views.create_order, name='create_order'),
    path('order/success/', views.order_success, name='order_success'),
]