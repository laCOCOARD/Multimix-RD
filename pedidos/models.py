import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse

from catalogo.models import Producto
from promociones.models import Cupon


class ZonaEnvio(models.Model):
    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='zonas_envio')
    nombre = models.CharField(max_length=80)
    tarifa = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'zona de envío'
        verbose_name_plural = 'zonas de envío'
        ordering = ['orden', 'nombre']
        constraints = [
            models.CheckConstraint(condition=Q(tarifa__gte=0), name='zona_tarifa_no_negativa'),
            models.UniqueConstraint(
                fields=['tienda', 'nombre'], name='zona_nombre_unico_por_tienda',
                violation_error_message='Ya tienes una zona con ese nombre.',
            ),
        ]

    def __str__(self):
        return self.nombre


class SecuenciaTienda(models.Model):
    """Contador por tienda y año para numerar sus pedidos sin huecos ni duplicados."""

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='secuencias')
    anio = models.PositiveSmallIntegerField('año')
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'secuencia de pedidos'
        verbose_name_plural = 'secuencias de pedidos'
        constraints = [
            models.UniqueConstraint(fields=['tienda', 'anio'], name='secuencia_unica_por_tienda_y_anio'),
        ]

    def __str__(self):
        return f'{self.tienda_id} · {self.anio}: {self.ultimo}'


class Pedido(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        PAGADO = 'pagado', 'Pagado'
        PREPARANDO = 'preparando', 'Preparando pedido'
        LISTO = 'listo', 'Listo para recoger'
        ENVIADO = 'enviado', 'Enviado'
        EN_REPARTO = 'en_reparto', 'En reparto'
        ENTREGADO = 'entregado', 'Entregado'
        CANCELADO = 'cancelado', 'Cancelado'
        REEMBOLSADO = 'reembolsado', 'Reembolsado'

    class Entrega(models.TextChoices):
        RECOGER = 'recoger', 'Recoger en tienda'
        ENVIO = 'envio', 'Envío a domicilio'

    class Pago(models.TextChoices):
        TRANSFERENCIA = 'transferencia', 'Transferencia bancaria'
        EFECTIVO_RECOGER = 'efectivo_recoger', 'Efectivo al recoger'
        CONTRA_ENTREGA = 'contra_entrega', 'Efectivo contra entrega'

    # Estados que cuentan como venta para "Más vendidos" y los reportes.
    ESTADOS_VENTA = (
        Estado.PAGADO, Estado.PREPARANDO, Estado.LISTO, Estado.ENVIADO, Estado.EN_REPARTO, Estado.ENTREGADO,
    )
    # Un pedido en estos estados no cuenta como dinero cobrado aunque tenga fecha de pago.
    ESTADOS_SIN_VENTA = (Estado.CANCELADO, Estado.REEMBOLSADO)

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.PROTECT, related_name='pedidos', editable=False)
    numero = models.CharField('número', max_length=20, unique=True, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos',
        editable=False, help_text='La cuenta con la que se hizo el pedido; vacío si compró como invitado.',
    )
    nombre = models.CharField(max_length=120)
    telefono = models.CharField('teléfono', max_length=10)
    correo = models.EmailField(blank=True)

    metodo_entrega = models.CharField('método de entrega', max_length=10, choices=Entrega.choices)
    zona = models.ForeignKey(
        ZonaEnvio, on_delete=models.PROTECT, null=True, blank=True, related_name='pedidos',
        verbose_name='zona de envío',
    )
    sector = models.CharField(max_length=80, blank=True)
    direccion = models.CharField('dirección', max_length=255, blank=True)
    referencia = models.CharField('referencia de la dirección', max_length=255, blank=True)

    metodo_pago = models.CharField('método de pago', max_length=20, choices=Pago.choices)
    transferencia_realizada = models.BooleanField('el cliente dice que ya transfirió', default=False)
    referencia_transferencia = models.CharField('referencia de la transferencia', max_length=60, blank=True)

    cupon = models.ForeignKey(
        Cupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos', verbose_name='cupón',
    )
    codigo_cupon = models.CharField('código de cupón aplicado', max_length=30, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    impuesto = models.DecimalField('ITBIS', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    porcentaje_impuesto = models.DecimalField(
        'ITBIS aplicado (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'),
    )
    costo_envio = models.DecimalField('costo de envío', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2)

    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    transportista = models.CharField(max_length=60, blank=True, help_text='Empresa o persona que lleva el pedido.')
    numero_seguimiento = models.CharField(
        'número de seguimiento', max_length=60, blank=True, help_text='El que da el transportista, si lo hay.',
    )
    notas_cliente = models.TextField('notas del cliente', blank=True)
    notas_internas = models.TextField('notas internas', blank=True, help_text='Solo se ven en el panel.')

    creado = models.DateTimeField('fecha de creación', auto_now_add=True)
    fecha_pago = models.DateTimeField('fecha de pago', null=True, blank=True)
    fecha_entrega = models.DateTimeField('fecha de entrega', null=True, blank=True)
    stock_descontado = models.BooleanField('stock ya descontado', default=False, editable=False)
    # Reparto a la tienda (pagos/liquidaciones.py). Solo los toca `pagos.liquidaciones.liquidar`.
    liquidacion = models.ForeignKey(
        'pagos.Liquidacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos',
        editable=False, verbose_name='liquidación',
    )
    monto_liquidado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False)
    ajuste_liquidacion = models.ForeignKey(
        'pagos.Liquidacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='reembolsos_descontados',
        editable=False, help_text='Liquidación en la que se descontó este pedido por haberse reembolsado.',
    )
    ip = models.GenericIPAddressField('IP del cliente', null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'
        ordering = ['-creado', '-id']
        constraints = [
            models.CheckConstraint(
                condition=Q(metodo_entrega='recoger') | Q(zona__isnull=False),
                name='pedido_envio_requiere_zona',
            ),
            models.CheckConstraint(
                condition=~Q(metodo_pago='efectivo_recoger') | Q(metodo_entrega='recoger'),
                name='pedido_efectivo_recoger_solo_en_tienda',
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0) & Q(costo_envio__gte=0) & Q(total__gte=0) & Q(impuesto__gte=0),
                name='pedido_montos_no_negativos',
            ),
            models.CheckConstraint(
                condition=Q(descuento__gte=0) & Q(descuento__lte=F('subtotal')),
                name='pedido_descuento_no_supera_subtotal',
            ),
        ]
        indexes = [
            models.Index(fields=['tienda', '-creado'], name='pedido_tienda_creado_idx'),
            models.Index(fields=['estado', '-creado'], name='pedido_estado_creado_idx'),
            models.Index(fields=['-creado'], name='pedido_creado_idx'),
            models.Index(fields=['fecha_pago'], name='pedido_fecha_pago_idx'),
            models.Index(fields=['telefono'], name='pedido_telefono_idx'),
            models.Index(fields=['ip', '-creado'], name='pedido_ip_creado_idx'),
        ]

    def __str__(self):
        return self.numero

    def get_absolute_url(self):
        return reverse('pedidos:confirmacion', args=[self.token])

    @property
    def paga_por_transferencia(self):
        return self.metodo_pago == self.Pago.TRANSFERENCIA

    @property
    def recoge_en_tienda(self):
        return self.metodo_entrega == self.Entrega.RECOGER

    @property
    def etiqueta_impuesto(self):
        """'ITBIS (18%)', con el porcentaje que se aplico al comprar."""
        return f'ITBIS ({self.porcentaje_impuesto.normalize():f}%)'

    @property
    def direccion_completa(self):
        return ', '.join(parte for parte in (self.direccion, self.sector) if parte)

    @property
    def esta_pagado(self):
        return self.fecha_pago is not None and self.estado not in self.ESTADOS_SIN_VENTA


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles')
    nombre_producto = models.CharField('producto (al comprar)', max_length=150)
    precio_unitario = models.DecimalField('precio unitario (al comprar)', max_digits=12, decimal_places=2)
    cantidad = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    reserva_stock = models.BooleanField(
        'apartó stock', default=False, editable=False,
        help_text='El producto llevaba inventario al comprar: el pedido apartó sus unidades.',
    )

    class Meta:
        verbose_name = 'producto del pedido'
        verbose_name_plural = 'productos del pedido'
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gt=0), name='detalle_cantidad_positiva'),
            models.UniqueConstraint(fields=['pedido', 'producto'], name='detalle_producto_unico_por_pedido'),
        ]

    def __str__(self):
        return f'{self.cantidad} × {self.nombre_producto}'


class EventoPedido(models.Model):
    """Cada paso del pedido: lo ve el cliente como seguimiento y queda como registro de quien lo cambio."""

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='eventos')
    estado = models.CharField(max_length=12, choices=Pedido.Estado.choices)
    nota = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text='Quien hizo el cambio en el panel; vacío si fue el cliente o el sistema.',
    )
    creado = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'paso del pedido'
        verbose_name_plural = 'seguimiento del pedido'
        ordering = ['creado', 'id']

    def __str__(self):
        return f'{self.pedido_id}: {self.get_estado_display()}'


class SolicitudDevolucion(models.Model):
    """El cliente pide devolver un pedido entregado; la tienda la acepta o la rechaza."""

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Por revisar'
        ACEPTADA = 'aceptada', 'Aceptada'
        RECHAZADA = 'rechazada', 'Rechazada'

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='devoluciones', editable=False)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='devoluciones', editable=False)
    motivo = models.TextField(max_length=600)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    respuesta = models.CharField('respuesta de la tienda', max_length=255, blank=True)
    creado = models.DateTimeField('fecha de la solicitud', auto_now_add=True)
    resuelto_en = models.DateTimeField('fecha de respuesta', null=True, blank=True)
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        verbose_name='respondió',
    )

    class Meta:
        verbose_name = 'solicitud de devolución'
        verbose_name_plural = 'solicitudes de devolución'
        ordering = ['-creado', '-id']

    def __str__(self):
        return f'Devolución de {self.pedido}'
