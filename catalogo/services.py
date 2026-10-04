"""Consultas del catalogo: secciones automaticas de la portada y filtros del listado."""
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import ConfiguracionTienda
from core.texto import normalizar
from pedidos.models import DetallePedido, Pedido

from .models import Producto, q_oferta_vigente

CACHE_MAS_VENDIDOS = 'catalogo_ids_mas_vendidos'


def _base():
    return Producto.objects.activos().para_listado()


def ids_mas_vendidos(limite=40):
    """Ids de productos ordenados por unidades vendidas. Se guarda en cache unos minutos."""
    ids = cache.get(CACHE_MAS_VENDIDOS)
    if ids is None:
        ids = list(
            DetallePedido.objects.filter(pedido__estado__in=Pedido.ESTADOS_VENTA)
            .values('producto_id').annotate(unidades=Sum('cantidad'))
            .order_by('-unidades', 'producto_id').values_list('producto_id', flat=True)[:40]
        )
        cache.set(CACHE_MAS_VENDIDOS, ids, settings.MAS_VENDIDOS_CACHE_SEGUNDOS)
    return ids[:limite]


def mas_vendidos(limite=8):
    ids = ids_mas_vendidos()
    productos = _base().in_bulk(ids)
    return [productos[pk] for pk in ids if pk in productos][:limite]


def en_oferta(limite=8):
    return list(_base().filter(q_oferta_vigente()).order_by('-actualizado')[:limite])


def destacados(limite=8):
    return list(_base().filter(destacado=True)[:limite])


def q_nuevos():
    dias = ConfiguracionTienda.obtener().dias_producto_nuevo
    return Q(nuevo=True) | Q(creado__gte=timezone.now() - timedelta(days=dias))


def nuevos(limite=8):
    return list(_base().filter(q_nuevos())[:limite])


def relacionados(producto, limite=4):
    return list(_base().filter(categoria_id=producto.categoria_id).exclude(pk=producto.pk)[:limite])


def filtrar_catalogo(filtros, categoria=None):
    """Aplica los filtros ya validados (FiltroCatalogoForm.cleaned_data) y el orden elegido."""
    productos = _base().con_datos_venta()
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
