from django.urls import path

from . import factura_views, views

app_name = 'pedidos'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('totales/', views.totales, name='totales'),
    path('<uuid:token>/factura.png', factura_views.factura, name='factura'),
    path('<uuid:token>/verificar/', factura_views.verificar_factura, name='verificar_factura'),
    path('<uuid:token>/', views.confirmacion, name='confirmacion'),
    path('<uuid:token>/transferencia/', views.avisar_transferencia, name='avisar_transferencia'),
]
