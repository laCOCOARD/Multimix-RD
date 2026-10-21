"""Avisame cuando este disponible: se anota el correo y se avisa una sola vez cuando el producto vuelve."""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from core import correo, limites
from core.correo import url_absoluta

from .models import AvisoDisponible, Producto, q_comprable

logger = logging.getLogger('multimix.catalogo')

# Pedidos de aviso por persona (cuenta, conexion o sesion) en una hora: nadie llena de correos a otro.
AVISOS_POR_PERSONA = 10
UNA_HORA = 60 * 60


class AvisoError(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def pedir_aviso(producto, correo_cliente, quien, usuario=None):
    """Anota el aviso. `quien` son las formas de reconocer a la persona, como en los cupones."""
    correo_cliente = (correo_cliente or '').strip().lower()
    if not correo_cliente:
        raise AvisoError('Escribe tu correo para avisarte.')
    if producto.se_puede_comprar:
        raise AvisoError('Este producto ya está disponible: puedes comprarlo ahora.')
    if any(limites.bloqueado('aviso-disponible', *parte, maximo=AVISOS_POR_PERSONA, ventana=UNA_HORA) for parte in quien):
        raise AvisoError('Pediste muchos avisos seguidos. Espera un rato y vuelve a intentarlo.')
    for parte in quien:
        limites.anotar_intento('aviso-disponible', *parte)
    # Si ya se le aviso antes y se volvio a agotar, se le avisa otra vez.
    aviso, _ = AvisoDisponible.objects.update_or_create(
        producto=producto, correo=correo_cliente,
        defaults={'tienda_id': producto.tienda_id, 'usuario': usuario, 'avisado': None},
    )
    return aviso


def esperando(producto, correo_cliente):
    return bool(correo_cliente) and AvisoDisponible.objects.filter(
        producto=producto, correo=correo_cliente.strip().lower(), avisado__isnull=True,
    ).exists()


def avisar_disponibles(productos=None):
    """Envia el correo a quienes esperan un producto que ya se puede comprar. Devuelve cuantos se avisaron."""
    pendientes = AvisoDisponible.objects.filter(avisado__isnull=True).filter(
        producto__in=Producto.objects.activos().filter(q_comprable()),
    )
    if productos is not None:
        pendientes = pendientes.filter(producto__in=productos)
    avisados = 0
    for aviso in pendientes.select_related('producto', 'producto__tienda'):
        producto = aviso.producto
        contexto = {'producto': producto, 'tienda': producto.tienda, 'enlace': url_absoluta(producto.get_absolute_url())}
        if correo.enviar(f'Ya está disponible: {producto.nombre}', 'cliente_disponible', contexto, [aviso.correo]):
            AvisoDisponible.objects.filter(pk=aviso.pk).update(avisado=timezone.now())
            avisados += 1
    if avisados:
        logger.info('Avisos de disponibilidad enviados: %s', avisados)
    return avisados


@receiver(post_save, sender=Producto)
def avisar_si_volvio(sender, instance, **kwargs):
    """Al guardar un producto que ya se puede comprar y que alguien espera, se avisa en cuanto se confirme."""
    if not instance.se_puede_comprar or not instance.activo:
        return
    if AvisoDisponible.objects.filter(producto=instance, avisado__isnull=True).exists():
        transaction.on_commit(lambda: avisar_disponibles([instance.pk]))
