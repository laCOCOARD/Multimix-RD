import os
from ipaddress import ip_address
from io import BytesIO
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carrito.carrito import Carrito
from core.models import CuentaBancaria
from core.templatetags.moneda import formatear_monto
from promociones.services import CuponInvalido
from tiendas.decoradores import de_tienda

from . import services
from .forms import AvisoTransferenciaForm, CheckoutForm
from .models import Pedido
from .whatsapp import enlace_del_pedido

SESION_PEDIDO_NUEVO = 'pedido_nuevo'


def _ip_cliente(request):
    if settings.CONFIAR_IP_PROXY:
        candidatos = [
            request.META.get('HTTP_X_REAL_IP', '').strip(),
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip(),
        ]
        for candidato in candidatos:
            try:
                return str(ip_address(candidato))
            except ValueError:
                continue

        # Render may expose the client IP only through its forwarded headers.
        # Never rate-limit every visitor together by the platform proxy address.
        if os.getenv('RENDER_EXTERNAL_HOSTNAME'):
            return None

    try:
        return str(ip_address(request.META.get('REMOTE_ADDR', '')))
    except ValueError:
        return None


def _zona_elegida(valor, tienda):
    try:
        return services.zonas_activas(tienda).filter(pk=int(valor)).first()
    except (TypeError, ValueError):
        return None


def _cuentas_de(tienda):
    return CuentaBancaria.objects.filter(tienda=tienda, activa=True)


def _contexto_checkout(request, carrito, formulario):
    tienda = carrito.tienda
    entrega = formulario['metodo_entrega'].value() or Pedido.Entrega.RECOGER
    zona = _zona_elegida(formulario['zona'].value(), tienda) if entrega == Pedido.Entrega.ENVIO else None
    return {
        'formulario': formulario,
        'lineas': carrito.lineas(),
        'totales': services.calcular_totales(carrito, entrega, zona),
        'zonas': services.zonas_activas(tienda),
        'cuentas': _cuentas_de(tienda),
        'pagos_recoger': services.metodos_pago_disponibles(Pedido.Entrega.RECOGER, tienda),
        'pagos_envio': services.metodos_pago_disponibles(Pedido.Entrega.ENVIO, tienda),
    }


@de_tienda
def checkout(request):
    tienda = request.tienda
    carrito = Carrito(request, tienda)
    if not carrito:
        messages.info(request, 'Tu carrito está vacío. Agrega productos para hacer tu pedido.')
        return redirect('carrito:detalle', tienda.slug)
    avisos = carrito.sincronizar()
    if avisos:
        for aviso in avisos:
            messages.warning(request, aviso)
        return redirect('carrito:detalle', tienda.slug)

    if request.method != 'POST':
        formulario = CheckoutForm(carrito=carrito, initial={
            'metodo_entrega': Pedido.Entrega.RECOGER,
            'metodo_pago': Pedido.Pago.TRANSFERENCIA,
            'cupon': carrito.codigo_cupon,
        })
        return render(request, 'pedidos/checkout.html', _contexto_checkout(request, carrito, formulario))

    formulario = CheckoutForm(request.POST, carrito=carrito)
    if formulario.is_valid():
        ip = _ip_cliente(request)
        if services.supera_limite_por_ip(ip):
            formulario.add_error(None, 'Recibimos varios pedidos desde tu conexión. Espera un rato o escríbenos por WhatsApp.')
        else:
            try:
                pedido = services.crear_pedido(carrito, formulario.cleaned_data, ip=ip)
            except services.StockInsuficiente as error:
                carrito.sincronizar()
                messages.error(request, f'{error.mensaje} Revisa tu carrito y vuelve a confirmar.')
                return redirect('carrito:detalle', tienda.slug)
            except services.PedidoError as error:
                carrito.resumen()
                formulario.add_error(None, error.mensaje)
            else:
                carrito.vaciar()
                request.session[SESION_PEDIDO_NUEVO] = str(pedido.token)
                return redirect(pedido)
    return render(request, 'pedidos/checkout.html', _contexto_checkout(request, carrito, formulario))


@require_POST
@de_tienda
def totales(request):
    """Totales del checkout calculados en el servidor para refrescar el resumen en vivo."""
    tienda = request.tienda
    carrito = Carrito(request, tienda)
    cupon_mensaje, cupon_ok = '', True
    if 'cupon' in request.POST:
        codigo = request.POST['cupon'].strip()
        if codigo:
            try:
                carrito.aplicar_cupon(codigo)
                cupon_mensaje = 'Cupón aplicado.'
            except CuponInvalido as error:
                carrito.quitar_cupon()
                cupon_mensaje, cupon_ok = error.mensaje, False
        else:
            carrito.quitar_cupon()

    entrega = request.POST.get('metodo_entrega')
    if entrega not in Pedido.Entrega.values:
        entrega = Pedido.Entrega.RECOGER
    zona = _zona_elegida(request.POST.get('zona'), tienda) if entrega == Pedido.Entrega.ENVIO else None
    calculo = services.calcular_totales(carrito, entrega, zona)
    if calculo.aviso_cupon:
        cupon_mensaje, cupon_ok = calculo.aviso_cupon, False

    if entrega == Pedido.Entrega.RECOGER:
        envio_texto = 'Gratis'
    elif zona is None:
        envio_texto = 'Elige tu zona'
    else:
        envio_texto = formatear_monto(calculo.costo_envio)

    return JsonResponse({
        'vacio': not carrito,
        'subtotal': formatear_monto(calculo.subtotal),
        'descuento': formatear_monto(calculo.descuento),
        'hay_descuento': calculo.descuento > 0,
        'envio': envio_texto,
        'total': formatear_monto(calculo.total),
        'cupon': calculo.cupon.codigo if calculo.cupon else '',
        'cupon_ok': cupon_ok,
        'cupon_mensaje': cupon_mensaje,
        'metodos_pago': services.metodos_pago_disponibles(entrega, tienda),
    })


def pedido_del_enlace(request, token, consulta=None):
    """Pedido del enlace privado del cliente. La pagina se muestra con la marca de su tienda."""
    consulta = Pedido.objects.all() if consulta is None else consulta
    pedido = get_object_or_404(consulta.select_related('tienda'), token=token)
    request.tienda = pedido.tienda
    return pedido


def confirmacion(request, token):
    pedido = pedido_del_enlace(
        request, token, Pedido.objects.select_related('zona').prefetch_related('detalles'),
    )
    tienda = pedido.tienda
    recien_creado = request.session.pop(SESION_PEDIDO_NUEVO, None) == str(pedido.token)
    return render(request, 'pedidos/confirmacion.html', {
        'pedido': pedido,
        'cuentas': _cuentas_de(tienda) if pedido.paga_por_transferencia else [],
        'enlace_whatsapp': enlace_del_pedido(pedido, tienda.whatsapp),
        'abrir_whatsapp': recien_creado and bool(tienda.whatsapp),
        'puede_avisar_transferencia': (
            pedido.paga_por_transferencia and pedido.estado == Pedido.Estado.PENDIENTE
        ),
    })


@require_POST
def avisar_transferencia(request, token):
    pedido = get_object_or_404(Pedido, token=token)
    formulario = AvisoTransferenciaForm(request.POST)
    if not formulario.is_valid():
        messages.error(request, 'La referencia es demasiado larga.')
        return redirect(pedido)
    try:
        services.marcar_transferencia(pedido, formulario.cleaned_data['referencia_transferencia'])
    except services.PedidoError as error:
        messages.error(request, error.mensaje)
    else:
        messages.success(request, 'Gracias. Verificaremos tu transferencia y te confirmaremos por WhatsApp.')
    return redirect(pedido)
