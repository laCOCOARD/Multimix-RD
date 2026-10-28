from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse

from core.archivos import NombreUnico
from core.telefonos import normalizar_whatsapp
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
    plantillas usen `marca.<campo>` sin distinguir entre una tienda y el sitio.
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
        upload_to=NombreUnico('tiendas'), blank=True, validators=[validar_imagen],
        help_text='JPG, PNG o WebP de hasta 5 MB. Si no subes un logo se muestra el nombre en texto.',
    )
    banner_titulo = models.CharField(
        'título del banner', max_length=120, blank=True, help_text='Vacío = se muestra el nombre de la tienda.',
    )
    banner_subtitulo = models.CharField(
        'subtítulo del banner', max_length=220, blank=True,
        help_text='Frase corta que describe la tienda. También se ve en el directorio de tiendas.',
    )
    banner_texto_boton = models.CharField('texto del botón del banner', max_length=40, default='Ver catálogo')
    banner_imagen = models.ImageField(
        'imagen del banner', upload_to=NombreUnico('tiendas'), blank=True, validators=[validar_imagen],
        help_text='JPG, PNG o WebP de hasta 5 MB. Es el fondo del banner de la tienda y de su tarjeta en la portada.',
    )

    correo = models.EmailField('correo de contacto', blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    horario = models.CharField(max_length=150, blank=True, help_text='Ej.: Lun a Sáb, 9:00 a.m. a 6:00 p.m.')
    whatsapp = models.CharField(
        'número de WhatsApp', max_length=20, blank=True, validators=[validar_whatsapp],
        help_text='Aquí llegan los pedidos. Ej.: 829-555-1234. A los números dominicanos se les agrega solo '
                  'el 1 del código de país.',
    )
    direccion_tienda = models.CharField(
        'dirección para recoger', max_length=255, blank=True,
        help_text='Se muestra a quien elige recoger su pedido.',
    )
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)

    permitir_contra_entrega = models.BooleanField('permitir efectivo contra entrega', default=False)
    envio_gratis_desde = models.DecimalField(
        'envío gratis desde', max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Los pedidos a domicilio con productos por este monto o más (después del cupón) no pagan envío. '
                  'Vacío = el envío se cobra siempre.',
    )
    dias_para_recoger = models.PositiveSmallIntegerField(
        'días para tener listo un pedido', default=1, validators=[MaxValueValidator(30)],
        help_text='Días hábiles (lunes a sábado) para que un pedido esté listo para recoger. 0 = el mismo día.',
    )
    dias_bajo_pedido = models.PositiveSmallIntegerField(
        'días extra de los productos bajo pedido', default=7, validators=[MaxValueValidator(90)],
        help_text='Días hábiles que se suman a la entrega cuando el pedido lleva productos bajo pedido.',
    )
    itbis_porcentaje = models.DecimalField(
        'ITBIS (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='0 = la tienda no cobra ITBIS aparte (lo normal). Con un porcentaje, se suma al confirmar el '
                  'pedido sobre los productos, después del descuento; el envío no lo paga.',
    )
    comision_porcentaje = models.DecimalField(
        'comisión del sitio (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Solo para liquidar los pedidos que cobró el sitio antes del 26 de octubre de 2026. Desde entonces '
                  'cada tienda cobra lo suyo y el sitio no se queda con un porcentaje de las ventas.',
    )
    # Plan y cobros del sitio a la tienda (pedido del dueño el 2026-10-26): ver la app `planes`.
    plan = models.ForeignKey(
        'planes.Plan', on_delete=models.PROTECT, null=True, blank=True, related_name='tiendas',
        help_text='Mensualidad, pedidos incluidos al mes y anuncios. Sin plan no se le cobra nada ni puede anunciarse.',
    )
    plan_desde = models.DateField('con este plan desde', null=True, blank=True, editable=False)
    cerrada_por_falta_de_pago = models.BooleanField(default=False, editable=False)
    cerrada_el = models.DateTimeField('cerrada el', null=True, blank=True, editable=False)
    habilitada_el = models.DateTimeField('habilitada otra vez el', null=True, blank=True, editable=False)
    creada = models.DateTimeField('fecha de creación', auto_now_add=True)

    objects = TiendaQuerySet.as_manager()

    class Meta:
        verbose_name = 'tienda'
        verbose_name_plural = 'tiendas'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

    def clean_fields(self, exclude=None):
        # Antes de validar: se aceptan el prefijo en minusculas y el WhatsApp con guiones o sin codigo de pais.
        self.prefijo = (self.prefijo or '').strip().upper()
        self.whatsapp = normalizar_whatsapp(self.whatsapp)
        super().clean_fields(exclude=exclude)

    @classmethod
    def from_db(cls, db, field_names, values):
        tienda = super().from_db(db, field_names, values)
        # Para saber al guardar si cambio el plan (y desde cuando lo tiene).
        tienda._plan_original = tienda.__dict__.get('plan_id')
        return tienda

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generar_slug_unico(self, self.nombre, largo=60)
        self.prefijo = (self.prefijo or '').strip().upper() or self._prefijo_libre()
        self.whatsapp = normalizar_whatsapp(self.whatsapp)
        if 'plan_id' in self.__dict__ and self.plan_id != getattr(self, '_plan_original', None):
            from django.utils import timezone

            self.plan_desde = timezone.localdate() if self.plan_id else None
            campos = kwargs.get('update_fields')
            if campos is not None:
                kwargs['update_fields'] = {*campos, 'plan_desde'}
        super().save(*args, **kwargs)
        self._plan_original = self.__dict__.get('plan_id')

    def get_absolute_url(self):
        return reverse('catalogo:inicio', args=[self.slug])

    @property
    def descripcion(self):
        """Frase que describe la tienda; el sitio tiene su propio campo con este nombre."""
        return self.banner_subtitulo

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


class CuentaBancaria(models.Model):
    """Cuenta de la tienda: a ella le transfieren sus clientes y ella confirma el pago (pedido del dueño el
    2026-10-26: cada tienda es responsable de sus pagos). Sin cuentas activas la tienda no ofrece transferencia."""

    class Tipo(models.TextChoices):
        AHORROS = 'ahorros', 'Ahorros'
        CORRIENTE = 'corriente', 'Corriente'

    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='cuentas')
    banco = models.CharField(max_length=80)
    tipo_cuenta = models.CharField('tipo de cuenta', max_length=10, choices=Tipo.choices, default=Tipo.AHORROS)
    numero = models.CharField('número de cuenta', max_length=30)
    titular = models.CharField(max_length=120)
    cedula_rnc = models.CharField('cédula o RNC', max_length=20, blank=True)
    activa = models.BooleanField(default=True, help_text='Solo las activas las ven tus clientes al pagar.')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'cuenta bancaria'
        verbose_name_plural = 'cuentas bancarias de la tienda'
        ordering = ['orden', 'banco']
        constraints = [
            models.UniqueConstraint(
                fields=['tienda', 'banco', 'numero'], name='cuenta_bancaria_unica_por_tienda',
                violation_error_message='Ya registraste esa cuenta de ese banco.',
            ),
        ]

    def __str__(self):
        return f'{self.banco} · {self.get_tipo_cuenta_display()} · {self.numero}'


def validar_enlace_interno_o_seguro(valor):
    """El boton de un banner lleva a una pagina del sitio (/tienda/...) o a una direccion https."""
    from django.core.exceptions import ValidationError

    if not (valor.startswith('/') and not valor.startswith('//')) and not valor.startswith('https://'):
        raise ValidationError('Usa una ruta del sitio (empieza con /) o una dirección que empiece con https://.')


class Banner(models.Model):
    """Promocion que rota en el inicio de la tienda. Sin banners activos se muestra el banner fijo de la tienda."""

    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='banners')
    titulo = models.CharField('título', max_length=120)
    subtitulo = models.CharField('subtítulo', max_length=220, blank=True)
    imagen = models.ImageField(
        upload_to=NombreUnico('banners'), blank=True, validators=[validar_imagen],
        help_text='JPG, PNG o WebP de hasta 5 MB, apaisada. Sin imagen se usa el color de la marca.',
    )
    texto_boton = models.CharField('texto del botón', max_length=40, blank=True)
    enlace = models.CharField(
        max_length=255, blank=True, validators=[validar_enlace_interno_o_seguro],
        help_text='A dónde lleva el botón. Ej.: /tienda/mi-tienda/catalogo/?oferta=on',
    )
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)
    vigente_desde = models.DateTimeField(null=True, blank=True)
    vigente_hasta = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'banner'
        verbose_name_plural = 'banners'
        ordering = ['orden', 'id']

    def __str__(self):
        return self.titulo

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.vigente_desde and self.vigente_hasta and self.vigente_hasta <= self.vigente_desde:
            raise ValidationError({'vigente_hasta': 'La vigencia debe terminar después de su inicio.'})


# Rubros generales para quien pide una tienda (pedido del dueño el 2026-10-27): no las categorias de los productos
# del sitio, que hoy son las de una sola tienda.
RUBROS = [
    ('alimentos', 'Alimentos y bebidas'),
    ('belleza', 'Belleza y cuidado personal'),
    ('barberia', 'Barbería y peluquería'),
    ('salud', 'Salud y bienestar'),
    ('moda', 'Ropa, calzado y accesorios'),
    ('joyeria', 'Joyería y relojes'),
    ('hogar', 'Hogar y decoración'),
    ('cocina', 'Cocina y utensilios'),
    ('limpieza', 'Detergentes y limpieza'),
    ('electronica', 'Electrónica y tecnología'),
    ('celulares', 'Celulares y accesorios'),
    ('electrodomesticos', 'Electrodomésticos'),
    ('musica', 'Música e instrumentos'),
    ('deportes', 'Deportes y fitness'),
    ('bebes', 'Bebés y niños'),
    ('juguetes', 'Juguetes y juegos'),
    ('mascotas', 'Mascotas'),
    ('ferreteria', 'Ferretería y construcción'),
    ('vehiculos', 'Vehículos, repuestos y accesorios'),
    ('papeleria', 'Papelería, oficina y escolar'),
    ('libros', 'Libros'),
    ('arte', 'Arte y manualidades'),
    ('regalos', 'Regalos, flores y detalles'),
    ('fiestas', 'Fiestas y eventos'),
    ('agricultura', 'Jardín y agricultura'),
    ('servicios', 'Servicios'),
    ('otro', 'Otro'),
]


class SolicitudTienda(models.Model):
    """Un negocio que pide abrir su tienda en el sitio (Fase 2 del rediseño, 2026-10-27).

    No crea cuentas ni da acceso al panel: las tiendas las sigue creando el administrador principal, que revisa la
    solicitud, contacta al negocio y, si la aprueba, crea la tienda (con los datos de la solicitud ya puestos) y le da
    acceso a sus vendedores como siempre. Los datos son privados: solo el administrador principal los ve.
    """

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        EN_REVISION = 'en_revision', 'En revisión'
        APROBADA = 'aprobada', 'Aprobada'
        RECHAZADA = 'rechazada', 'Rechazada'

    nombre_responsable = models.CharField('nombre del responsable', max_length=120)
    nombre_comercial = models.CharField('nombre comercial', max_length=80)
    correo = models.EmailField(max_length=150)
    telefono = models.CharField('teléfono', max_length=10, help_text='10 dígitos, sin guiones.')
    rubro = models.CharField('rubro del negocio', max_length=20, choices=RUBROS, default='otro')
    descripcion = models.TextField('qué vende')
    redes = models.CharField('redes o sitio web', max_length=200, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    notas = models.TextField(
        'notas internas', blank=True, help_text='Solo las ve el administrador principal; el negocio no las recibe.',
    )
    tienda = models.ForeignKey(
        Tienda, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes',
        help_text='La tienda que se creó a partir de esta solicitud, si se aprobó.',
    )
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', editable=False,
    )
    revisada_el = models.DateTimeField('revisada el', null=True, blank=True, editable=False)
    creada = models.DateTimeField('recibida el', auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'solicitud de tienda'
        verbose_name_plural = 'solicitudes de tiendas'
        ordering = ['-creada', '-id']
        indexes = [models.Index(fields=['estado', '-creada'], name='solicitud_estado_idx')]

    def __str__(self):
        return f'{self.nombre_comercial} ({self.get_estado_display().lower()})'
