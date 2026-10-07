from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from pedidos.whatsapp import construir_enlace
from tiendas.decoradores import de_tienda

from . import services
from .forms import ORDENES, FiltroCatalogoForm
from .models import Categoria, Producto

PRODUCTOS_POR_PAGINA = 12


@de_tienda
def inicio(request):
    tienda = request.tienda
    secciones = [
        {'titulo': 'Ofertas', 'icono': 'bi-tag-fill', 'productos': services.en_oferta(tienda), 'enlace': '?oferta=on'},
        {'titulo': 'Destacados', 'icono': 'bi-star-fill', 'productos': services.destacados(tienda), 'enlace': ''},
        {'titulo': 'Nuevos', 'icono': 'bi-stars', 'productos': services.nuevos(tienda), 'enlace': '?orden=nuevos'},
        {'titulo': 'Más vendidos', 'icono': 'bi-fire', 'productos': services.mas_vendidos(tienda), 'enlace': '?orden=vendidos'},
    ]
    return render(request, 'catalogo/inicio.html', {
        'secciones': [s for s in secciones if s['productos']],
        'categorias': services.categorias_de_portada(tienda),
    })


@de_tienda
def lista(request, slug=None):
    categoria = get_object_or_404(Categoria, slug=slug, activa=True) if slug else None
    formulario = FiltroCatalogoForm(request.GET)
    filtros = formulario.filtros()
    productos = services.filtrar_catalogo(filtros, categoria, request.tienda)
    pagina = Paginator(productos, PRODUCTOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'catalogo/lista.html', {
        'categoria': categoria,
        'categorias': services.categorias_de(request.tienda),
        'filtros': filtros,
        'ordenes': ORDENES,
        'orden_actual': filtros.get('orden') or 'nuevos',
        'pagina': pagina,
        'hay_filtros': any(filtros.get(c) for c in ('q', 'precio_min', 'precio_max', 'oferta', 'disponibles')),
    })


@de_tienda
def producto(request, slug):
    tienda = request.tienda
    item = get_object_or_404(Producto.objects.activos().para_listado(), tienda=tienda, slug=slug)
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
