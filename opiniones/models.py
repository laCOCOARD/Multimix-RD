from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Resena(models.Model):
    """Opinion de un cliente con cuenta sobre un producto. Solo se publica cuando el administrador la aprueba."""

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Por revisar'
        APROBADA = 'aprobada', 'Publicada'
        RECHAZADA = 'rechazada', 'Rechazada'

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='resenas', editable=False)
    producto = models.ForeignKey('catalogo.Producto', on_delete=models.CASCADE, related_name='resenas', editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resenas', editable=False,
        verbose_name='cliente',
    )
    estrellas = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.TextField(max_length=1000)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    compra_verificada = models.BooleanField(
        default=False, editable=False,
        help_text='El cliente recibió este producto en un pedido hecho con su cuenta.',
    )
    creado = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'reseña'
        verbose_name_plural = 'reseñas'
        ordering = ['-creado', '-id']
        constraints = [
            models.UniqueConstraint(fields=['producto', 'usuario'], name='una_resena_por_cliente_y_producto'),
            models.CheckConstraint(condition=models.Q(estrellas__gte=1, estrellas__lte=5), name='resena_de_1_a_5_estrellas'),
        ]
        indexes = [models.Index(fields=['producto', 'estado', '-creado'], name='resena_producto_estado_idx')]

    def __str__(self):
        return f'{self.estrellas} estrellas a {self.producto}'

    @property
    def autor(self):
        """Solo el primer nombre: la reseña es publica."""
        nombre = (self.usuario.first_name or '').split()
        return nombre[0] if nombre else 'Cliente'
