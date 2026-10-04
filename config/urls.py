from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core.sitemaps import SITEMAPS

urlpatterns = [
    path(f'{settings.ADMIN_URL}/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('carrito/', include('carrito.urls')),
    path('pedido/', include('pedidos.urls')),
    path('', include('core.urls')),
    path('', include('catalogo.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
