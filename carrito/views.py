from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from catalogo.models import Producto
from core.templatetags.moneda import formatear_monto
from promociones.services import CuponInvalido
from tiendas.decoradores import de_tienda

from .carrito import Carrito, CarritoError


def _es_fetch(request):
    return request.headers.get('X-Requested-With') == 'fetch'


def _entero(valor, defecto=1):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def _estado_json(carrito):
    resumen = carrito.resumen()
    return {
        'cantidad_total': len(carrito),
        'vacio': not carrito,
        'lineas': {
            str(linea.producto.pk): {'cantidad': linea.cantidad, 'subtotal': formatear_monto(linea.subtotal)}
            for linea in carrito.lineas()
        },
        'subtotal': formatear_monto(resumen.subtotal),
        'descuento': formatear_monto(resumen.descuento),
        'hay_descuento': resumen.descuento > 0,
        'total': formatear_monto(resumen.total),
        'cupon': resumen.cupon.codigo if resumen.cupon else '',
        'aviso_cupon': resumen.aviso_cupon,
    }


def _producto_de_la_tienda(request, producto_id):
    return Producto.objects.select_related('categoria').filter(tienda=request.tienda, pk=producto_id).first()


def _responder(request, carrito, ok, mensaje):
    """JSON para las llamadas con fetch; mensaje y redireccion para el envio normal del formulario."""
    if _es_fetch(request):
        return JsonResponse({'ok': ok, 'mensaje': mensaje, **_estado_json(carrito)}, status=200 if ok else 400)
    if mensaje:
        (messages.success if ok else messages.error)(request, mensaje)
    siguiente = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(siguiente)
    return redirect('carrito:detalle', request.tienda.slug)


@require_GET
@de_tienda
def detalle(request):
    carrito = Carrito(request, request.tienda)
    for aviso in carrito.sincronizar():
        messages.warning(request, aviso)
    resumen = carrito.resumen()
    if resumen.aviso_cupon:
        messages.warning(request, resumen.aviso_cupon)
    return render(request, 'carrito/detalle.html', {
        'lineas': carrito.lineas(),
        'resumen': resumen,
        'maximo_por_producto': settings.CARRITO_MAX_POR_PRODUCTO,
    })


@require_POST
@de_tienda
def agregar(request):
    carrito = Carrito(request, request.tienda)
    producto = _producto_de_la_tienda(request, _entero(request.POST.get('producto_id'), 0))
    if producto is None:
        return _responder(request, carrito, False, 'Ese producto no existe.')
    cantidad = max(_entero(request.POST.get('cantidad')), 1)
    try:
        final, ajustada = carrito.agregar(producto, cantidad)
    except CarritoError as error:
        return _responder(request, carrito, False, error.mensaje)
    if ajustada:
        mensaje = f'Solo hay {final} disponibles de "{producto.nombre}"; dejamos esa cantidad en tu carrito.'
    else:
        mensaje = f'"{producto.nombre}" se agregó al carrito.'
    return _responder(request, carrito, True, mensaje)


@require_POST
@de_tienda
def actualizar(request):
    carrito = Carrito(request, request.tienda)
    producto_id = _entero(request.POST.get('producto_id'), 0)
    cantidad = _entero(request.POST.get('cantidad'))
    if cantidad <= 0:
        carrito.eliminar(producto_id)
        return _responder(request, carrito, True, 'Producto eliminado del carrito.')
    producto = _producto_de_la_tienda(request, producto_id)
    if producto is None or not carrito.cantidad_de(producto_id):
        return _responder(request, carrito, False, 'Ese producto no está en tu carrito.')
    try:
        final, ajustada = carrito.agregar(producto, cantidad, reemplazar=True)
    except CarritoError as error:
        carrito.eliminar(producto_id)
        return _responder(request, carrito, False, f'{error.mensaje} Lo quitamos del carrito.')
    mensaje = f'Solo quedan {final} de "{producto.nombre}"; ajustamos la cantidad.' if ajustada else ''
    return _responder(request, carrito, True, mensaje)


@require_POST
@de_tienda
def eliminar(request):
    carrito = Carrito(request, request.tienda)
    carrito.eliminar(_entero(request.POST.get('producto_id'), 0))
    return _responder(request, carrito, True, 'Producto eliminado del carrito.')


@require_POST
@de_tienda
def cupon_aplicar(request):
    carrito = Carrito(request, request.tienda)
    try:
        cupon = carrito.aplicar_cupon(request.POST.get('codigo', ''))
    except CuponInvalido as error:
        return _responder(request, carrito, False, error.mensaje)
    return _responder(request, carrito, True, f'Cupón {cupon.codigo} aplicado.')


@require_POST
@de_tienda
def cupon_quitar(request):
    carrito = Carrito(request, request.tienda)
    carrito.quitar_cupon()
    return _responder(request, carrito, True, 'Cupón quitado.')
