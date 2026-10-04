from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Cupon(models.Model):
    class Tipo(models.TextChoices):
        PORCENTAJE = 'porcentaje', 'Porcentaje'
        MONTO_FIJO = 'monto_fijo', 'Monto fijo'

    codigo = models.CharField('código', max_length=30, unique=True, help_text='Se guarda en mayúsculas.')
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.PORCENTAJE)
    valor = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Porcentaje (1 a 100) o monto en RD$, según el tipo.',
    )
    compra_minima = models.DecimalField(
        'compra mínima', max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    vigente_desde = models.DateTimeField(null=True, blank=True)
    vigente_hasta = models.DateTimeField(null=True, blank=True)
    usos_maximos = models.PositiveIntegerField('usos máximos', null=True, blank=True, help_text='Vacío = ilimitado.')
    usos_actuales = models.PositiveIntegerField(default=0, editable=False)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'cupón'
        verbose_name_plural = 'cupones'
        ordering = ['codigo']
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name='cupon_valor_positivo'),
            models.CheckConstraint(
                condition=~Q(tipo='porcentaje') | Q(valor__lte=100),
                name='cupon_porcentaje_maximo_100',
            ),
        ]

    def __str__(self):
        return self.codigo

    def clean(self):
        errores = {}
        if self.tipo == self.Tipo.PORCENTAJE and self.valor is not None and self.valor > 100:
            errores['valor'] = 'Un cupón de porcentaje no puede superar 100.'
        if self.vigente_desde and self.vigente_hasta and self.vigente_hasta <= self.vigente_desde:
            errores['vigente_hasta'] = 'La vigencia debe terminar después de su inicio.'
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or '').strip().upper()
        super().save(*args, **kwargs)

    @property
    def usos_restantes(self):
        if self.usos_maximos is None:
            return None
        return max(self.usos_maximos - self.usos_actuales, 0)

    @property
    def vigente(self):
        ahora = timezone.now()
        if self.vigente_desde and self.vigente_desde > ahora:
            return False
        if self.vigente_hasta and self.vigente_hasta < ahora:
            return False
        return True
