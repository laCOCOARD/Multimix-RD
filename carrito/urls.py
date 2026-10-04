from django.urls import path

from . import views

app_name = 'carrito'

urlpatterns = [
    path('', views.detalle, name='detalle'),
    path('agregar/', views.agregar, name='agregar'),
    path('actualizar/', views.actualizar, name='actualizar'),
    path('eliminar/', views.eliminar, name='eliminar'),
    path('cupon/aplicar/', views.cupon_aplicar, name='cupon_aplicar'),
    path('cupon/quitar/', views.cupon_quitar, name='cupon_quitar'),
]
