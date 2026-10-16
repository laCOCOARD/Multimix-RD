from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.archivos import NombreUnico
from core.validators import validar_imagen
from pedidos.models import Pedido


class Pago(models.Model):
    """Un intento de pago de un pedido: la transferencia con su comprobante, el efectivo o, mas adelante, la tarjeta.

    Nunca guarda datos de tarjetas: del proveedor solo quedan la referencia y el codigo de autorizacion.
    """

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente de pago'
        EN_REVISION = 'en_revision', 'Pago en revisión'
        APROBADO = 'aprobado', 'Pago confirmado'
        RECHAZADO = 'rechazado', 'Rechazado'
        CANCELADO = 'cancelado', 'Cancelado'
        REEMBOLSADO = 'reembolsado', 'Reembolsado'

    # Un pedido tiene un solo pago en curso; los rechazados y cancelados quedan como historial.
    VIGENTES = (Estado.PENDIENTE, Estado.EN_REVISION, Estado.APROBADO)
    POR_RESOLVER = (Estado.PENDIENTE, Estado.EN_REVISION)

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.PROTECT, related_name='pagos', editable=False)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='pagos', editable=False)
    referencia = models.CharField(
        max_length=40, unique=True, editable=False,
        help_text='Identifica este intento de pago; no se repite aunque el pedido tenga varios.',
    )
    metodo = models.CharField('método de pago', max_length=20, choices=Pedido.Pago.choices)
    proveedor = models.CharField(
        max_length=20, blank=True, help_text='Pasarela que procesó el pago, si fue con tarjeta.',
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)

    comprobante = models.ImageField(
        upload_to=NombreUnico('comprobantes'), blank=True, validators=[validar_imagen],
        help_text='Foto o captura de la transferencia que envió el cliente.',
    )
    referencia_cliente = models.CharField('referencia que dio el cliente', max_length=60, blank=True)
    codigo_autorizacion = models.CharField('código de autorización', max_length=40, blank=True)
    respuesta_proveedor = models.JSONField('respuesta del proveedor', default=dict, blank=True, editable=False)
    nota = models.CharField('nota del vendedor', max_length=255, blank=True)

    creado = models.DateTimeField('fecha de creación', auto_now_add=True)
    actualizado = models.DateTimeField('última actualización', auto_now=True)
    revisado_en = models.DateTimeField('fecha de revisión', null=True, blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pagos_revisados',
        verbose_name='revisado por',
    )

    class Meta:
        verbose_name = 'pago'
        verbose_name_plural = 'pagos'
        ordering = ['-creado', '-id']
        constraints = [
            models.CheckConstraint(condition=Q(monto__gte=0), name='pago_monto_no_negativo'),
            # Un pedido no se cobra dos veces, aunque lleguen dos avisos de aprobacion a la vez.
            models.UniqueConstraint(
                fields=['pedido'], condition=Q(estado='aprobado'), name='un_pago_aprobado_por_pedido',
            ),
        ]
        indexes = [
            models.Index(fields=['tienda', 'estado', '-creado'], name='pago_tienda_estado_idx'),
        ]

    def __str__(self):
        return self.referencia

    @property
    def por_resolver(self):
        return self.estado in self.POR_RESOLVER


@receiver(post_delete, sender=Pago)
def borrar_comprobante(sender, instance, **kwargs):
    if instance.comprobante:
        instance.comprobante.delete(save=False)


class Liquidacion(models.Model):
    """Cierre de cuentas con una tienda: lo que el sitio le deposito (o lo que la tienda le debia) por sus ventas."""

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.PROTECT, related_name='liquidaciones')
    creada = models.DateTimeField('fecha', auto_now_add=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        verbose_name='registrada por',
    )
    pedidos_incluidos = models.PositiveIntegerField('pedidos', default=0)
    ventas = models.DecimalField('vendido', max_digits=12, decimal_places=2)
    cobrado_por_el_sitio = models.DecimalField('cobró el sitio', max_digits=12, decimal_places=2)
    cobrado_por_la_tienda = models.DecimalField(
        'cobró la tienda (efectivo)', max_digits=12, decimal_places=2, default=0,
        help_text='Lo que la tienda cobró directamente (en efectivo): no se le deposita.',
    )
    comision_de_lo_cobrado_por_la_tienda = models.DecimalField(
        'comisión de lo que cobró la tienda', max_digits=12, decimal_places=2, default=0,
        help_text='Parte de la comisión que se descontó de lo depositado (o que la tienda pagó) por esas ventas.',
    )
    comision_porcentaje = models.DecimalField('comisión (%)', max_digits=5, decimal_places=2)
    comision = models.DecimalField('comisión', max_digits=12, decimal_places=2)
    ajustes = models.DecimalField('reembolsos descontados', max_digits=12, decimal_places=2, default=0)
    costo_transferencia = models.DecimalField(
        'comisión de la transferencia', max_digits=12, decimal_places=2, default=0,
        help_text='Lo que cobró el banco por enviar el depósito. Se descuenta de lo que recibe la tienda.',
    )
    monto = models.DecimalField(
        'saldo', max_digits=12, decimal_places=2,
        help_text='Lo que recibió la tienda, ya descontada la comisión de la transferencia. '
                  'Negativo: la tienda le debía al sitio.',
    )
    nota = models.CharField('referencia del depósito', max_length=255, blank=True)

    class Meta:
        verbose_name = 'liquidación'
        verbose_name_plural = 'liquidaciones'
        ordering = ['-creada', '-id']

    def __str__(self):
        return f'{self.tienda} · {self.creada:%d/%m/%Y}'
