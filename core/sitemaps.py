from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalogo.models import Categoria, Producto


class PaginasSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return ['catalogo:inicio', 'catalogo:lista', 'core:como_comprar', 'core:envios']

    def location(self, item):
        return reverse(item)


class CategoriasSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Categoria.objects.filter(activa=True)


class ProductosSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        return Producto.objects.activos().order_by('-actualizado')

    def lastmod(self, producto):
        return producto.actualizado


SITEMAPS = {
    'paginas': PaginasSitemap,
    'categorias': CategoriasSitemap,
    'productos': ProductosSitemap,
}
