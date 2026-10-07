from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import BooleanField, Case, DecimalField, F, Q, Value, When
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

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


class Categoria(models.Model):
    """Las categorias son de todo el sitio: las administra el dueño y las comparten las tiendas."""

    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text='Se genera solo si lo dejas vacío.')
    descripcion = models.TextField('descripción', blank=True)
    imagen = models.ImageField(upload_to='categorias/', blank=True, validators=[validar_imagen])
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generar_slug_unico(self, self.nombre, largo=100)
        super().save(*args, **kwargs)


class ProductoQuerySet(models.QuerySet):
    def activos(self):
        """A la venta: producto, categoria y tienda encendidos."""
        return self.filter(activo=True, categoria__activa=True, tienda__activa=True)

    def con_datos_venta(self):
        """Anota precio_actual, oferta_vigente y disponible para filtrar y ordenar en la base."""
        vigente = q_oferta_vigente()
        return self.annotate(
            oferta_vigente=Case(When(vigente, then=Value(True)), default=Value(False), output_field=BooleanField()),
            precio_actual=Case(
                When(vigente, then=F('precio_oferta')), default=F('precio'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            disponible=F('stock_almacen') - F('stock_reservado'),
        )

    def para_listado(self):
        return self.select_related('categoria', 'tienda').prefetch_related('fotos')


class Producto(models.Model):
    tienda = models.ForeignKey('tiendas.Tienda', on_delete=models.PROTECT, related_name='productos')
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='productos', verbose_name='categoría',
    )
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, blank=True, help_text='Se genera solo si lo dejas vacío.')
    sku = models.CharField('SKU', max_length=40, help_text='Código del producto. No se repite dentro de la tienda.')
    descripcion = models.TextField('descripción', blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    precio_oferta = models.DecimalField(
        'precio de oferta', max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    oferta_inicio = models.DateTimeField('inicio de la oferta', null=True, blank=True)
    oferta_fin = models.DateTimeField('fin de la oferta', null=True, blank=True)
    stock_almacen = models.PositiveIntegerField('stock en almacén', default=0)
    stock_reservado = models.PositiveIntegerField(
        'stock reservado', default=0, editable=False,
        help_text='Unidades apartadas por pedidos sin entregar. Lo maneja el sistema.',
    )
    destacado = models.BooleanField(default=False)
    nuevo = models.BooleanField(default=False, help_text='Márcalo para mostrarlo siempre como nuevo.')
    activo = models.BooleanField(default=True)
    texto_busqueda = models.TextField(
        editable=False, default='',
        help_text='Nombre, SKU y descripción sin tildes; lo usa el buscador.',
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
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generar_slug_unico(self, self.nombre, largo=170, tienda=self.tienda_id)
        if self.sku:
            self.sku = self.sku.strip().upper()
        self.texto_busqueda = normalizar(f'{self.nombre} {self.sku} {self.descripcion}')
        campos = kwargs.get('update_fields')
        if campos is not None and {'nombre', 'sku', 'descripcion'} & set(campos):
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
    def agotado(self):
        return self.stock_disponible <= 0

    @property
    def stock_bajo(self):
        return 0 < self.stock_disponible <= ConfiguracionTienda.obtener().umbral_stock_bajo

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
