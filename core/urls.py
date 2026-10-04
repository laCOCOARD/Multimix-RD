from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('como-comprar/', views.como_comprar, name='como_comprar'),
    path('envios-y-retiros/', views.envios, name='envios'),
    path('robots.txt', views.robots_txt, name='robots'),
]
