from django.urls import path

from . import views

app_name = 'pedidos'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('totales/', views.totales, name='totales'),
    path('<uuid:token>/', views.confirmacion, name='confirmacion'),
    path('<uuid:token>/transferencia/', views.avisar_transferencia, name='avisar_transferencia'),
]
