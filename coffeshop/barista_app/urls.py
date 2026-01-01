from django.urls import path
from . import views

app_name = 'barista_app'

urlpatterns = [
    path('', views.order_panel, name='order_panel'),
]