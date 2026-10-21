from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Avg, BooleanField, Case, Count, DecimalField, F, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from core.archivos import NombreUnico
from core.models import ConfiguracionTienda
from core.texto import generar_slug_unico, normalizar
from core.validators import validar_imagen

from .imagenes import convertir_a_webp


def q_oferta_vigente(ahora=None):
    """Condicion ORM equivalente a la propiedad Producto.en_oferta."""
    ahora = ahora or timezone.now()
    return (
        Q(precio_oferta__isnull=False)
        & (Q(oferta_inicio__isnull=True) | Q(oferta_inicio__lte=ahora))
        & (Q(oferta_fin__isnull=True) | Q(oferta_fin__gte=ahora))
    )


class Disponibilidad(models.TextChoices):
    """Lo que el vendedor dice del producto. No depende de llevar inventario."""

    DISPONIBLE = 'disponible', 'Disponible'
    BAJO_PEDIDO = 'bajo_pedido', 'Bajo pedido'
    AGOTADO = 'agotado', 'Agotado'
    NO_DISPONIBLE = 'no_disponible', 'Temporalmente no disponible'


# Con estas el cliente puede comprar; las otras dos muestran el producto sin boton de compra.
EN_VENTA = (Disponibilidad.DISPONIBLE, Disponibilidad.BAJO_PEDIDO)


def q_con_existencias():
    """Sin inventario siempre hay; con inventario, mientras quede algo sin reservar."""
    return Q(controla_stock=False) | Q(stock_almacen__gt=F('stock_reservado'))


def q_comprable():
    """Condicion ORM equivalente a la propiedad Producto.se_puede_comprar."""
    return Q(disponibilidad__in=EN_VENTA) & q_con_existencias()


def q_agotado():
    """Marcado como agotado por el vendedor o, si lleva inventario, sin unidades."""
    return Q(disponibilidad=Disponibilidad.AGOTADO) | (Q(disponibilidad__in=EN_VENTA) & ~q_con_existencias())


class Categoria(models.Model):
    """Las categorias son de todo el sitio: las administra el dueño y las comparten las tiendas."""

    nombre = models.CharField(max_length=80, unique=True)
    padre = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='subcategorias',
        verbose_name='categoría principal',
        help_text='Déjalo vacío para una categoría principal. Elige una para que esta sea su subcategoría.',
    )
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text='Se genera solo si lo dejas vacío.')
    descripcion = models.TextField('descripción', blank=True)
    imagen = models.ImageField(upload_to=NombreUnico('categorias'), blank=True, validators=[validar_imagen])
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

    def clean(self):
        """Solo hay dos niveles: categoria principal y subcategoria."""
        if self.padre_id is None:
            return
        if self.padre_id == self.pk:
            raise ValidationError({'padre': 'Una categoría no puede ser su propia subcategoría.'})
        if self.padre.padre_id is not None:
            raise ValidationError({'padre': 'Elige una categoría principal, no una subcategoría.'})
        if self.pk and self.subcategorias.exists():
            raise ValidationError({'padre': 'Esta categoría ya tiene subcategorías: no puede ser subcategoría de otra.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generar_slug_unico(self, self.nombre, largo=100)
        super().save(*args, **kwargs)


class ProductoQuerySet(models.QuerySet):
    def activos(self):
        """A la venta: producto, categoria y tienda encendidos."""
        return self.filter(activo=True, categoria__activa=True, tienda__activa=True)

    def con_datos_venta(self):
        """Anota precio_actual, oferta_vigente y comprable para filtrar y ordenar en la base."""
        vigente = q_oferta_vigente()
        return self.annotate(
            oferta_vigente=Case(When(vigente, then=Value(True)), default=Value(False), output_field=BooleanField()),
            precio_actual=Case(
                When(vigente, then=F('precio_oferta')), default=F('precio'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            comprable=Case(When(q_comprable(), then=Value(True)), default=Value(False), output_field=BooleanField()),
        )

    def para_listado(self):
        return self.select_related('categoria', 'tienda').prefetch_related('fotos').con_valoracion().con_variantes()

    def sin_variantes_repetidas(self):
        """Para los listados: de cada grupo de variantes, solo el principal (si el principal no se vende, sus
        variantes salen sueltas)."""
        return self.filter(Q(variante_de__isnull=True) | Q(variante_de__activo=False))

    def con_variantes(self):
        """`total_variantes`: cuantas variantes a la venta tiene cada producto, para el "N opciones" de la tarjeta."""
        variantes = (
            Producto.objects.filter(variante_de=OuterRef('pk'), activo=True).order_by()
            .values('variante_de').annotate(total=Count('id')).values('total')[:1]
        )
        return self.annotate(total_variantes=Coalesce(Subquery(variantes), 0, output_field=models.IntegerField()))

    def con_valoracion(self):
        """Promedio y cantidad de reseñas publicadas, para las estrellas de las tarjetas. Con subconsultas: un
        JOIN repetiria filas al combinarse con otros agregados del listado."""
        from opiniones.models import Resena

        publicadas = Resena.objects.filter(producto=OuterRef('pk'), estado=Resena.Estado.APROBADA).values('producto')
        return self.annotate(
            valoracion_promedio=Subquery(publicadas.annotate(valor=Avg('estrellas')).values('valor')[:1]),
            valoracion_total=Coalesce(
                Subquery(publicadas.annotate(valor=Count('id')).values('valor')[:1]), 0,
                output_field=models.IntegerField(),
            ),
        )


class Producto(models.Model):
    Disponibilidad = Disponibilidad

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.PROTECT, related_name='productos')
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='productos', verbose_name='categoría',
    )
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, blank=True, help_text='Se genera solo si lo dejas vacío.')
    sku = models.CharField('SKU', max_length=40, help_text='Código del producto. No se repite dentro de la tienda.')
    marca = models.CharField(
        max_length=60, blank=True, help_text='Marca o fabricante. Los clientes pueden filtrar el catálogo por marca.',
    )
    descripcion = models.TextField('descripción', blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    precio_oferta = models.DecimalField(
        'precio de oferta', max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    exento_itbis = models.BooleanField(
        'exento de ITBIS', default=False, help_text='Márcalo si este producto no paga ITBIS.',
    )
    oferta_inicio = models.DateTimeField('inicio de la oferta', null=True, blank=True)
    oferta_fin = models.DateTimeField('fin de la oferta', null=True, blank=True)
    disponibilidad = models.CharField(
        max_length=15, choices=Disponibilidad.choices, default=Disponibilidad.DISPONIBLE,
        help_text='"Disponible" y "Bajo pedido" se pueden comprar; las otras dos muestran el producto sin botón de compra.',
    )
    controla_stock = models.BooleanField(
        'llevar inventario', default=False,
        help_text='Márcalo solo si cuentas las unidades de este producto: se venderá hasta agotar el stock. '
                  'Sin marcar, el stock se ignora y manda la disponibilidad.',
    )
    stock_almacen = models.PositiveIntegerField('stock en almacén', default=0)
    stock_reservado = models.PositiveIntegerField(
        'stock reservado', default=0, editable=False,
        help_text='Unidades apartadas por pedidos sin entregar. Lo maneja el sistema.',
    )
    # Variantes (talla, color, tamaño): cada una es un producto con su SKU, precio y disponibilidad, agrupado bajo
    # el principal. Los listados muestran solo el principal y la ficha ofrece las opciones.
    variante_de = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='variantes',
        verbose_name='variante de',
        help_text='Si este producto es otra talla, color o tamaño de otro, elige aquí el producto principal.',
    )
    nombre_variante = models.CharField(
        'opción', max_length=40, blank=True,
        help_text='Lo que distingue esta variante: "Rojo", "Talla M", "500 ml". En el principal, su propia opción.',
    )
    tipo_variante = models.CharField(
        'tipo de opción', max_length=30, blank=True,
        help_text='Solo en el producto principal: "Color", "Talla", "Tamaño"... Vacío = "Opción".',
    )
    destacado = models.BooleanField(default=False)
    nuevo = models.BooleanField(default=False, help_text='Márcalo para mostrarlo siempre como nuevo.')
    activo = models.BooleanField(default=True)
    texto_busqueda = models.TextField(
        editable=False, default='',
        help_text='Nombre, marca, SKU y descripción sin tildes; lo usa el buscador.',
    )
    creado = models.DateTimeField('fecha de creación', auto_now_add=True)
    actualizado = models.DateTimeField('última actualización', auto_now=True)

    objects = ProductoQuerySet.as_manager()

    class Meta:
        verbose_name = 'producto'
        verbose_name_plural = 'productos'
        ordering = ['-creado', '-id']
        constraints = [
            models.CheckConstraint(condition=Q(precio__gt=0), name='producto_precio_positivo'),
            models.CheckConstraint(
                condition=Q(precio_oferta__isnull=True) | (Q(precio_oferta__gt=0) & Q(precio_oferta__lt=F('precio'))),
                name='producto_oferta_menor_que_precio',
            ),
            models.CheckConstraint(
                condition=Q(stock_reservado__lte=F('stock_almacen')),
                name='producto_reservado_no_supera_almacen',
            ),
            models.UniqueConstraint(
                fields=['tienda', 'sku'], name='producto_sku_unico_por_tienda',
                violation_error_message='Ya tienes un producto con ese SKU.',
            ),
            models.UniqueConstraint(
                fields=['tienda', 'slug'], name='producto_slug_unico_por_tienda',
                violation_error_message='Ya tienes un producto con ese slug.',
            ),
        ]
        indexes = [
            models.Index(fields=['tienda', 'activo', '-creado'], name='producto_tienda_activo_idx'),
            models.Index(fields=['activo', '-creado'], name='producto_activo_creado_idx'),
            models.Index(fields=['activo', 'destacado'], name='producto_activo_destacado_idx'),
            models.Index(fields=['categoria', 'activo'], name='producto_categoria_activo_idx'),
            models.Index(fields=['precio'], name='producto_precio_idx'),
            models.Index(fields=['tienda', 'disponibilidad'], name='producto_disponibilidad_idx'),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        errores = {}
        if self.precio_oferta is not None and self.precio is not None and self.precio_oferta >= self.precio:
            errores['precio_oferta'] = 'El precio de oferta debe ser menor que el precio normal.'
        if self.oferta_inicio and self.oferta_fin and self.oferta_fin <= self.oferta_inicio:
            errores['oferta_fin'] = 'La oferta debe terminar después de su inicio.'
        if self.stock_almacen is not None and self.stock_reservado > self.stock_almacen:
            errores['stock_almacen'] = (
                f'Hay {self.stock_reservado} unidades reservadas por pedidos; '
                'el almacén no puede quedar por debajo de esa cantidad.'
            )
        errores.update(self._errores_de_variante())
        if errores:
            raise ValidationError(errores)

    def _errores_de_variante(self):
        """Un solo nivel: el principal no es variante de otro, y todo queda dentro de la misma tienda."""
        principal = self.variante_de
        if principal is None:
            return {}
        if self.pk and principal.pk == self.pk:
            return {'variante_de': 'Un producto no puede ser variante de sí mismo.'}
        if principal.tienda_id != self.tienda_id:
            return {'variante_de': 'Elige un producto de la misma tienda.'}
        if principal.variante_de_id is not None:
            return {'variante_de': 'Elige el producto principal, no otra variante.'}
        if self.pk and Producto.objects.filter(variante_de=self).exists():
            return {'variante_de': 'Este producto ya tiene variantes: no puede ser variante de otro.'}
        if not self.nombre_variante.strip():
            return {'nombre_variante': 'Escribe la opción de esta variante (por ejemplo "Rojo" o "Talla M").'}
        return {}

    @property
    def principal(self):
        return self.variante_de or self

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generar_slug_unico(self, self.nombre, largo=170, tienda=self.tienda_id)
        if self.sku:
            self.sku = self.sku.strip().upper()
        self.marca = ' '.join((self.marca or '').split())
        self.texto_busqueda = normalizar(f'{self.nombre} {self.marca} {self.sku} {self.descripcion}')
        campos = kwargs.get('update_fields')
        if campos is not None and {'nombre', 'marca', 'sku', 'descripcion'} & set(campos):
            kwargs['update_fields'] = {*campos, 'texto_busqueda'}
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('catalogo:producto', args=[self.tienda.slug, self.slug])

    @property
    def stock_disponible(self):
        return max(self.stock_almacen - self.stock_reservado, 0)

    @property
    def en_oferta(self):
        if self.precio_oferta is None or self.precio_oferta >= self.precio:
            return False
        ahora = timezone.now()
        if self.oferta_inicio and self.oferta_inicio > ahora:
            return False
        if self.oferta_fin and self.oferta_fin < ahora:
            return False
        return True

    @property
    def precio_final(self):
        return self.precio_oferta if self.en_oferta else self.precio

    @property
    def porcentaje_descuento(self):
        if not self.en_oferta:
            return 0
        return int(round((1 - self.precio_oferta / self.precio) * 100))

    @property
    def es_nuevo(self):
        if self.nuevo:
            return True
        if not self.creado:
            return False
        dias = ConfiguracionTienda.obtener().dias_producto_nuevo
        return self.creado >= timezone.now() - timedelta(days=dias)

    @property
    def se_puede_comprar(self):
        if self.disponibilidad not in EN_VENTA:
            return False
        return not self.controla_stock or self.stock_disponible > 0

    @property
    def estado_venta(self):
        """La disponibilidad que ve el cliente: la del vendedor, o Agotado si lleva inventario y no queda."""
        if self.disponibilidad in EN_VENTA and not self.se_puede_comprar:
            return Disponibilidad.AGOTADO
        return Disponibilidad(self.disponibilidad)

    @property
    def bajo_pedido(self):
        return self.estado_venta == Disponibilidad.BAJO_PEDIDO

    @property
    def agotado(self):
        """No se puede comprar ahora, por la razon que sea; `estado_venta` dice cual."""
        return not self.se_puede_comprar

    @property
    def limite_compra(self):
        """Unidades que caben en un carrito: el tope por producto y, si lleva inventario, lo que queda."""
        if not self.se_puede_comprar:
            return 0
        if not self.controla_stock:
            return settings.CARRITO_MAX_POR_PRODUCTO
        return min(self.stock_disponible, settings.CARRITO_MAX_POR_PRODUCTO)

    @property
    def stock_bajo(self):
        if not self.controla_stock or not self.se_puede_comprar:
            return False
        return self.stock_disponible <= ConfiguracionTienda.obtener().umbral_stock_bajo

    @property
    def foto_principal(self):
        """Usa las fotos precargadas (prefetch_related) si las hay, sin consultas extra."""
        fotos = sorted(self.fotos.all(), key=lambda f: (not f.principal, f.orden, f.pk))
        return fotos[0] if fotos else None

    @property
    def fotos_ordenadas(self):
        return sorted(self.fotos.all(), key=lambda f: (not f.principal, f.orden, f.pk))


class FotoProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='fotos')
    imagen = models.ImageField(
        upload_to='productos/%Y/%m/', validators=[validar_imagen],
        help_text='JPG, PNG o WebP de hasta 5 MB. Se ajusta a 1200 px y se guarda en WebP.',
    )
    orden = models.PositiveSmallIntegerField(default=0)
    principal = models.BooleanField(default=False, help_text='Es la foto que se ve en las tarjetas.')

    class Meta:
        verbose_name = 'foto de producto'
        verbose_name_plural = 'fotos de producto'
        ordering = ['-principal', 'orden', 'id']

    def __str__(self):
        return f'Foto de {self.producto}'

    def save(self, *args, **kwargs):
        if self.imagen and not self.imagen._committed:
            contenido = convertir_a_webp(self.imagen.file)
            self.imagen.save(f'{uuid4().hex}.webp', contenido, save=False)
        otras = FotoProducto.objects.filter(producto_id=self.producto_id).exclude(pk=self.pk)
        if self.principal:
            otras.filter(principal=True).update(principal=False)
        elif not otras.filter(principal=True).exists():
            self.principal = True
        super().save(*args, **kwargs)


@receiver(post_delete, sender=FotoProducto)
def borrar_archivo_de_foto(sender, instance, **kwargs):
    if instance.imagen:
        instance.imagen.delete(save=False)


class AvisoDisponible(models.Model):
    """"Avisame cuando este disponible": el correo al que se avisa cuando el producto vuelve a venderse."""

    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE, related_name='avisos_disponible', editable=False)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='avisos_disponible', editable=False)
    correo = models.EmailField(editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', editable=False,
        verbose_name='cuenta',
    )
    creado = models.DateTimeField('pedido el', auto_now_add=True)
    avisado = models.DateTimeField('avisado el', null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'aviso de disponibilidad'
        verbose_name_plural = 'clientes esperando un producto'
        ordering = ['-creado', '-id']
        constraints = [
            models.UniqueConstraint(fields=['producto', 'correo'], name='aviso_disponible_unico_por_correo'),
        ]
        indexes = [models.Index(fields=['producto', 'avisado'], name='aviso_producto_pendiente_idx')]

    def __str__(self):
        return f'{self.correo} espera {self.producto}'
