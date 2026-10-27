from django.urls import path

from . import views

app_name = 'planes'

urlpatterns = [
    path('videos/<int:pk>/vista/', views.vista_de_video, name='vista_de_video'),
]
