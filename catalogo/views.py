from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from core.models import ConfiguracionTienda
from pedidos.whatsapp import construir_enlace

from . import services
from .forms import ORDENES, FiltroCatalogoForm
from .models import Categoria, Producto

PRODUCTOS_POR_PAGINA = 12


def inicio(request):
    secciones = [
        {'titulo': 'Ofertas', 'icono': 'bi-tag-fill', 'productos': services.en_oferta(), 'enlace': '?oferta=on'},
        {'titulo': 'Destacados', 'icono': 'bi-star-fill', 'productos': services.destacados(), 'enlace': ''},
        {'titulo': 'Nuevos', 'icono': 'bi-stars', 'productos': services.nuevos(), 'enlace': '?orden=nuevos'},
        {'titulo': 'Más vendidos', 'icono': 'bi-fire', 'productos': services.mas_vendidos(), 'enlace': '?orden=vendidos'},
    ]
    return render(request, 'catalogo/inicio.html', {
        'secciones': [s for s in secciones if s['productos']],
        'categorias': Categoria.objects.filter(activa=True),
    })


def lista(request, slug=None):
    categoria = get_object_or_404(Categoria, slug=slug, activa=True) if slug else None
    formulario = FiltroCatalogoForm(request.GET)
    filtros = formulario.filtros()
    productos = services.filtrar_catalogo(filtros, categoria)
    pagina = Paginator(productos, PRODUCTOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'catalogo/lista.html', {
        'categoria': categoria,
        'categorias': Categoria.objects.filter(activa=True),
        'filtros': filtros,
        'ordenes': ORDENES,
        'orden_actual': filtros.get('orden') or 'nuevos',
        'pagina': pagina,
        'hay_filtros': any(filtros.get(c) for c in ('q', 'precio_min', 'precio_max', 'oferta', 'disponibles')),
    })


def producto(request, slug):
    item = get_object_or_404(Producto.objects.activos().para_listado(), slug=slug)
    tienda = ConfiguracionTienda.obtener()
    url_absoluta = request.build_absolute_uri(item.get_absolute_url())
    foto = item.foto_principal
    consulta = f'Hola, me interesa este producto: {item.nombre} (SKU {item.sku})\n{url_absoluta}'
    return render(request, 'catalogo/producto.html', {
        'producto': item,
        'fotos': item.fotos_ordenadas,
        'relacionados': services.relacionados(item),
        'cantidad_maxima': min(item.stock_disponible, settings.CARRITO_MAX_POR_PRODUCTO),
        'url_absoluta': url_absoluta,
        'og_imagen': request.build_absolute_uri(foto.imagen.url) if foto else '',
        'enlace_consulta': construir_enlace(tienda.whatsapp, consulta) if tienda.whatsapp else '',
    })
