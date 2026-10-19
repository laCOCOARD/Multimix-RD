from django.urls import path

from tiendas.decoradores import RUTA_DE_TIENDA

from . import factura_views, views

app_name = 'pedidos'

urlpatterns = [
    # El pedido se hace dentro de una tienda, con el carrito de esa tienda.
    path(RUTA_DE_TIENDA + 'pedido/checkout/', views.checkout, name='checkout'),
    path(RUTA_DE_TIENDA + 'pedido/totales/', views.totales, name='totales'),
    # Despues el cliente lo consulta con su enlace privado; el token ya dice de que tienda es.
    path('pedido/<uuid:token>/factura.png', factura_views.factura, name='factura'),
    path('pedido/<uuid:token>/verificar/', factura_views.verificar_factura_anterior, name='verificar_factura_anterior'),
    # El QR de la factura: un codigo firmado que solo sirve para verificar (no es el token del pedido).
    path('factura/<str:codigo>/', factura_views.verificar_factura, name='verificar_factura'),
    path('pedido/<uuid:token>/', views.confirmacion, name='confirmacion'),
    path('pedido/<uuid:token>/transferencia/', views.avisar_transferencia, name='avisar_transferencia'),
    path('pedido/<uuid:token>/cancelar/', views.cancelar, name='cancelar'),
    path('pedido/<uuid:token>/devolucion/', views.pedir_devolucion, name='pedir_devolucion'),
]
