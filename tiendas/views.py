from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET

from catalogo.forms import ORDENES, FiltroCatalogoForm
from catalogo.models import Categoria
from catalogo.services import (
    categorias_del_sitio, en_oferta, filtrar_catalogo, nuevos, ofertas_del_sitio, sugerencias as sugerencias_de_productos,
    vitrina_del_sitio,
)
from catalogo.views import respuesta_de_sugerencias
from core.models import ConfiguracionTienda
from core.seo import sitio_json_ld

from . import services

RESULTADOS_POR_PAGINA = 12
TIENDAS_EN_PORTADA = 8
PRODUCTOS_EN_PORTADA = 12
TIENDAS_POR_PAGINA = 24


@require_GET
def portada(request):
    """Portada del sitio: productos de todas las tiendas y las tiendas mismas, para comprar sin conocer al vendedor
    o para entrar a la tienda de un emprendedor. Cada producto se sigue comprando dentro de su tienda."""
    from core.models import PreguntaFrecuente

    tiendas = list(services.directorio()[:TIENDAS_EN_PORTADA + 1])
    ofertas = ofertas_del_sitio()
    # Lo que ya sale en ofertas no se repite en la seleccion.
    productos = vitrina_del_sitio(PRODUCTOS_EN_PORTADA, excluir=[producto.pk for producto in ofertas])
    plataforma = ConfiguracionTienda.obtener()
    return render(request, 'tiendas/portada.html', {
        'tiendas': services.para_el_directorio(tiendas[:TIENDAS_EN_PORTADA]),
        'hay_mas_tiendas': len(tiendas) > TIENDAS_EN_PORTADA,
        'categorias': categorias_del_sitio(),
        'productos': productos,
        'ofertas': ofertas,
        # Fotos reales para el bloque de bienvenida (en pantallas anchas): los ultimos de la seleccion con foto.
        'vitrina': [producto for producto in productos if producto.foto_principal][-4:],
        'preguntas': PreguntaFrecuente.objects.filter(activa=True)[:6],
        'sitio_json_ld': sitio_json_ld(
            plataforma.nombre, request.build_absolute_uri('/'),
            request.build_absolute_uri(reverse('tiendas:buscar')),
            logo=request.build_absolute_uri(static('img/icono-512.png')),
        ),
    })


@require_GET
def directorio(request):
    """Todas las tiendas activas, por paginas: la portada muestra solo las primeras."""
    pagina = Paginator(services.directorio(), TIENDAS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'tiendas/directorio.html', {
        'pagina': pagina,
        'tiendas': services.para_el_directorio(pagina.object_list),
    })


@require_GET
def buscar(request):
    """Buscador del sitio: productos de todas las tiendas. Cada resultado se compra dentro de su tienda.

    `?categoria=<slug>` limita a una categoria (con sus subcategorias): es a donde llevan las categorias de la portada.
    """
    filtros = FiltroCatalogoForm(request.GET).filtros()
    slug = request.GET.get('categoria', '')[:100]
    # Una categoria que no existe o esta apagada se ignora, como los demas filtros que no valen.
    categoria = Categoria.objects.filter(slug=slug, activa=True).first() if slug else None
    pagina = Paginator(filtrar_catalogo(filtros, categoria), RESULTADOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'tiendas/buscar.html', {
        # Sin resultados no se deja la pagina vacia: se sugieren ofertas o lo nuevo.
        'sugeridos': (en_oferta(None, limite=10) or nuevos(None, limite=10)) if not pagina.object_list else [],
        'categoria': categoria,
        'filtros': filtros,
        'ordenes': ORDENES,
        'orden_actual': filtros.get('orden') or 'nuevos',
        'pagina': pagina,
    })


@require_GET
def sugerencias(request):
    """Sugerencias del buscador del sitio: productos de todas las tiendas activas."""
    productos = sugerencias_de_productos(request.GET.get('q', '')[:80])
    return respuesta_de_sugerencias(productos, con_tienda=True)


@require_GET
def enlace_anterior(request, **kwargs):
    """Rutas de cuando habia una sola tienda (/catalogo/, /producto/x/): llevan a la tienda principal."""
    principal = services.tienda_principal()
    if principal is None:
        raise Http404
    destino = principal.get_absolute_url().rstrip('/') + request.path
    consulta = request.META.get('QUERY_STRING')
    return redirect(f'{destino}?{consulta}' if consulta else destino)
