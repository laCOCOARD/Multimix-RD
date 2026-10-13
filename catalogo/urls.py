from django.urls import path

from . import views

app_name = 'catalogo'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('catalogo/', views.lista, name='lista'),
    path('sugerencias/', views.sugerencias, name='sugerencias'),
    path('categoria/<slug:slug>/', views.lista, name='categoria'),
    path('producto/<slug:slug>/', views.producto, name='producto'),
]
