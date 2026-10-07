from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from catalogo.forms import ORDENES, FiltroCatalogoForm
from catalogo.services import filtrar_catalogo

from . import services

RESULTADOS_POR_PAGINA = 12


@require_GET
def portada(request):
    """Directorio de tiendas: desde aqui el cliente entra a comprar en una."""
    return render(request, 'tiendas/portada.html', {'tiendas': services.directorio()})


@require_GET
def buscar(request):
    """Buscador del sitio: productos de todas las tiendas. Cada resultado se compra dentro de su tienda."""
    filtros = FiltroCatalogoForm(request.GET).filtros()
    pagina = Paginator(filtrar_catalogo(filtros), RESULTADOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'tiendas/buscar.html', {
        'filtros': filtros,
        'ordenes': ORDENES,
        'orden_actual': filtros.get('orden') or 'nuevos',
        'pagina': pagina,
    })


@require_GET
def enlace_anterior(request, **kwargs):
    """Rutas de cuando habia una sola tienda (/catalogo/, /producto/x/): llevan a la tienda principal."""
    principal = services.tienda_principal()
    if principal is None:
        raise Http404
    destino = principal.get_absolute_url().rstrip('/') + request.path
    consulta = request.META.get('QUERY_STRING')
    return redirect(f'{destino}?{consulta}' if consulta else destino)
