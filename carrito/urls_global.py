from django.urls import path

from . import views_global

app_name = 'carrito_global'

urlpatterns = [
    path('', views_global.carrito_global, name='global'),
    path('checkout/', views_global.checkout_global, name='checkout_global'),
    path('confirmacion/<uuid:grupo>/', views_global.confirmacion_global, name='confirmacion_global'),
    path('pago/<uuid:grupo>/comprobante/', views_global.aviso_transferencia_global, name='aviso_transferencia_global'),
]
