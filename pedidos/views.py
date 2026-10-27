import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from carrito.carrito import Carrito, agregar_pedido
from clientes import services as clientes
from core.archivos import ERRORES_DE_ALMACENAMIENTO
from core.models import cuentas_para_transferir
from core.red import ip_del_cliente as _ip_cliente
from core.templatetags.moneda import formatear_monto
from pagos import services as pagos
from pagos.proveedores import proveedor_de_tarjeta
from promociones.services import CuponInvalido
from tiendas.decoradores import de_tienda

from . import services, whatsapp_api
from .forms import AvisoTransferenciaForm, CheckoutForm
from .models import Pedido
from .whatsapp import enlace_del_pedido

logger = logging.getLogger('multimix.pedidos')


def _zona_elegida(valor, tienda):
    try:
        return services.zonas_activas(tienda).filter(pk=int(valor)).first()
    except (TypeError, ValueError):
        return None


def _texto_envio(entrega, zona, calculo):
    if entrega == Pedido.Entrega.RECOGER:
        return 'Gratis'
    if zona is None:
        return 'Elige tu zona'
    return formatear_monto(calculo.costo_envio) if calculo.costo_envio else 'Gratis'


def _texto_plazo(carrito, entrega, zona):
    plazo = services.entrega_estimada(carrito, entrega, zona)
    if plazo is None:
        return 'Elige tu zona para ver cuándo llega.'
    if entrega == Pedido.Entrega.RECOGER:
        return f'Listo para recoger {plazo.texto}.'
    return f'Llega {plazo.texto}.'


def _contexto_checkout(request, carrito, formulario):
    tienda = carrito.tienda
    entrega = formulario['metodo_entrega'].value() or Pedido.Entrega.RECOGER
    zona = _zona_elegida(formulario['zona'].value(), tienda) if entrega == Pedido.Entrega.ENVIO else None
    totales = services.calcular_totales(carrito, entrega, zona)
    return {
        'formulario': formulario,
        'lineas': carrito.lineas(),
        'totales': totales,
        'texto_envio': _texto_envio(entrega, zona, totales),
        'texto_plazo': _texto_plazo(carrito, entrega, zona),
        'envio_gratis': services.progreso_envio_gratis(tienda, totales.subtotal - totales.descuento),
        'zonas': services.zonas_activas(tienda),
        'direcciones': clientes.direcciones_de(request.user),
        'cuentas': cuentas_para_transferir(tienda),
        'pagos_recoger': services.metodos_pago_disponibles(Pedido.Entrega.RECOGER, tienda),
        'pagos_envio': services.metodos_pago_disponibles(Pedido.Entrega.ENVIO, tienda),
        # Sin pasarela conectada la tarjeta se anuncia, pero no se puede elegir ni se piden sus datos.
        'tarjeta_disponible': proveedor_de_tarjeta() is not None,
        'whatsapp_automatico': whatsapp_api.configurado(),
    }


@de_tienda
@login_required
def checkout(request):
    tienda = request.tienda
    if not clientes.correo_confirmado(request.user):
        # Los avisos del pedido van al correo de la cuenta: tiene que ser de quien compra.
        return redirect(f"{reverse('clientes:confirma_tu_correo')}?{urlencode({'next': request.path})}")
    carrito = Carrito(request, tienda)
    if not carrito:
        messages.info(request, 'Tu carrito está vacío. Agrega productos para hacer tu pedido.')
        return redirect('carrito:detalle', tienda.slug)
    avisos = carrito.sincronizar()
    if avisos:
        for aviso in avisos:
            messages.warning(request, aviso)
        return redirect('carrito:detalle', tienda.slug)

    cliente = request.user
    if request.method != 'POST':
        formulario = CheckoutForm(carrito=carrito, initial={
            # El cliente no vuelve a escribir los datos que ya tiene su cuenta.
            **clientes.datos_para_el_checkout(cliente),
            'metodo_entrega': Pedido.Entrega.RECOGER,
            'metodo_pago': Pedido.Pago.TRANSFERENCIA,
            'cupon': carrito.codigo_cupon,
        })
        return render(request, 'pedidos/checkout.html', _contexto_checkout(request, carrito, formulario))

    formulario = CheckoutForm(request.POST, request.FILES, carrito=carrito)
    if formulario.is_valid():
        ip = _ip_cliente(request)
        if services.supera_limite_por_ip(ip) or services.supera_limite_por_cuenta(cliente):
            formulario.add_error(None, 'Recibimos varios pedidos desde tu conexión. Espera un rato y vuelve a intentarlo.')
        else:
            # Los avisos del pedido van al correo de la cuenta: el checkout ya no lo pide.
            datos = {**formulario.cleaned_data, 'correo': cliente.email}
            try:
                pedido = services.crear_pedido(carrito, datos, ip=ip, cliente=cliente)
            except services.StockInsuficiente as error:
                carrito.sincronizar()
                messages.error(request, f'{error.mensaje} Revisa tu carrito y vuelve a confirmar.')
                return redirect('carrito:detalle', tienda.slug)
            except (services.PedidoError, pagos.PagoError) as error:
                carrito.resumen()
                formulario.add_error(None, error.mensaje)
            except ERRORES_DE_ALMACENAMIENTO:
                logger.exception('No se pudo guardar el comprobante del checkout')
                formulario.add_error('comprobante', 'No pudimos guardar tu comprobante. Inténtalo otra vez en un momento.')
            else:
                carrito.vaciar()
                clientes.recordar_pedido(cliente, pedido)
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

    return JsonResponse({
        'vacio': not carrito,
        'subtotal': formatear_monto(calculo.subtotal),
        'descuento': formatear_monto(calculo.descuento),
        'hay_descuento': calculo.descuento > 0,
        'impuesto': formatear_monto(calculo.impuesto),
        'hay_impuesto': calculo.impuesto > 0,
        'envio': _texto_envio(entrega, zona, calculo),
        'plazo': _texto_plazo(carrito, entrega, zona),
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


@login_not_required
def confirmacion(request, token):
    pedido = pedido_del_enlace(
        request, token, Pedido.objects.select_related('zona').prefetch_related('detalles'),
    )
    tienda = pedido.tienda
    return render(request, 'pedidos/confirmacion.html', {
        'pedido': pedido,
        'pago': pagos.pago_vigente(pedido),
        'eventos': pedido.eventos.all(),
        'puede_cancelar': services.puede_cancelar_el_cliente(pedido),
        'puede_pedir_devolucion': services.puede_pedir_devolucion(pedido),
        'devolucion': services.devolucion_abierta(pedido),
        'cuentas': cuentas_para_transferir(tienda) if pedido.paga_por_transferencia else [],
        # WhatsApp ya no es un paso de la compra: queda como canal opcional para hablar con la tienda.
        'enlace_whatsapp': enlace_del_pedido(pedido, tienda.whatsapp) if tienda.whatsapp else '',
        'puede_avisar_transferencia': (
            pedido.paga_por_transferencia and pedido.estado == Pedido.Estado.PENDIENTE
        ),
    })


# El enlace privado del pedido abre sin sesion: el token es la llave (pedidos de antes de las cuentas).
@login_not_required
@require_POST
def avisar_transferencia(request, token):
    pedido = get_object_or_404(Pedido, token=token)
    formulario = AvisoTransferenciaForm(request.POST, request.FILES)
    if not formulario.is_valid():
        errores = [error for lista in formulario.errors.values() for error in lista]
        messages.error(request, ' '.join(errores) or 'Revisa los datos de la transferencia.')
        return redirect(pedido)
    datos = formulario.cleaned_data
    try:
        pagos.registrar_comprobante(pedido, datos['comprobante'], datos['referencia_transferencia'])
    except (pagos.PagoError, services.PedidoError) as error:
        messages.error(request, error.mensaje)
    except ERRORES_DE_ALMACENAMIENTO:
        logger.exception('No se pudo guardar el comprobante del pedido %s', pedido.numero)
        messages.error(request, 'No pudimos guardar tu comprobante. Espera un momento e inténtalo otra vez.')
    else:
        messages.success(request, 'Gracias. La tienda revisará tu transferencia; aquí mismo verás tu pago confirmado.')
    return redirect(pedido)


@login_not_required
@require_POST
def cancelar(request, token):
    """El cliente cancela su pedido desde su enlace privado. Solo antes de pagar."""
    pedido = get_object_or_404(Pedido, token=token)
    try:
        services.cancelar_por_cliente(pedido)
    except services.PedidoError as error:
        messages.error(request, error.mensaje)
    else:
        messages.success(request, 'Cancelamos tu pedido.')
    return redirect(pedido)


@login_not_required
@require_POST
def volver_a_pedir(request, token):
    """Pone en el carrito de la tienda los productos del pedido que sigan a la venta, con las mismas cantidades."""
    pedido = pedido_del_enlace(request, token, Pedido.objects.prefetch_related('detalles'))
    if not pedido.tienda.activa:
        messages.error(request, f'{pedido.tienda.nombre} ya no está vendiendo en el sitio.')
        return redirect(pedido)
    _, agregados, avisos = agregar_pedido(request, pedido)
    for aviso in avisos:
        messages.warning(request, aviso)
    if agregados:
        messages.success(request, f'Pusimos en tu carrito los productos del pedido {pedido.numero}.')
    else:
        messages.error(request, 'Ninguno de los productos de ese pedido está a la venta ahora.')
    return redirect('carrito:detalle', pedido.tienda.slug)


@login_not_required
@require_POST
def pedir_devolucion(request, token):
    pedido = get_object_or_404(Pedido, token=token)
    try:
        services.solicitar_devolucion(pedido, request.POST.get('motivo', ''))
    except services.PedidoError as error:
        messages.error(request, error.mensaje)
    else:
        messages.success(request, 'Enviamos tu solicitud a la tienda. Te responderá por correo o aquí mismo.')
    return redirect(pedido)
