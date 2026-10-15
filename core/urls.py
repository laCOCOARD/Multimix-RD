from django.urls import path
from django.views.generic import RedirectView

from tiendas.decoradores import RUTA_DE_TIENDA

from . import views

app_name = 'core'

urlpatterns = [
    # La guia "Como comprar" se quito: su enlace lleva al inicio de la tienda.
    path(RUTA_DE_TIENDA + 'como-comprar/', RedirectView.as_view(pattern_name='catalogo:inicio', permanent=True)),
    # Cada tienda explica a donde envia.
    path(RUTA_DE_TIENDA + 'envios-y-retiros/', views.envios, name='envios'),
    path('terminos/', views.terminos, name='terminos'),
    path('pagina/<slug:slug>/', views.pagina, name='pagina'),
    path('preguntas-frecuentes/', views.preguntas, name='preguntas'),
    path('robots.txt', views.robots_txt, name='robots'),
    path('salud/', views.salud, name='salud'),
]
