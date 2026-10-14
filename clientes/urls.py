from django.urls import path

from . import views

app_name = 'clientes'

urlpatterns = [
    path('', views.cuenta, name='cuenta'),
    path('crear/', views.registro, name='registro'),
    path('entrar/', views.Entrar.as_view(), name='entrar'),
    path('salir/', views.Salir.as_view(), name='salir'),
    path('datos/', views.perfil, name='perfil'),
    path('favoritos/', views.favoritos, name='favoritos'),
    path('favoritos/<int:producto_id>/', views.alternar_favorito, name='alternar_favorito'),
    path('clave/', views.CambiarClave.as_view(), name='clave'),
    path('recuperar/', views.Recuperar.as_view(), name='recuperar'),
    path('recuperar/enviado/', views.RecuperarEnviado.as_view(), name='recuperar_enviado'),
    path('recuperar/<uidb64>/<token>/', views.NuevaClave.as_view(), name='nueva_clave'),
    path('recuperar/listo/', views.RecuperarListo.as_view(), name='recuperar_listo'),
]
