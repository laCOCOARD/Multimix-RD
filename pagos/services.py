"""Pagos de los pedidos: comprobantes de transferencia, aprobacion y rechazo, y su sincronia con el pedido."""
import logging
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from catalogo.imagenes import convertir_a_webp
from core.archivos import ERRORES_DE_ALMACENAMIENTO, hay_almacenamiento_privado
from pedidos import avisos
from pedidos import services as pedidos
from pedidos.models import Pedido
from tiendas.services import ve_todas

from .models import Pago

logger = logging.getLogger('multimix.pagos')

Estado = Pago.Estado
# Lado maximo del comprobante: suficiente para leer una captura del banco sin guardar fotos enormes.
LADO_COMPROBANTE = 1600


class PagoError(Exception):
    """Error de negocio con un mensaje listo para mostrar."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def _estado_inicial(pedido):
    if pedido.esta_pagado:
        return Estado.APROBADO
    if pedido.transferencia_realizada:
        return Estado.EN_REVISION
    return Estado.PENDIENTE


def puede_resolver(pago, usuario):
    """Si el cliente transfirio a las cuentas del sitio, solo el administrador principal puede comprobarlo en su
    banco: el vendedor ve el pago, pero no lo aprueba ni lo rechaza. `usuario` vacio es el sistema."""
    return usuario is None or not pago.pedido.cobra_el_sitio or ve_todas(usuario)


def _exigir_permiso(pago, usuario):
    if not puede_resolver(pago, usuario):
        raise PagoError(
            f'El pago {pago.referencia} llegó a las cuentas del sitio: lo confirma el administrador principal.'
        )


def pago_vigente(pedido):
    """El pago en curso del pedido; lo abre si aun no tiene. Un pedido cancelado no abre pagos nuevos."""
    pago = pedido.pagos.filter(estado__in=Pago.VIGENTES).order_by('-id').first()
    if pago is not None or pedido.estado in Pedido.ESTADOS_SIN_VENTA:
        return pago or pedido.pagos.order_by('-id').first()
    return Pago.objects.create(
        tienda_id=pedido.tienda_id, pedido=pedido, metodo=pedido.metodo_pago, monto=pedido.total,
        referencia=f'{pedido.numero}-P{pedido.pagos.count() + 1}', estado=_estado_inicial(pedido),
        referencia_cliente=pedido.referencia_transferencia,
        revisado_en=pedido.fecha_pago if pedido.esta_pagado else None,
    )


@transaction.atomic
def registrar_comprobante(pedido, archivo=None, referencia=''):
    """El cliente avisa que transfirio y, si quiere, adjunta el comprobante. El pago queda en revision.

    No cambia el estado del pedido: eso lo hace el vendedor al aprobar el pago.
    """
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if not pedido.paga_por_transferencia or pedido.estado != Pedido.Estado.PENDIENTE:
        raise PagoError('Este pedido ya no admite avisos de transferencia.')
    pago = pago_vigente(pedido)
    anterior = pago.comprobante.name if archivo and pago.comprobante else ''
    almacen_anterior = pago.almacenamiento_del_comprobante
    if archivo:
        # Se guarda siempre como WebP: achica la foto y descarta los metadatos del telefono.
        pago.comprobante.save(f'{uuid4().hex}.webp', convertir_a_webp(archivo, LADO_COMPROBANTE), save=False)
        pago.comprobante_privado = hay_almacenamiento_privado()
    pago.referencia_cliente = (referencia or '').strip()[:60]
    pago.estado = Estado.EN_REVISION
    pago.save()
    if anterior:
        almacen_anterior.delete(anterior)
    pedidos.marcar_transferencia(pedido, pago.referencia_cliente)
    avisos.comprobante_recibido(pago)
    logger.info('Pago %s en revision%s', pago.referencia, ' con comprobante' if pago.comprobante else '')
    return pago


@transaction.atomic
def aprobar_pago(pago, usuario=None):
    """Confirma el pago y pasa el pedido a Pagado. Repetirlo no hace nada: un pedido se cobra una sola vez."""
    pago = Pago.objects.select_for_update().select_related('pedido').get(pk=pago.pk)
    _exigir_permiso(pago, usuario)
    if pago.estado == Estado.APROBADO:
        return pago
    if not pago.por_resolver:
        raise PagoError(f'El pago {pago.referencia} está "{pago.get_estado_display()}" y ya no se puede aprobar.')
    pedido = pago.pedido
    if pedido.estado == Pedido.Estado.PENDIENTE:
        # cambiar_estado deja aprobado el pago del pedido (sincronizar_con_pedido).
        pedidos.cambiar_estado(pedido, Pedido.Estado.PAGADO, usuario=usuario)
    elif not pedido.esta_pagado:
        raise PagoError(f'El pedido {pedido.numero} está "{pedido.get_estado_display()}" y no se puede cobrar.')
    pago.refresh_from_db()
    pago.estado = Estado.APROBADO
    pago.revisado_en = pago.revisado_en or timezone.now()
    pago.revisado_por = usuario
    pago.save(update_fields=['estado', 'revisado_en', 'revisado_por', 'actualizado'])
    logger.info('Pago %s aprobado por %s', pago.referencia, usuario or 'el sistema')
    return pago


@transaction.atomic
def rechazar_pago(pago, usuario=None, nota=''):
    """El comprobante no sirve: el pago queda rechazado y el cliente puede enviar otro."""
    pago = Pago.objects.select_for_update().select_related('pedido').get(pk=pago.pk)
    _exigir_permiso(pago, usuario)
    if not pago.por_resolver:
        raise PagoError(f'El pago {pago.referencia} está "{pago.get_estado_display()}" y ya no se puede rechazar.')
    pago.estado = Estado.RECHAZADO
    pago.nota = (nota or pago.nota or '')[:255]
    pago.revisado_en = timezone.now()
    pago.revisado_por = usuario
    pago.save(update_fields=['estado', 'nota', 'revisado_en', 'revisado_por', 'actualizado'])
    Pedido.objects.filter(pk=pago.pedido_id).update(transferencia_realizada=False, referencia_transferencia='')
    avisos.pago_rechazado(pago)
    logger.info('Pago %s rechazado por %s', pago.referencia, usuario or 'el sistema')
    return pago


def sincronizar_con_pedido(pedido):
    """Deja el pago de acuerdo con el pedido. Lo llama `pedidos.services.cambiar_estado`.

    El vendedor tambien puede marcar el pedido como pagado o cancelarlo desde el propio pedido.
    """
    if pedido.estado == Pedido.Estado.REEMBOLSADO:
        pedido.pagos.filter(estado=Estado.APROBADO).update(estado=Estado.REEMBOLSADO, actualizado=timezone.now())
    elif pedido.estado == Pedido.Estado.CANCELADO:
        pedido.pagos.filter(estado__in=Pago.POR_RESOLVER).update(estado=Estado.CANCELADO, actualizado=timezone.now())
    elif pedido.fecha_pago:
        pago = pago_vigente(pedido)
        if pago.estado != Estado.APROBADO:
            pago.estado = Estado.APROBADO
            pago.revisado_en = pedido.fecha_pago
            pago.save(update_fields=['estado', 'revisado_en', 'actualizado'])


def mover_comprobantes_al_privado(limite=5):
    """Pasa al almacenamiento privado los comprobantes que quedaron en el publico. Devuelve cuantos movio.

    Lo llaman las tareas periodicas, de a pocos: cada uno es una descarga y una subida, y la visita que dispara
    la tarea espera a que terminen.
    """
    if not hay_almacenamiento_privado():
        return 0
    from django.core.files.storage import storages

    publico, privado = storages['default'], storages['privado']
    movidos = 0
    for pago in Pago.objects.exclude(comprobante='').filter(comprobante_privado=False)[:limite]:
        nombre = pago.comprobante.name
        try:
            nuevo = nombre
            if publico.exists(nombre):
                with publico.open(nombre) as archivo:
                    nuevo = privado.save(nombre, archivo)
            Pago.objects.filter(pk=pago.pk).update(comprobante=nuevo, comprobante_privado=True)
            if publico.exists(nombre):
                publico.delete(nombre)
        except ERRORES_DE_ALMACENAMIENTO:
            logger.exception('No se pudo mover el comprobante del pago %s', pago.referencia)
            break
        movidos += 1
    return movidos
