"""Vistas para mostrar la factura y verificar su código QR."""
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_GET

from .factura import codigo_de_verificacion, generar_imagen_factura, pedido_de_la_verificacion
from .models import Pedido


@login_not_required
@require_GET
def factura(request, token):
    pedido = get_object_or_404(
        Pedido.objects.select_related('zona', 'tienda').prefetch_related('detalles'), token=token,
    )
    url_verificacion = request.build_absolute_uri(
        reverse('pedidos:verificar_factura', args=[codigo_de_verificacion(pedido)]),
    )
    imagen = generar_imagen_factura(pedido, pedido.tienda.nombre, url_verificacion)
    respuesta = HttpResponse(imagen, content_type='image/png')
    respuesta['Content-Disposition'] = f'inline; filename="factura-{pedido.numero}.png"'
    respuesta['X-Content-Type-Options'] = 'nosniff'
    respuesta['X-Robots-Tag'] = 'noindex, nofollow'
    respuesta['Referrer-Policy'] = 'no-referrer'
    add_never_cache_headers(respuesta)
    return respuesta


@login_not_required
@require_GET
def verificar_factura(request, codigo):
    """Lo que abre el QR de la factura: que el pedido existe, su numero, total y estado. Nada del cliente."""
    pedido = get_object_or_404(Pedido.objects.select_related('tienda'), pk=pedido_de_la_verificacion(codigo) or 0)
    request.tienda = pedido.tienda
    respuesta = render(request, 'pedidos/verificar_factura.html', {'pedido': pedido})
    respuesta['X-Robots-Tag'] = 'noindex, nofollow'
    respuesta['Referrer-Policy'] = 'no-referrer'
    add_never_cache_headers(respuesta)
    return respuesta


@login_not_required
@require_GET
def verificar_factura_anterior(request, token):
    """El QR de las facturas de antes llevaba el token del pedido; esos siguen funcionando."""
    pedido = get_object_or_404(Pedido, token=token)
    return redirect('pedidos:verificar_factura', codigo_de_verificacion(pedido))
