from django.urls import path
from . import views

app_name = 'barista_app'

urlpatterns = [
    path('', views.order_panel, name='order_panel'),
    path('accept/', views.accept_order, name='accept_order'),
    path('accept/cart/add/', views.cart_add, name='cart_add'),
    path('accept/cart/update/', views.cart_update, name='cart_update'),
    path('accept/cart/clear/', views.cart_clear, name='cart_clear'),
    path('accept/create/', views.create_order, name='create_order'),
    path('update/<int:order_id>/<str:status>/', views.update_status, name='update_status'),
]