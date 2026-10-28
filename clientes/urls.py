from django.urls import path

from . import views

app_name = 'clientes'

urlpatterns = [
    path('', views.cuenta, name='cuenta'),
    path('crear/', views.registro, name='registro'),
    path('entrar/', views.Entrar.as_view(), name='entrar'),
    path('salir/', views.Salir.as_view(), name='salir'),
    path('datos/', views.perfil, name='perfil'),
    path('gustos/', views.gustos, name='gustos'),
    path('direcciones/', views.direcciones, name='direcciones'),
    path('direcciones/<int:pk>/', views.editar_direccion, name='editar_direccion'),
    path('direcciones/<int:pk>/principal/', views.principal_direccion, name='principal_direccion'),
    path('direcciones/<int:pk>/borrar/', views.borrar_direccion, name='borrar_direccion'),
    path('recordatorios/<str:token>/', views.apagar_recordatorios, name='apagar_recordatorios'),
    path('confirmar/', views.confirma_tu_correo, name='confirma_tu_correo'),
    path('confirmar/<str:token>/', views.confirmar_correo, name='confirmar_correo'),
    path('favoritos/', views.favoritos, name='favoritos'),
    path('favoritos/<int:producto_id>/', views.alternar_favorito, name='alternar_favorito'),
    path('clave/', views.CambiarClave.as_view(), name='clave'),
    path('recuperar/', views.Recuperar.as_view(), name='recuperar'),
    path('recuperar/enviado/', views.RecuperarEnviado.as_view(), name='recuperar_enviado'),
    path('recuperar/<uidb64>/<token>/', views.NuevaClave.as_view(), name='nueva_clave'),
    path('recuperar/listo/', views.RecuperarListo.as_view(), name='recuperar_listo'),
]
