from django.urls import path

from tiendas.decoradores import RUTA_DE_TIENDA

from . import views

app_name = 'core'

urlpatterns = [
    # Cada tienda explica como cobra y a donde envia.
    path(RUTA_DE_TIENDA + 'como-comprar/', views.como_comprar, name='como_comprar'),
    path(RUTA_DE_TIENDA + 'envios-y-retiros/', views.envios, name='envios'),
    path('terminos/', views.terminos, name='terminos'),
    path('robots.txt', views.robots_txt, name='robots'),
]
