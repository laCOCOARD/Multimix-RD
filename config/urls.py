from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core.sitemaps import SITEMAPS
from tiendas.decoradores import RUTA_DE_TIENDA

urlpatterns = [
    path(f'{settings.ADMIN_URL}/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    # Dentro de una tienda: su catalogo y su carrito.
    path(RUTA_DE_TIENDA + 'carrito/', include('carrito.urls')),
    path(RUTA_DE_TIENDA, include('catalogo.urls')),
    # Estas apps mezclan rutas de tienda y del sitio; cada una declara las suyas completas.
    path('', include('pedidos.urls')),
    path('', include('core.urls')),
    path('', include('tiendas.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
