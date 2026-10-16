from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models

from .archivos import NombreUnico
from .telefonos import normalizar_whatsapp
from .validators import validar_imagen, validar_whatsapp

DESCRIPCION_DEL_SITIO = (
    'Tiendas de emprendedores en un solo lugar. Compra en línea y recibe tu pedido en casa o recógelo en la tienda.'
)


class ConfiguracionTienda(models.Model):
    """Ajustes generales del sitio que reune las tiendas. Siempre existe una sola fila (pk=1).

    La marca, los contactos y la forma de cobrar de cada vendedor estan en tiendas.Tienda.
    """

    CACHE_KEY = 'configuracion_tienda'
    # Corto a proposito: con varios procesos de Gunicorn cada uno tiene su propia cache.
    CACHE_SEGUNDOS = 60

    nombre = models.CharField('nombre del sitio', max_length=80, default='Multimix RD')
    logo = models.ImageField(
        upload_to=NombreUnico('tienda'), blank=True, validators=[validar_imagen],
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
    dias_devolucion = models.PositiveSmallIntegerField(
        'días para pedir una devolución', default=7,
        help_text='Días después de la entrega en que el cliente puede solicitar una devolución. 0 = no se ofrecen.',
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


class CuentaDelSitio(models.Model):
    """Cuenta del dueño del sitio. Todas las transferencias de todas las tiendas llegan aqui: es la unica cuenta que
    ve el cliente. Las tiendas no registran cuentas; el sitio les deposita lo suyo en la liquidacion."""

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
        verbose_name = 'cuenta bancaria del sitio'
        verbose_name_plural = 'cuentas bancarias del sitio'
        ordering = ['orden', 'banco']
        constraints = [
            models.UniqueConstraint(
                fields=['banco', 'numero'], name='cuenta_del_sitio_unica',
                violation_error_message='Ya registraste esa cuenta de ese banco.',
            ),
        ]

    def __str__(self):
        return f'{self.banco} · {self.get_tipo_cuenta_display()} · {self.numero}'


def cuentas_para_transferir():
    """Las cuentas que ve el cliente de cualquier tienda: siempre las del sitio."""
    return CuentaDelSitio.objects.filter(activa=True)


CACHE_CONTENIDO = 'contenido_del_pie'


class PaginaInformativa(models.Model):
    """Pagina de texto del sitio: privacidad, entregas, devoluciones... La escribe el administrador principal."""

    slug = models.SlugField('dirección web', max_length=60, unique=True, help_text='Queda en /pagina/<esto>/.')
    titulo = models.CharField('título', max_length=120)
    contenido = models.TextField(blank=True, help_text='Texto simple. Deja una línea en blanco entre párrafos.')
    publicada = models.BooleanField(
        default=False, help_text='Sin publicar solo la ve el administrador (vista previa) y no sale en el pie.',
    )
    orden = models.PositiveSmallIntegerField(default=0)
    actualizado = models.DateTimeField('última actualización', auto_now=True)

    class Meta:
        verbose_name = 'página informativa'
        verbose_name_plural = 'páginas informativas'
        ordering = ['orden', 'titulo']

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(CACHE_CONTENIDO)

    def delete(self, *args, **kwargs):
        resultado = super().delete(*args, **kwargs)
        cache.delete(CACHE_CONTENIDO)
        return resultado

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('core:pagina', args=[self.slug])


class PreguntaFrecuente(models.Model):
    pregunta = models.CharField(max_length=200)
    respuesta = models.TextField()
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'pregunta frecuente'
        verbose_name_plural = 'preguntas frecuentes'
        ordering = ['orden', 'id']

    def __str__(self):
        return self.pregunta

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(CACHE_CONTENIDO)

    def delete(self, *args, **kwargs):
        resultado = super().delete(*args, **kwargs)
        cache.delete(CACHE_CONTENIDO)
        return resultado


def contenido_del_pie():
    """Paginas publicadas y si hay preguntas frecuentes: lo que enlaza el pie de todas las paginas."""
    datos = cache.get(CACHE_CONTENIDO)
    if datos is None:
        datos = {
            'paginas': list(PaginaInformativa.objects.filter(publicada=True).values('slug', 'titulo')),
            'hay_preguntas': PreguntaFrecuente.objects.filter(activa=True).exists(),
        }
        cache.set(CACHE_CONTENIDO, datos, 300)
    return datos
