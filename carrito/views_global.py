import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clientes import services as clientes
from core.archivos import ERRORES_DE_ALMACENAMIENTO
from core.models import cuentas_del_sitio
from core.red import ip_del_cliente as _ip_cliente
from pagos import services as pagos
from pedidos import services as pedidos
from pedidos.whatsapp import construir_enlace

from .carrito import CarritoGlobal
from .forms_global import AvisoTransferenciaGlobalForm, CheckoutGlobalForm

logger = logging.getLogger('multimix.carrito')


def carrito_global(request):
    """Carrito de todas las tiendas. Se ve y se edita sin cuenta; la cuenta se pide al pagar (checkout_global)."""
    carrito = CarritoGlobal(request)
    carritos = carrito.carritos()
    total_global = sum(c.resumen().total for c in carritos.values())
    return render(request, 'carrito/carrito_global.html', {
        'carritos': carritos,
        'total_global': total_global,
    })


@login_required
def checkout_global(request):
    carrito = CarritoGlobal(request)
    if not carrito:
        messages.info(request, 'Tu carrito está vacío. Agrega productos para hacer tu pedido.')
        return redirect('carrito_global:global')

    if not clientes.correo_confirmado(request.user):
        from django.urls import reverse
        from django.utils.http import urlencode
        return redirect(f"{reverse('clientes:confirma_tu_correo')}?{urlencode({'next': request.path})}")

    cliente = request.user

    if request.method != 'POST':
        formulario = CheckoutGlobalForm(initial={
            **clientes.datos_para_el_checkout(cliente),
        })
        return render(request, 'carrito/checkout_global.html', _contexto_checkout(carrito, formulario))

    formulario = CheckoutGlobalForm(request.POST)
    if formulario.is_valid():
        ip = _ip_cliente(request)
        if pedidos.supera_limite_por_ip(ip) or pedidos.supera_limite_por_cuenta(cliente):
            formulario.add_error(None, 'Recibimos varios pedidos desde tu conexión. Espera un rato y vuelve a intentarlo.')
        else:
            datos = {**formulario.cleaned_data, 'correo': cliente.email}
            try:
                pago_global, _ = pedidos.crear_pedidos_global(carrito, datos, ip=ip, cliente=cliente)
            except pedidos.StockInsuficiente as error:
                messages.error(request, f'{error.mensaje} Revisa tu carrito.')
                return redirect('carrito_global:global')
            except pedidos.PedidoError as error:
                formulario.add_error(None, error.mensaje)
            else:
                return redirect('carrito_global:confirmacion_global', grupo=pago_global.grupo)

    return render(request, 'carrito/checkout_global.html', _contexto_checkout(carrito, formulario))


def _contexto_checkout(carrito, formulario):
    from decimal import Decimal
    carritos = carrito.carritos()
    total = sum(c.resumen().total for c in carritos.values())
    return {
        'formulario': formulario,
        'carritos': carritos,
        'total_global': total,
        'cuentas_sitio': cuentas_del_sitio(),
    }


def confirmacion_global(request, grupo):
    from pagos.models import PagoGlobal
    pago_global = get_object_or_404(PagoGlobal, grupo=grupo)
    pedidos_del_grupo = pago_global.pedidos.select_related('tienda').order_by('tienda__nombre')
    return render(request, 'carrito/confirmacion_global.html', {
        'pago_global': pago_global,
        'pedidos': pedidos_del_grupo,
        'cuentas_sitio': cuentas_del_sitio(),
        'puede_avisar': pago_global.estado in pago_global.POR_RESOLVER and not pago_global.comprobante,
    })


@require_POST
def aviso_transferencia_global(request, grupo):
    from pagos.models import PagoGlobal
    pago_global = get_object_or_404(PagoGlobal, grupo=grupo)
    formulario = AvisoTransferenciaGlobalForm(request.POST, request.FILES)
    if not formulario.is_valid():
        errores = [error for lista in formulario.errors.values() for error in lista]
        messages.error(request, ' '.join(errores) or 'Revisa los datos de la transferencia.')
        return redirect('carrito_global:confirmacion_global', grupo=grupo)
    datos = formulario.cleaned_data
    try:
        pagos.registrar_comprobante_global(
            pago_global,
            datos['comprobante'],
            datos.get('referencia_transferencia', ''),
        )
    except pagos.PagoError as error:
        messages.error(request, error.mensaje)
    except ERRORES_DE_ALMACENAMIENTO:
        logger.exception('No se pudo guardar el comprobante del pago global %s', grupo)
        messages.error(request, 'No pudimos guardar tu comprobante. Espera un momento e inténtalo otra vez.')
    else:
        messages.success(request, 'Gracias. Revisaremos tu transferencia y te confirmaremos cada pedido.')
    return redirect('carrito_global:confirmacion_global', grupo=grupo)
