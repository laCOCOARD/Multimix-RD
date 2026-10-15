from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from catalogo.forms import ORDENES, FiltroCatalogoForm
from catalogo.services import filtrar_catalogo, sugerencias as sugerencias_de_productos
from catalogo.views import respuesta_de_sugerencias

from . import services

RESULTADOS_POR_PAGINA = 12


# "Compra con tranquilidad" de la portada: cada bloque enlaza su politica si esta publicada.
RESPALDOS = [
    {'slug': 'metodos-de-pago', 'icono': 'bi-credit-card-2-front', 'titulo': 'Pagos claros',
     'texto': 'Transferencia con comprobante o efectivo. Pagas solo a las cuentas que muestra tu pedido.'},
    {'slug': 'entregas', 'icono': 'bi-box-seam', 'titulo': 'Entrega o retiro',
     'texto': 'Recibe en tu casa dentro de las zonas de cada tienda o recoge tu pedido cuando esté listo.'},
    {'slug': 'cambios-y-devoluciones', 'icono': 'bi-arrow-counterclockwise', 'titulo': 'Cambios y devoluciones',
     'texto': 'Si algo no está bien, lo solicitas desde tu pedido y la tienda te responde.'},
]


@require_GET
def portada(request):
    """Directorio de tiendas: desde aqui el cliente entra a comprar en una."""
    from core.models import PreguntaFrecuente

    return render(request, 'tiendas/portada.html', {
        'tiendas': services.directorio(),
        'preguntas': PreguntaFrecuente.objects.filter(activa=True)[:6],
        'respaldos': RESPALDOS,
    })


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
