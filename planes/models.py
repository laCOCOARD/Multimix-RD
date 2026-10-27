"""Planes de las tiendas y lo que el sitio les cobra (pedido del dueño el 2026-10-26).

Cada tienda paga una mensualidad segun su plan, que tambien fija cuantos pedidos cobrados al mes incluye, el
porcentaje que se cobra sobre lo vendido en los pedidos de mas y cuantos anuncios puede tener en la portada. El
sitio ya no cobra a los clientes ni se queda con un porcentaje de cada venta: cada tienda cobra lo suyo.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from core.archivos import NombreUnico, almacenamiento_privado
from core.validators import validar_imagen


class Plan(models.Model):
    """Lo que paga una tienda cada mes y lo que incluye. Los asigna el administrador principal."""

    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(
        'descripción', max_length=200, blank=True, help_text='Frase corta que ve la tienda en su panel.',
    )
    mensualidad = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0'))],
        help_text='Lo que paga la tienda cada mes, en RD$. Vence el día 1. 0 = no se cobra mensualidad.',
    )
    pedidos_incluidos = models.PositiveIntegerField(
        'pedidos incluidos al mes', null=True, blank=True,
        help_text='Pedidos cobrados en un mes sin cargo extra. Vacío = sin límite.',
    )
    porcentaje_excedente = models.DecimalField(
        'porcentaje por los pedidos de más', max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Se cobra sobre lo vendido (productos menos descuento, sin el envío) en los pedidos que pasen del '
                  'límite del mes. Se calcula el día 1 y vence ese mismo día.',
    )
    anuncios_portada = models.PositiveSmallIntegerField(
        'anuncios en la portada', default=0,
        help_text='Banners que la tienda puede tener a la vez en la portada del sitio (los apruebas tú).',
    )
    productos_patrocinados = models.PositiveSmallIntegerField(
        'productos anunciados', default=0,
        help_text='Productos que la tienda puede mostrar como "Patrocinado" al inicio de la portada.',
    )
    activo = models.BooleanField(default=True, help_text='Apagado ya no se ofrece al asignar un plan.')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'plan'
        verbose_name_plural = 'planes'
        ordering = ['orden', 'mensualidad', 'nombre']

    def __str__(self):
        return self.nombre


class Cargo(models.Model):
    """Lo que una tienda le debe al sitio: la mensualidad de un mes, los pedidos de mas de un mes u otro cargo.

    La tienda transfiere a las cuentas del sitio y sube el comprobante; el administrador lo aprueba.
    """

    class Tipo(models.TextChoices):
        MENSUALIDAD = 'mensualidad', 'Mensualidad'
        EXCEDENTE = 'excedente', 'Pedidos de más'
        OTRO = 'otro', 'Otro cargo'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente de pago'
        EN_REVISION = 'en_revision', 'Comprobante en revisión'
        PAGADO = 'pagado', 'Pagado'
        ANULADO = 'anulado', 'Anulado'

    POR_PAGAR = (Estado.PENDIENTE, Estado.EN_REVISION)

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.PROTECT, related_name='cargos')
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.MENSUALIDAD)
    periodo = models.DateField('mes', help_text='Mes al que corresponde: su primer día.')
    concepto = models.CharField(max_length=160)
    detalle = models.TextField(blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    vence = models.DateField('vence el')
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    comprobante = models.ImageField(
        upload_to=NombreUnico('comprobantes-tiendas'), blank=True, validators=[validar_imagen],
        storage=almacenamiento_privado, help_text='Foto o captura de la transferencia que hizo la tienda.',
    )
    referencia = models.CharField('referencia de la transferencia', max_length=60, blank=True)
    enviado_el = models.DateTimeField('comprobante enviado el', null=True, blank=True)
    revisado_el = models.DateTimeField('revisado el', null=True, blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        verbose_name='revisado por',
    )
    nota = models.CharField(
        max_length=255, blank=True, help_text='Por qué se rechazó el comprobante o se anuló el cargo.',
    )
    # Recordatorios ya enviados (por_vencer, vence_hoy, ultimo_dia, cerrada): cada uno sale una sola vez.
    avisos = models.JSONField(default=list, blank=True, editable=False)
    creado = models.DateTimeField('fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'cargo'
        verbose_name_plural = 'mensualidades y cargos'
        ordering = ['-vence', '-id']
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name='cargo_monto_positivo'),
            # Una sola mensualidad y un solo excedente por tienda y mes; los cargos "otro" pueden repetirse.
            models.UniqueConstraint(
                fields=['tienda', 'tipo', 'periodo'], condition=~Q(tipo='otro'), name='un_cargo_por_tipo_y_mes',
            ),
        ]
        indexes = [models.Index(fields=['estado', 'vence'], name='cargo_estado_vence_idx')]

    def __str__(self):
        return f'{self.concepto} · {self.tienda}'

    @property
    def por_pagar(self):
        return self.estado in self.POR_PAGAR


@receiver(post_delete, sender=Cargo)
def borrar_comprobante_del_cargo(sender, instance, **kwargs):
    if instance.comprobante:
        almacenamiento_privado().delete(instance.comprobante.name)


class Anuncio(models.Model):
    """Banner de una tienda en la portada del sitio. Cuantos puede tener a la vez lo dice su plan, y sale solo
    cuando el administrador lo aprueba (cambiar el texto o la imagen pide aprobarlo otra vez)."""

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='anuncios')
    titulo = models.CharField('título', max_length=70)
    texto = models.CharField(max_length=140, blank=True)
    imagen = models.ImageField(
        upload_to=NombreUnico('anuncios'), validators=[validar_imagen],
        help_text='JPG, PNG o WebP de hasta 5 MB, apaisada (por ejemplo 1200 x 600). Se ve recortada al centro.',
    )
    producto = models.ForeignKey(
        'catalogo.Producto', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text='A dónde lleva el anuncio. Vacío = a la tienda.',
    )
    activo = models.BooleanField(default=True)
    aprobado = models.BooleanField(
        default=False, help_text='Solo los anuncios aprobados salen en la portada.',
    )
    revisado_el = models.DateTimeField('revisado el', null=True, blank=True, editable=False)
    orden = models.PositiveSmallIntegerField(default=0)
    vigente_desde = models.DateTimeField(null=True, blank=True)
    vigente_hasta = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField('fecha de creación', auto_now_add=True)
    actualizado = models.DateTimeField('última actualización', auto_now=True)

    # Si la tienda cambia alguno de estos, el anuncio vuelve a revision.
    CAMPOS_DEL_CONTENIDO = ('titulo', 'texto', 'imagen', 'producto')

    class Meta:
        verbose_name = 'anuncio en la portada'
        verbose_name_plural = 'anuncios en la portada'
        ordering = ['orden', '-creado', '-id']

    def __str__(self):
        return self.titulo

    def clean(self):
        errores = {}
        if self.producto_id and self.tienda_id and self.producto.tienda_id != self.tienda_id:
            errores['producto'] = 'Elige un producto de tu tienda.'
        if self.vigente_desde and self.vigente_hasta and self.vigente_hasta <= self.vigente_desde:
            errores['vigente_hasta'] = 'La vigencia debe terminar después de su inicio.'
        if self.activo and self.tienda_id:
            limite = self.tienda.plan.anuncios_portada if self.tienda.plan_id else 0
            activos = Anuncio.objects.filter(tienda_id=self.tienda_id, activo=True).exclude(pk=self.pk).count()
            if activos >= limite:
                errores['activo'] = (
                    f'Tu plan permite {limite} anuncio{"s" if limite != 1 else ""} activo{"s" if limite != 1 else ""} '
                    'a la vez. Apaga otro o pide un plan con más anuncios.'
                    if limite else 'Tu plan no incluye anuncios en la portada. Pide un plan que los incluya.'
                )
        if errores:
            raise ValidationError(errores)

    @property
    def vigente(self):
        ahora = timezone.now()
        return (not self.vigente_desde or self.vigente_desde <= ahora) and (not self.vigente_hasta or self.vigente_hasta >= ahora)

    def get_url(self):
        """El producto si sigue a la venta en una tienda activa; si no, la tienda."""
        if self.producto_id and self.producto.activo and self.producto.categoria.activa:
            return self.producto.get_absolute_url()
        return self.tienda.get_absolute_url()


@receiver(post_delete, sender=Anuncio)
def borrar_imagen_del_anuncio(sender, instance, **kwargs):
    if instance.imagen:
        instance.imagen.delete(save=False)
