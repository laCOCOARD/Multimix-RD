from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalogo.models import Producto

from .models import PaginaInformativa
from tiendas.models import Tienda


class PaginasSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return ['tiendas:portada', 'tiendas:directorio', 'tiendas:buscar', 'tiendas:vender', 'core:terminos']

    def location(self, item):
        return reverse(item)


class PaginasInformativasSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.4

    def items(self):
        return PaginaInformativa.objects.filter(publicada=True)

    def lastmod(self, pagina):
        return pagina.actualizado


class TiendasSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return Tienda.objects.activas()


class ProductosSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        return Producto.objects.activos().select_related('tienda').order_by('-actualizado')

    def lastmod(self, producto):
        return producto.actualizado


SITEMAPS = {
    'paginas': PaginasSitemap,
    'informativas': PaginasInformativasSitemap,
    'tiendas': TiendasSitemap,
    'productos': ProductosSitemap,
}
