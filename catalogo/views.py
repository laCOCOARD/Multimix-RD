from django.core.paginator import Paginator
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from clientes.services import es_favorito
from core.templatetags.moneda import formatear_monto
from opiniones import services as opiniones

from pedidos.whatsapp import construir_enlace
from tiendas.decoradores import de_tienda
from tiendas.services import banners_de

from . import services
from .forms import ORDENES, FiltroCatalogoForm
from .models import Categoria, Producto

PRODUCTOS_POR_PAGINA = 12
OPCIONES_ESTRELLAS = [
    (5, '5 estrellas · Excelente'), (4, '4 estrellas · Muy bueno'), (3, '3 estrellas · Bueno'),
    (2, '2 estrellas · Regular'), (1, '1 estrella · Malo'),
]


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
        'banners': banners_de(tienda),
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
        'marcas': services.marcas_de(request.tienda, categoria),
        'filtros': filtros,
        'ordenes': ORDENES,
        'orden_actual': filtros.get('orden') or 'nuevos',
        'pagina': pagina,
        'hay_filtros': any(filtros.get(c) for c in ('q', 'marca', 'precio_min', 'precio_max', 'oferta', 'disponibles')),
    })


def respuesta_de_sugerencias(productos, con_tienda=False):
    """JSON del desplegable del buscador. `con_tienda` agrega de que tienda es cada producto."""
    resultados = []
    for item in productos:
        foto = item.foto_principal
        resultados.append({
            'nombre': item.nombre,
            'url': item.get_absolute_url(),
            'precio': formatear_monto(item.precio_final),
            'foto': foto.imagen.url if foto else '',
            'tienda': item.tienda.nombre if con_tienda else '',
        })
    return JsonResponse({'resultados': resultados})


@require_GET
@de_tienda
def sugerencias(request):
    return respuesta_de_sugerencias(services.sugerencias(request.GET.get('q', '')[:80], request.tienda))


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
        'es_favorito': es_favorito(request.user, item),
        'resenas': opiniones.publicadas(item),
        'resumen_resenas': opiniones.resumen(item),
        'mi_resena': opiniones.resena_de(request.user, item),
        'opciones_estrellas': OPCIONES_ESTRELLAS,
        'cantidad_maxima': item.limite_compra,
        'url_absoluta': url_absoluta,
        'og_imagen': request.build_absolute_uri(foto.imagen.url) if foto else '',
        'enlace_consulta': construir_enlace(tienda.whatsapp, consulta) if tienda.whatsapp else '',
    })


@require_POST
@login_required
@de_tienda
def opinar(request, slug):
    """Reseña de un cliente con cuenta. Queda por revisar: no se publica sola."""
    item = get_object_or_404(Producto.objects.activos(), tienda=request.tienda, slug=slug)
    try:
        opiniones.guardar_resena(request.user, item, request.POST.get('estrellas'), request.POST.get('comentario'))
    except opiniones.ResenaError as error:
        messages.error(request, error.mensaje)
    else:
        messages.success(request, 'Gracias por tu opinión. La publicamos en cuanto la revisemos.')
    return redirect(item.get_absolute_url() + '#opiniones')
