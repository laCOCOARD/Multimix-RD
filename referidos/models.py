import uuid

from django.conf import settings
from django.db import models


def _codigo_unico():
    return uuid.uuid4().hex[:8].upper()


class CodigoReferido(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='codigo_referido', verbose_name='usuario',
    )
    codigo = models.CharField('código', max_length=12, unique=True, default=_codigo_unico)
    clics = models.PositiveIntegerField(default=0, editable=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'código de referido'
        verbose_name_plural = 'códigos de referido'

    def __str__(self):
        return f'{self.usuario} ({self.codigo})'


class Referido(models.Model):
    referente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='referidos_hechos', verbose_name='referente',
    )
    invitado = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='referido_por', verbose_name='invitado',
    )
    ip = models.GenericIPAddressField(null=True, blank=True, editable=False)
    creado = models.DateTimeField(auto_now_add=True)
    tienda_creada = models.BooleanField('creó tienda', default=False)

    class Meta:
        verbose_name = 'referido'
        verbose_name_plural = 'referidos'
        constraints = [
            models.UniqueConstraint(
                fields=['invitado'],
                condition=models.Q(invitado__isnull=False),
                name='referido_invitado_unico',
            )
        ]

    def __str__(self):
        return f'{self.referente} → {self.invitado or "pendiente"}'


class TiendaReferida(models.Model):
    """Una tienda que llego invitada por otra (pedido del dueño el 2026-11-02). Se crea al hacer la tienda desde una
    solicitud que traia el codigo. Cuenta como activa cuando el sitio aprueba su primera mensualidad pagada."""

    referente = models.ForeignKey(
        'tiendas.Tienda', on_delete=models.CASCADE, related_name='tiendas_invitadas', verbose_name='la invitó',
    )
    tienda = models.OneToOneField(
        'tiendas.Tienda', on_delete=models.CASCADE, related_name='invitada_por', verbose_name='tienda invitada',
    )
    codigo = models.CharField('código usado', max_length=12)
    activa_desde = models.DateTimeField(
        'activa desde', null=True, blank=True, help_text='Cuando se aprobó el pago de su primera mensualidad.',
    )
    cargo_con_descuento = models.ForeignKey(
        'planes.Cargo', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        verbose_name='mensualidad con su descuento de bienvenida',
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'tienda invitada'
        verbose_name_plural = 'tiendas invitadas'
        ordering = ['-creada']

    def __str__(self):
        return f'{self.tienda} (invitada por {self.referente})'


class PremioReferido(models.Model):
    """Lo que gana una tienda por cada 2 tiendas invitadas activas: un descuento en su proxima mensualidad (se usa
    dentro del plazo o se pierde) y anuncios extra en la portada por unos dias."""

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='premios_referidos')
    numero = models.PositiveSmallIntegerField('premio número')
    descuento = models.DecimalField('descuento (%)', max_digits=5, decimal_places=2)
    anuncios_extra = models.PositiveSmallIntegerField(default=1)
    anuncios_hasta = models.DateField('anuncios extra hasta')
    vence = models.DateField('el descuento se usa hasta')
    cargo = models.ForeignKey(
        'planes.Cargo', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        verbose_name='mensualidad donde se usó',
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'premio por referidos'
        verbose_name_plural = 'premios por referidos'
        ordering = ['-creado']
        constraints = [models.UniqueConstraint(fields=['tienda', 'numero'], name='premio_referido_unico')]

    def __str__(self):
        return f'Premio {self.numero} de {self.tienda}'
