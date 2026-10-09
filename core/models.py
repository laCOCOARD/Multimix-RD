from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models

from .telefonos import normalizar_whatsapp
from .validators import validar_imagen, validar_whatsapp

DESCRIPCION_DEL_SITIO = 'Tiendas de emprendedores en un solo lugar. Compra directo a cada tienda por WhatsApp.'


class ConfiguracionTienda(models.Model):
    """Ajustes generales del sitio que reune las tiendas. Siempre existe una sola fila (pk=1).

    La marca, los contactos y la forma de cobrar de cada vendedor estan en tiendas.Tienda.
    """

    CACHE_KEY = 'configuracion_tienda'
    # Corto a proposito: con varios procesos de Gunicorn cada uno tiene su propia cache.
    CACHE_SEGUNDOS = 60

    nombre = models.CharField('nombre del sitio', max_length=80, default='Multimix RD')
    logo = models.ImageField(
        upload_to='tienda/', blank=True, validators=[validar_imagen],
        help_text='JPG, PNG o WebP de hasta 5 MB. Si no subes un logo se muestra el símbolo con el nombre.',
    )
    descripcion = models.CharField(
        'descripción del sitio', max_length=220, blank=True, default=DESCRIPCION_DEL_SITIO,
        help_text='Frase corta sobre el sitio: sale al pie de la portada y en los buscadores como Google.',
    )
    correo = models.EmailField('correo de contacto', blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    horario = models.CharField(max_length=150, blank=True, help_text='Ej.: Lun a Sáb, 9:00 a.m. a 6:00 p.m.')
    whatsapp = models.CharField(
        'número de WhatsApp', max_length=20, blank=True, validators=[validar_whatsapp],
        help_text='Ej.: 829-555-1234. A los números dominicanos se les agrega solo el 1 del código de país.',
    )
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)

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

    class Meta:
        verbose_name = 'configuración general'
        verbose_name_plural = 'configuración general'

    def __str__(self):
        return f'Configuración de {self.nombre}'

    def clean_fields(self, exclude=None):
        # Antes de validar: se acepta el numero con guiones o sin el codigo de pais.
        self.whatsapp = normalizar_whatsapp(self.whatsapp)
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        self.pk = 1
        self.whatsapp = normalizar_whatsapp(self.whatsapp)
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

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='cuentas_bancarias')
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
            models.UniqueConstraint(
                fields=['tienda', 'banco', 'numero'], name='cuenta_unica_por_tienda',
                violation_error_message='Ya registraste esa cuenta de ese banco.',
            ),
        ]

    def __str__(self):
        return f'{self.banco} · {self.get_tipo_cuenta_display()} · {self.numero}'
