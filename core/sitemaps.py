from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalogo.models import Producto
from tiendas.models import Tienda


class PaginasSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return ['tiendas:portada', 'tiendas:buscar', 'core:terminos']

    def location(self, item):
        return reverse(item)


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
    'tiendas': TiendasSitemap,
    'productos': ProductosSitemap,
}
