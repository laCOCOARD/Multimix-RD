"""Vistas para mostrar la factura y verificar su código QR."""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_GET

from core.models import ConfiguracionTienda

from .factura import generar_imagen_factura
from .models import Pedido


@require_GET
def factura(request, token):
    pedido = get_object_or_404(
        Pedido.objects.select_related('zona').prefetch_related('detalles'), token=token,
    )
    tienda = ConfiguracionTienda.obtener()
    url_verificacion = request.build_absolute_uri(
        reverse('pedidos:verificar_factura', args=[pedido.token]),
    )
    imagen = generar_imagen_factura(pedido, tienda.nombre, url_verificacion)
    respuesta = HttpResponse(imagen, content_type='image/png')
    respuesta['Content-Disposition'] = f'inline; filename="factura-{pedido.numero}.png"'
    respuesta['X-Content-Type-Options'] = 'nosniff'
    respuesta['X-Robots-Tag'] = 'noindex, nofollow'
    respuesta['Referrer-Policy'] = 'no-referrer'
    add_never_cache_headers(respuesta)
    return respuesta


@require_GET
def verificar_factura(request, token):
    pedido = get_object_or_404(Pedido, token=token)
    respuesta = render(request, 'pedidos/verificar_factura.html', {'pedido': pedido})
    respuesta['X-Robots-Tag'] = 'noindex, nofollow'
    respuesta['Referrer-Policy'] = 'no-referrer'
    add_never_cache_headers(respuesta)
    return respuesta
