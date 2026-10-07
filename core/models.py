from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models

from .validators import validar_imagen, validar_whatsapp


class ConfiguracionTienda(models.Model):
    """Ajustes generales de la tienda. Siempre existe una sola fila (pk=1)."""

    CACHE_KEY = 'configuracion_tienda'
    # Corto a proposito: con varios procesos de Gunicorn cada uno tiene su propia cache.
    CACHE_SEGUNDOS = 60

    nombre = models.CharField('nombre de la tienda', max_length=80, default='Multimix RD')
    logo = models.ImageField(
        upload_to='tienda/', blank=True, validators=[validar_imagen],
        help_text='Si no subes un logo se muestra el nombre en texto.',
    )
    correo = models.EmailField('correo de contacto', blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    horario = models.CharField(max_length=150, blank=True, help_text='Ej.: Lun a Sáb, 9:00 a.m. a 6:00 p.m.')
    whatsapp = models.CharField(
        'número de WhatsApp', max_length=15, blank=True, validators=[validar_whatsapp],
        help_text='Solo dígitos, con código de país. Ej.: 18095551234',
    )
    direccion_tienda = models.CharField(
        'dirección de la tienda', max_length=255, blank=True,
        help_text='Se muestra a quien elige recoger en tienda.',
    )
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)

    banner_titulo = models.CharField('título del banner', max_length=120, default='Tu tienda de bienestar')
    banner_subtitulo = models.CharField(
        'subtítulo del banner', max_length=220, blank=True,
        default='Salud, belleza y equilibrio: vitaminas, cuidado personal y más, con entrega en todo el país.',
    )
    banner_texto_boton = models.CharField('texto del botón del banner', max_length=40, default='Ver catálogo')
    banner_imagen = models.ImageField('imagen del banner', upload_to='tienda/', blank=True, validators=[validar_imagen])

    dias_producto_nuevo = models.PositiveSmallIntegerField(
        'días como producto nuevo', default=30,
        help_text='Días desde su creación en que un producto se muestra como nuevo.',
    )
    umbral_stock_bajo = models.PositiveSmallIntegerField(
        'umbral de stock bajo', default=5,
        help_text='Con esta cantidad o menos se avisa que queda poco.',
    )
    horas_vencimiento_pedido = models.PositiveSmallIntegerField(
        'horas para vencer pedidos pendientes', default=48, validators=[MinValueValidator(1)],
    )
    mostrar_cantidad_exacta = models.BooleanField(
        'mostrar la cantidad exacta disponible', default=False,
        help_text='Si está apagado solo se muestra "Disponible" o "Quedan X" cuando hay poco.',
    )
    permitir_contra_entrega = models.BooleanField('permitir efectivo contra entrega', default=False)

    class Meta:
        verbose_name = 'configuración de la tienda'
        verbose_name_plural = 'configuración de la tienda'

    def __str__(self):
        return f'Configuración de {self.nombre}'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.set(self.CACHE_KEY, self, self.CACHE_SEGUNDOS)

    def delete(self, *args, **kwargs):
        return 0, {}

    @classmethod
    def obtener(cls):
        config = cache.get(cls.CACHE_KEY)
        if config is None:
            config, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, config, cls.CACHE_SEGUNDOS)
        return config


class CuentaBancaria(models.Model):
    class Tipo(models.TextChoices):
        AHORROS = 'ahorros', 'Ahorros'
        CORRIENTE = 'corriente', 'Corriente'

    banco = models.CharField(max_length=80)
    tipo_cuenta = models.CharField('tipo de cuenta', max_length=10, choices=Tipo.choices, default=Tipo.AHORROS)
    numero = models.CharField('número de cuenta', max_length=30)
    titular = models.CharField(max_length=120)
    cedula_rnc = models.CharField('cédula o RNC', max_length=20, blank=True)
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'cuenta bancaria'
        verbose_name_plural = 'cuentas bancarias'
        ordering = ['orden', 'banco']
        constraints = [
            models.UniqueConstraint(fields=['banco', 'numero'], name='cuenta_banco_numero_unica'),
        ]

    def __str__(self):
        return f'{self.banco} · {self.get_tipo_cuenta_display()} · {self.numero}'
