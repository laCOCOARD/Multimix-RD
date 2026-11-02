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
