from django.urls import path

from . import views

app_name = 'tiendas'

# Enlaces que ya estaban compartidos o indexados antes de las subtiendas.
RUTAS_ANTERIORES = [
    'catalogo/', 'categoria/<slug:slug>/', 'producto/<slug:slug>/', 'carrito/', 'como-comprar/', 'envios-y-retiros/',
]

urlpatterns = [
    path('', views.portada, name='portada'),
    path('tiendas/', views.directorio, name='directorio'),
    path('buscar/', views.buscar, name='buscar'),
    path('sugerencias/', views.sugerencias, name='sugerencias'),
    path('vender/', views.vender, name='vender'),
    path('vender/solicitar/', views.solicitar_tienda, name='solicitar_tienda'),
    path('vender/solicitud-enviada/', views.solicitud_enviada, name='solicitud_enviada'),
    *[path(ruta, views.enlace_anterior) for ruta in RUTAS_ANTERIORES],
]
