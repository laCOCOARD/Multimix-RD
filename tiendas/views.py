from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from catalogo.forms import ORDENES, FiltroCatalogoForm
from catalogo.services import en_oferta, filtrar_catalogo, nuevos, sugerencias as sugerencias_de_productos
from catalogo.views import respuesta_de_sugerencias
from core.models import ConfiguracionTienda
from core.seo import sitio_json_ld

from . import services

RESULTADOS_POR_PAGINA = 12


@require_GET
def portada(request):
    """Directorio de tiendas: desde aqui el cliente entra a comprar en una."""
    from core.models import PreguntaFrecuente

    return render(request, 'tiendas/portada.html', {
        'tiendas': services.directorio(),
        'preguntas': PreguntaFrecuente.objects.filter(activa=True)[:6],
        'sitio_json_ld': sitio_json_ld(
            ConfiguracionTienda.obtener().nombre, request.build_absolute_uri('/'),
            request.build_absolute_uri(reverse('tiendas:buscar')),
        ),
    })


@require_GET
def buscar(request):
    """Buscador del sitio: productos de todas las tiendas. Cada resultado se compra dentro de su tienda."""
    filtros = FiltroCatalogoForm(request.GET).filtros()
    pagina = Paginator(filtrar_catalogo(filtros), RESULTADOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'tiendas/buscar.html', {
        # Sin resultados no se deja la pagina vacia: se sugieren ofertas o lo nuevo.
        'sugeridos': (en_oferta(None, limite=10) or nuevos(None, limite=10)) if not pagina.object_list else [],
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
