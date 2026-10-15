"""Correos de los pedidos: a la tienda cuando entra uno, llega un comprobante o el sitio confirma su pago, y al
cliente cuando cambia. Si el pedido lo cobra el sitio, el comprobante le llega al sitio."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from core.correo import enviar, url_absoluta
from core.models import ConfiguracionTienda

from .models import Pedido


def correos_del_sitio():
    """A quien se avisa en el sitio: su correo de contacto; si no tiene, los administradores principales."""
    plataforma = ConfiguracionTienda.obtener()
    if plataforma.correo:
        return [plataforma.correo]
    administradores = get_user_model().objects.filter(is_superuser=True, is_active=True).exclude(email='')
    return list(administradores.values_list('email', flat=True))


def correos_de_la_tienda(tienda):
    """A quien se avisa en la tienda: su correo de contacto; si no tiene, sus vendedores; si no, el sitio."""
    if tienda.correo:
        return [tienda.correo]
    vendedores = list(tienda.usuarios.filter(is_active=True).exclude(email='').values_list('email', flat=True))
    return vendedores or correos_del_sitio()


def _contexto(pedido, **extra):
    return {
        'pedido': pedido,
        'tienda': pedido.tienda,
        'sitio': ConfiguracionTienda.obtener().nombre,
        'enlace_pedido': url_absoluta(pedido.get_absolute_url()),
        'enlace_panel': url_absoluta(reverse('admin:pedidos_pedido_change', args=[pedido.pk])),
        **extra,
    }


def _al_confirmar(funcion):
    """El correo sale cuando la base ya guardo el cambio; si la operacion se deshace, no sale."""
    transaction.on_commit(funcion)


def pedido_creado(pedido):
    def enviar_avisos():
        fresco = Pedido.objects.select_related('tienda', 'zona').prefetch_related('detalles').get(pk=pedido.pk)
        contexto = _contexto(fresco)
        enviar(f'Nuevo pedido {fresco.numero}', 'tienda_pedido_nuevo', contexto, correos_de_la_tienda(fresco.tienda))
        enviar(f'Recibimos tu pedido {fresco.numero}', 'cliente_pedido_recibido', contexto, [fresco.correo])
    _al_confirmar(enviar_avisos)


def estado_cambiado(pedido):
    """Al cliente: su pedido fue pagado, esta listo, va en camino, se entrego o se cancelo."""
    def enviar_aviso():
        fresco = Pedido.objects.select_related('tienda').filter(pk=pedido.pk).first()
        # Al eliminar un pedido se cancela primero: para entonces ya no existe y no hay nada que avisar.
        if fresco is None:
            return
        asunto = f'Tu pedido {fresco.numero}: {fresco.get_estado_display().lower()}'
        enviar(asunto, 'cliente_estado', _contexto(fresco), [fresco.correo])
    _al_confirmar(enviar_aviso)


def comprobante_recibido(pago):
    def enviar_aviso():
        pedido = Pedido.objects.select_related('tienda').get(pk=pago.pedido_id)
        contexto = _contexto(
            pedido, pago=pago, enlace_pago=url_absoluta(reverse('admin:pagos_pago_change', args=[pago.pk])),
        )
        # Si el cliente transfirio a las cuentas del sitio, lo comprueba el dueño en su banco, no la tienda.
        destinatarios = correos_del_sitio() if pedido.cobra_el_sitio else correos_de_la_tienda(pedido.tienda)
        enviar(f'Transferencia por revisar: pedido {pedido.numero}', 'tienda_comprobante', contexto, destinatarios)
    _al_confirmar(enviar_aviso)


def pago_confirmado_a_la_tienda(pedido):
    """A la tienda: el sitio comprobo en su banco la transferencia del cliente y ya puede preparar el pedido."""
    def enviar_aviso():
        fresco = Pedido.objects.select_related('tienda', 'zona').prefetch_related('detalles').filter(pk=pedido.pk).first()
        if fresco is None:
            return
        enviar(
            f'Pago confirmado: pedido {fresco.numero}', 'tienda_pago_confirmado', _contexto(fresco),
            correos_de_la_tienda(fresco.tienda),
        )
    _al_confirmar(enviar_aviso)


def pago_rechazado(pago):
    def enviar_aviso():
        pedido = Pedido.objects.select_related('tienda').get(pk=pago.pedido_id)
        enviar(
            f'No pudimos confirmar tu pago del pedido {pedido.numero}', 'cliente_pago_rechazado',
            _contexto(pedido, pago=pago), [pedido.correo],
        )
    _al_confirmar(enviar_aviso)


def devolucion_solicitada(solicitud):
    def enviar_aviso():
        pedido = Pedido.objects.select_related('tienda').get(pk=solicitud.pedido_id)
        contexto = _contexto(
            pedido, solicitud=solicitud,
            enlace_solicitud=url_absoluta(reverse('admin:pedidos_solicituddevolucion_change', args=[solicitud.pk])),
        )
        enviar(
            f'Solicitud de devolución: pedido {pedido.numero}', 'tienda_devolucion', contexto,
            correos_de_la_tienda(pedido.tienda),
        )
    _al_confirmar(enviar_aviso)


def devolucion_respondida(solicitud):
    def enviar_aviso():
        pedido = Pedido.objects.select_related('tienda').get(pk=solicitud.pedido_id)
        enviar(
            f'Tu solicitud de devolución del pedido {pedido.numero}', 'cliente_devolucion',
            _contexto(pedido, solicitud=solicitud), [pedido.correo],
        )
    _al_confirmar(enviar_aviso)
