"""Catalogo: secciones de la portada de cada tienda, filtros del listado y carga de fotos por SKU."""
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from PIL import Image

from core.models import ConfiguracionTienda
from core.texto import normalizar
from core.validators import validar_imagen
from pedidos.models import DetallePedido, Pedido

from .models import Categoria, FotoProducto, Producto, q_oferta_vigente


def clave_mas_vendidos(tienda):
    return f'catalogo_ids_mas_vendidos_{tienda.pk}'


def _base(tienda=None):
    """Productos a la venta de una tienda; sin tienda, los de todas las tiendas activas."""
    productos = Producto.objects.activos().para_listado()
    return productos if tienda is None else productos.filter(tienda=tienda)


def ids_mas_vendidos(tienda, limite=40):
    """Ids de productos de la tienda ordenados por unidades vendidas. Se guarda en cache unos minutos."""
    clave = clave_mas_vendidos(tienda)
    ids = cache.get(clave)
    if ids is None:
        ids = list(
            DetallePedido.objects.filter(pedido__tienda=tienda, pedido__estado__in=Pedido.ESTADOS_VENTA)
            .values('producto_id').annotate(unidades=Sum('cantidad'))
            .order_by('-unidades', 'producto_id').values_list('producto_id', flat=True)[:40]
        )
        cache.set(clave, ids, settings.MAS_VENDIDOS_CACHE_SEGUNDOS)
    return ids[:limite]


def mas_vendidos(tienda, limite=8):
    ids = ids_mas_vendidos(tienda)
    productos = _base(tienda).in_bulk(ids)
    return [productos[pk] for pk in ids if pk in productos][:limite]


def en_oferta(tienda, limite=8):
    return list(_base(tienda).filter(q_oferta_vigente()).order_by('-actualizado')[:limite])


def destacados(tienda, limite=8):
    return list(_base(tienda).filter(destacado=True)[:limite])


def q_nuevos():
    dias = ConfiguracionTienda.obtener().dias_producto_nuevo
    return Q(nuevo=True) | Q(creado__gte=timezone.now() - timedelta(days=dias))


def nuevos(tienda, limite=8):
    return list(_base(tienda).filter(q_nuevos())[:limite])


def categorias_de(tienda):
    """Categorias activas en las que la tienda tiene productos activos."""
    return Categoria.objects.filter(activa=True, productos__tienda=tienda, productos__activo=True).distinct()


def categorias_de_portada(tienda):
    """Categorias de la tienda para su portada. La que no tiene imagen muestra la foto de uno de sus productos."""
    foto = (
        FotoProducto.objects.filter(
            producto__categoria=OuterRef('pk'), producto__tienda=tienda, producto__activo=True, principal=True,
        )
        .order_by('-producto__destacado', '-producto__creado', '-producto__id').values('imagen')[:1]
    )
    categorias = list(categorias_de(tienda).annotate(foto_de_producto=Subquery(foto)))
    for categoria in categorias:
        categoria.usa_foto_de_producto = not categoria.imagen and bool(categoria.foto_de_producto)
        if categoria.imagen:
            categoria.url_portada = categoria.imagen.url
        elif categoria.foto_de_producto:
            categoria.url_portada = default_storage.url(categoria.foto_de_producto)
        else:
            categoria.url_portada = ''
    return categorias


def relacionados(producto, limite=4):
    """Otros productos de la misma tienda y categoria."""
    return list(
        _base().filter(tienda_id=producto.tienda_id, categoria_id=producto.categoria_id)
        .exclude(pk=producto.pk)[:limite]
    )


def filtrar_catalogo(filtros, categoria=None, tienda=None):
    """Aplica los filtros ya validados (FiltroCatalogoForm.cleaned_data) y el orden elegido.

    Con `tienda` lista su catalogo; sin ella busca en todas las tiendas activas (buscador del sitio).
    """
    productos = _base(tienda).con_datos_venta()
    if categoria is not None:
        productos = productos.filter(categoria=categoria)

    # Busqueda sin tildes ni mayusculas: deben aparecer todas las palabras escritas.
    for palabra in normalizar(filtros.get('q')).split():
        productos = productos.filter(texto_busqueda__contains=palabra)
    if filtros.get('precio_min') is not None:
        productos = productos.filter(precio_actual__gte=filtros['precio_min'])
    if filtros.get('precio_max') is not None:
        productos = productos.filter(precio_actual__lte=filtros['precio_max'])
    if filtros.get('oferta'):
        productos = productos.filter(oferta_vigente=True)
    if filtros.get('disponibles'):
        productos = productos.filter(disponible__gt=0)

    orden = filtros.get('orden')
    if orden == 'precio_asc':
        return productos.order_by('precio_actual', '-id')
    if orden == 'precio_desc':
        return productos.order_by('-precio_actual', '-id')
    if orden == 'vendidos':
        vendidos = Coalesce(
            Sum('detalles__cantidad', filter=Q(detalles__pedido__estado__in=Pedido.ESTADOS_VENTA)), 0,
        )
        return productos.annotate(vendidos=vendidos).order_by('-vendidos', '-creado', '-id')
    return productos.order_by('-creado', '-id')


# --- Fotos por SKU ---------------------------------------------------------------------

@dataclass
class FotoPorSku:
    archivo: str
    sku: str
    asignada: bool
    detalle: str


def _es_imagen(archivo):
    try:
        with Image.open(archivo) as imagen:
            imagen.verify()
    except Exception:
        return False
    finally:
        archivo.seek(0)
    return True


def asignar_foto_por_sku(archivo, tienda, reemplazar=False):
    """Pone el archivo como foto principal del producto de la tienda cuyo SKU es el nombre del archivo.

    `123785.jpg` va al producto con SKU 123785. Con `reemplazar` se borran las fotos que ya tenia.
    """
    sku = Path(archivo.name).stem.strip().upper()
    producto = Producto.objects.filter(tienda=tienda, sku=sku).first() if tienda else None
    if producto is None:
        return FotoPorSku(archivo.name, sku, False, 'No hay ningún producto con ese SKU.')
    try:
        validar_imagen(archivo)
    except ValidationError as error:
        return FotoPorSku(archivo.name, sku, False, ' '.join(error.messages))
    if not _es_imagen(archivo):
        return FotoPorSku(archivo.name, sku, False, 'El archivo no es una imagen válida.')

    nueva = FotoProducto.objects.create(producto=producto, imagen=archivo, principal=True)
    if reemplazar:
        # Se borran una a una para que tambien se elimine el archivo de cada foto.
        for anterior in producto.fotos.exclude(pk=nueva.pk):
            anterior.delete()
    return FotoPorSku(archivo.name, sku, True, producto.nombre)
