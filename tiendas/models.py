from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse

from core.texto import generar_slug_unico, quitar_tildes
from core.validators import validar_imagen, validar_whatsapp

LARGO_PREFIJO = 5

validar_prefijo = RegexValidator(
    r'^[A-Z0-9]{2,5}$', 'Usa de 2 a 5 letras mayúsculas o números, sin espacios. Ejemplo: FIT',
)


class TiendaQuerySet(models.QuerySet):
    def activas(self):
        return self.filter(activa=True)


class Tienda(models.Model):
    """Subtienda de un vendedor: su marca, sus contactos, su forma de cobrar y la numeracion de sus pedidos.

    Los campos de marca y contacto se llaman igual que en ConfiguracionTienda para que las
    plantillas usen `tienda.<campo>` sin distinguir.
    """

    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(
        'dirección web', max_length=60, unique=True, blank=True,
        help_text='Parte del enlace de la tienda: /tienda/<esto>/. Se genera sola si la dejas vacía.',
    )
    prefijo = models.CharField(
        'prefijo de pedidos', max_length=LARGO_PREFIJO, unique=True, blank=True, validators=[validar_prefijo],
        help_text='Con él empiezan sus números de pedido (FIT-2026-00001). Vacío = se toma del nombre. '
                  'No se puede cambiar después.',
    )
    activa = models.BooleanField(
        default=True, help_text='Si la apagas, la tienda y sus productos dejan de verse en el sitio.',
    )
    orden = models.PositiveSmallIntegerField(default=0, help_text='Posición en el directorio de tiendas.')
    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='tiendas', verbose_name='vendedores',
        help_text='Usuarios que administran esta tienda. Al guardar reciben acceso al panel y solo ven lo de sus tiendas.',
    )

    logo = models.ImageField(
        upload_to='tiendas/', blank=True, validators=[validar_imagen],
        help_text='Si no subes un logo se muestra el nombre en texto.',
    )
    banner_titulo = models.CharField(
        'título del banner', max_length=120, blank=True, help_text='Vacío = se muestra el nombre de la tienda.',
    )
    banner_subtitulo = models.CharField(
        'subtítulo del banner', max_length=220, blank=True,
        help_text='Frase corta que describe la tienda. También se ve en el directorio de tiendas.',
    )
    banner_texto_boton = models.CharField('texto del botón del banner', max_length=40, default='Ver catálogo')
    banner_imagen = models.ImageField('imagen del banner', upload_to='tiendas/', blank=True, validators=[validar_imagen])

    correo = models.EmailField('correo de contacto', blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    horario = models.CharField(max_length=150, blank=True, help_text='Ej.: Lun a Sáb, 9:00 a.m. a 6:00 p.m.')
    whatsapp = models.CharField(
        'número de WhatsApp', max_length=15, blank=True, validators=[validar_whatsapp],
        help_text='Aquí llegan los pedidos. Solo dígitos, con código de país. Ej.: 18095551234',
    )
    direccion_tienda = models.CharField(
        'dirección para recoger', max_length=255, blank=True,
        help_text='Se muestra a quien elige recoger su pedido.',
    )
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)

    permitir_contra_entrega = models.BooleanField('permitir efectivo contra entrega', default=False)
    creada = models.DateTimeField('fecha de creación', auto_now_add=True)

    objects = TiendaQuerySet.as_manager()

    class Meta:
        verbose_name = 'tienda'
        verbose_name_plural = 'tiendas'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generar_slug_unico(self, self.nombre, largo=60)
        self.prefijo = (self.prefijo or '').strip().upper() or self._prefijo_libre()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('catalogo:inicio', args=[self.slug])

    def _prefijo_libre(self):
        """Tres primeras letras del nombre; si otra tienda ya las usa, les agrega un numero."""
        letras = ''.join(c for c in quitar_tildes(self.nombre).upper() if c.isascii() and c.isalnum())
        base = (letras[:3] or 'TDA').ljust(2, 'X')
        prefijo, numero = base, 2
        while Tienda.objects.filter(prefijo=prefijo).exclude(pk=self.pk).exists():
            sufijo = str(numero)
            prefijo = f'{base[:LARGO_PREFIJO - len(sufijo)]}{sufijo}'
            numero += 1
        return prefijo
