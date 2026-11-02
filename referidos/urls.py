from django.urls import path

from . import views

app_name = 'referidos'

urlpatterns = [
    path('ref/<slug:codigo>/', views.registrar_clic, name='clic'),
]
