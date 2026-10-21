from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.validators import validar_imagen


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


class FotoResena(models.Model):
    """Foto que el cliente sube con su reseña. Se publica junto con la reseña, cuando el administrador la aprueba."""

    MAXIMO = 3

    resena = models.ForeignKey(Resena, on_delete=models.CASCADE, related_name='fotos')
    imagen = models.ImageField(upload_to='resenas/%Y/%m/', validators=[validar_imagen])
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'foto de reseña'
        verbose_name_plural = 'fotos de reseñas'
        ordering = ['orden', 'id']

    def __str__(self):
        return f'Foto de la reseña {self.resena_id}'

    def save(self, *args, **kwargs):
        # Igual que las fotos de productos: WebP con nombre generado (Supabase rechaza tildes y ñ en el nombre).
        if self.imagen and not self.imagen._committed:
            from catalogo.imagenes import convertir_a_webp

            self.imagen.save(f'{uuid4().hex}.webp', convertir_a_webp(self.imagen.file), save=False)
        super().save(*args, **kwargs)


@receiver(post_delete, sender=FotoResena)
def borrar_archivo_de_foto(sender, instance, **kwargs):
    if instance.imagen:
        instance.imagen.delete(save=False)


class Pregunta(models.Model):
    """Pregunta de un cliente sobre un producto. Se publica cuando la tienda la responde desde el panel."""

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Sin responder'
        PUBLICADA = 'publicada', 'Respondida y publicada'
        OCULTA = 'oculta', 'Oculta'

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='preguntas', editable=False)
    producto = models.ForeignKey(
        'catalogo.Producto', on_delete=models.CASCADE, related_name='preguntas', editable=False,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preguntas', editable=False,
        verbose_name='cliente',
    )
    texto = models.TextField('pregunta', max_length=500)
    respuesta = models.TextField(
        max_length=1000, blank=True, help_text='Al guardar con respuesta, la pregunta se publica en la ficha del '
                                               'producto y el cliente recibe un correo.',
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, editable=False)
    creado = models.DateTimeField('fecha', auto_now_add=True)
    respondida_en = models.DateTimeField('respondida el', null=True, blank=True, editable=False)
    respondida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', editable=False,
        verbose_name='respondió',
    )

    class Meta:
        verbose_name = 'pregunta de cliente'
        verbose_name_plural = 'preguntas de clientes'
        ordering = ['-creado', '-id']
        indexes = [models.Index(fields=['producto', 'estado', '-creado'], name='pregunta_producto_estado_idx')]

    def __str__(self):
        return self.texto[:60]

    @property
    def autor(self):
        nombre = (self.usuario.first_name or '').split()
        return nombre[0] if nombre else 'Cliente'
