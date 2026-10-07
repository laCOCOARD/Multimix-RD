from django.urls import path

from . import views

app_name = 'tiendas'

# Enlaces que ya estaban compartidos o indexados antes de las subtiendas.
RUTAS_ANTERIORES = [
    'catalogo/', 'categoria/<slug:slug>/', 'producto/<slug:slug>/', 'carrito/', 'como-comprar/', 'envios-y-retiros/',
]

urlpatterns = [
    path('', views.portada, name='portada'),
    path('buscar/', views.buscar, name='buscar'),
    *[path(ruta, views.enlace_anterior) for ruta in RUTAS_ANTERIORES],
]
