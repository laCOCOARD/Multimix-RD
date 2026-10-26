"""Catalogo: secciones de la portada de cada tienda, filtros del listado y carga de fotos por SKU."""
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import Count, Exists, F, OuterRef, Q, Subquery, Sum, Window
from django.db.models.functions import Coalesce, RowNumber
from django.utils import timezone
from PIL import Image

from core.models import ConfiguracionTienda
from core.texto import normalizar
from core.validators import validar_imagen
from pedidos.models import DetallePedido, Pedido

from .models import Categoria, FotoProducto, Producto, q_comprable, q_oferta_vigente


def clave_mas_vendidos(tienda):
    return f'catalogo_ids_mas_vendidos_{tienda.pk}'


def _base(tienda=None, agrupar=True):
    """Productos a la venta de una tienda; sin tienda, los de todas las tiendas activas.

    Con `agrupar`, de cada grupo de variantes sale solo el principal: la ficha ofrece las demas.
    """
    productos = Producto.objects.activos().para_listado()
    if agrupar:
        productos = productos.sin_variantes_repetidas()
    return productos if tienda is None else productos.filter(tienda=tienda)


def opciones_de(producto):
    """Las variantes del grupo del producto (el principal primero) que siguen publicadas. Vacio si no tiene."""
    principal = producto.principal
    variantes = list(
        Producto.objects.activos().filter(variante_de=principal).order_by('nombre_variante', 'id')
    )
    if not variantes:
        return []
    return [principal, *variantes] if principal.activo else variantes


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
    """Categorias activas en las que la tienda tiene productos activos, propios o de sus subcategorias.

    Vienen ordenadas con cada subcategoria debajo de su categoria principal.
    """
    directos = Q(productos__tienda=tienda, productos__activo=True)
    en_subcategorias = Q(
        subcategorias__activa=True, subcategorias__productos__tienda=tienda, subcategorias__productos__activo=True,
    )
    return (
        Categoria.objects.filter(activa=True).filter(directos | en_subcategorias).distinct()
        .order_by(
            Coalesce('padre__orden', 'orden'), Coalesce('padre__nombre', 'nombre'),
            F('padre').asc(nulls_first=True), 'orden', 'nombre',
        )
    )


def marcas_de(tienda, categoria=None):
    """Marcas de los productos a la venta de la tienda (y de la categoria, si se pasa), en orden alfabetico."""
    productos = Producto.objects.activos().filter(tienda=tienda).exclude(marca='')
    if categoria is not None:
        # Una categoria principal muestra tambien lo de sus subcategorias.
        productos = productos.filter(Q(categoria=categoria) | Q(categoria__padre=categoria, categoria__activa=True))
    # Una misma marca escrita con otra capitalizacion cuenta una sola vez.
    marcas = {}
    for marca in productos.order_by('marca').values_list('marca', flat=True).distinct():
        marcas.setdefault(marca.casefold(), marca)
    return sorted(marcas.values(), key=str.casefold)


def sugerencias(texto, tienda=None, limite=6):
    """Productos para el desplegable del buscador: deben contener todas las palabras escritas."""
    palabras = normalizar(texto).split()
    if not palabras or max(len(palabra) for palabra in palabras) < 2:
        return []
    productos = _base(tienda)
    for palabra in palabras:
        productos = productos.filter(texto_busqueda__contains=palabra)
    return list(productos.order_by('-destacado', '-creado', '-id')[:limite])


def _foto_de_la_categoria(**filtros):
    """Subconsulta: la foto principal de un producto de la categoria (o de sus subcategorias), destacados primero."""
    return (
        FotoProducto.objects.filter(
            Q(producto__categoria=OuterRef('pk')) | Q(producto__categoria__padre=OuterRef('pk')),
            producto__activo=True, principal=True, **filtros,
        )
        .order_by('-producto__destacado', '-producto__creado', '-producto__id').values('imagen')[:1]
    )


def _con_imagen_de_portada(categorias):
    """Pone `url_portada` en cada categoria: su imagen o, si no tiene, la foto de uno de sus productos."""
    for categoria in categorias:
        categoria.usa_foto_de_producto = not categoria.imagen and bool(categoria.foto_de_producto)
        if categoria.imagen:
            categoria.url_portada = categoria.imagen.url
        elif categoria.foto_de_producto:
            categoria.url_portada = default_storage.url(categoria.foto_de_producto)
        else:
            categoria.url_portada = ''
    return categorias


def categorias_de_portada(tienda):
    """Categorias de la tienda para su portada. La que no tiene imagen muestra la foto de uno de sus productos."""
    foto = _foto_de_la_categoria(producto__tienda=tienda)
    return _con_imagen_de_portada(list(categorias_de(tienda).annotate(foto_de_producto=Subquery(foto))))


# --- Portada y menu del sitio (todas las tiendas) ----------------------------------------

def categorias_del_menu():
    """Categorias principales con algo a la venta en alguna tienda activa, propio o de sus subcategorias.

    Es la lista del menu del sitio y de la portada; cada una lleva al buscador del sitio filtrado por ella.
    Es perezosa: solo consulta si la plantilla la recorre.
    """
    a_la_venta = Producto.objects.activos().sin_variantes_repetidas()
    return (
        Categoria.objects.filter(activa=True, padre__isnull=True)
        .filter(Q(pk__in=a_la_venta.values('categoria_id')) | Q(pk__in=a_la_venta.values('categoria__padre_id')))
        .order_by('orden', 'nombre')
    )


def categorias_del_sitio():
    """Las categorias del menu para la portada del sitio, con cuantos productos tienen y una imagen.

    `total_productos` cuenta lo que muestra el buscador del sitio al filtrar por ella: sus productos y los de sus
    subcategorias, de todas las tiendas activas y una vez por grupo de variantes.
    """
    totales = dict(
        Producto.objects.activos().sin_variantes_repetidas()
        .annotate(principal=Coalesce('categoria__padre_id', 'categoria_id'))
        .order_by().values('principal').annotate(total=Count('id')).values_list('principal', 'total')
    )
    foto = _foto_de_la_categoria(producto__tienda__activa=True, producto__categoria__activa=True)
    categorias = list(categorias_del_menu().annotate(foto_de_producto=Subquery(foto)))
    for categoria in categorias:
        categoria.total_productos = totales.get(categoria.pk, 0)
    return _con_imagen_de_portada(categorias)


def _repartidos_entre_tiendas(productos, limite):
    """Lo mejor de cada tienda primero, luego lo segundo de cada una...: ninguna tienda llena la seleccion. Dentro de
    cada tienda se alternan sus categorias, para que no salga todo de una sola (lo ultimo que se cargo, por ejemplo).

    Con foto primero; despues destacados y lo mas nuevo. La base numera cada producto dentro de su tienda y su
    categoria; aqui se reparte con esos numeros y al final se traen solo los elegidos.
    """
    orden = [F('destacado').desc(), F('creado').desc(), F('id').desc()]
    candidatos = (
        productos.annotate(tiene_foto=Exists(FotoProducto.objects.filter(producto=OuterRef('pk'))))
        .annotate(puesto=Window(
            RowNumber(), partition_by=[F('tienda_id'), F('categoria_id')], order_by=[F('tiene_foto').desc(), *orden],
        ))
        .filter(puesto__lte=limite)
        .order_by(F('tiene_foto').desc(), 'puesto', *orden)
        .values_list('pk', 'tienda_id')
    )
    # Cada tienda con sus candidatos en orden (una categoria tras otra) y las tiendas por su mejor candidato.
    por_tienda = {}
    for pk, tienda_id in candidatos:
        por_tienda.setdefault(tienda_id, []).append(pk)
    filas = list(por_tienda.values())
    elegidos = []
    while len(elegidos) < limite and any(filas):
        for fila in filas:
            if fila and len(elegidos) < limite:
                elegidos.append(fila.pop(0))
    encontrados = productos.in_bulk(elegidos)
    return [encontrados[pk] for pk in elegidos if pk in encontrados]


def vitrina_del_sitio(limite=12, excluir=()):
    """Productos de todas las tiendas para la portada del sitio: solo lo que se puede comprar."""
    return _repartidos_entre_tiendas(_base().filter(q_comprable()).exclude(pk__in=excluir), limite)


def ofertas_del_sitio(limite=10):
    """Ofertas vigentes de todas las tiendas que se pueden comprar, repartidas entre las tiendas."""
    return _repartidos_entre_tiendas(_base().filter(q_oferta_vigente()).filter(q_comprable()), limite)


# Vistos recientemente (como en las grandes tiendas): ids en la sesion, el mas reciente primero.
CLAVE_VISTOS = 'vistos'
MAXIMO_VISTOS = 12


def recordar_visto(sesion, producto):
    anteriores = [pk for pk in sesion.get(CLAVE_VISTOS, []) if pk != producto.pk]
    sesion[CLAVE_VISTOS] = [producto.pk, *anteriores][:MAXIMO_VISTOS]


def vistos(sesion, tienda=None, excluir=None, limite=10):
    """Los productos que el visitante miro hace poco y siguen a la venta; dentro de una tienda, solo los suyos."""
    ids = [pk for pk in sesion.get(CLAVE_VISTOS, []) if pk != excluir]
    productos = _base(tienda, agrupar=False).in_bulk(ids)
    return [productos[pk] for pk in ids if pk in productos][:limite]


def oferta_por_terminar(producto, dias=7):
    """Fin de la oferta si termina dentro de pocos dias (para la cuenta regresiva); si no, None."""
    if producto.en_oferta and producto.oferta_fin and producto.oferta_fin - timezone.now() <= timedelta(days=dias):
        return producto.oferta_fin
    return None


def sugerencias_para_el_carrito(tienda, en_el_carrito, limite=10):
    """Para completar el pedido: de las categorias de lo que lleva, y si no alcanza, destacados de la tienda."""
    productos = _base(tienda).filter(q_comprable()).exclude(pk__in=en_el_carrito)
    categorias = Producto.objects.filter(pk__in=en_el_carrito).values('categoria_id')
    sugeridos = list(productos.filter(categoria_id__in=categorias)[:limite]) if en_el_carrito else []
    if len(sugeridos) < limite:
        ya = [p.pk for p in sugeridos]
        sugeridos += list(productos.exclude(pk__in=ya).order_by('-destacado', '-creado')[:limite - len(sugeridos)])
    return sugeridos


def relacionados(producto, limite=10):
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
        # Una categoria principal muestra tambien lo de sus subcategorias.
        productos = productos.filter(Q(categoria=categoria) | Q(categoria__padre=categoria, categoria__activa=True))

    # Busqueda sin tildes ni mayusculas: deben aparecer todas las palabras escritas.
    for palabra in normalizar(filtros.get('q')).split():
        productos = productos.filter(texto_busqueda__contains=palabra)
    if filtros.get('marca'):
        productos = productos.filter(marca__iexact=filtros['marca'].strip())
    if filtros.get('precio_min') is not None:
        productos = productos.filter(precio_actual__gte=filtros['precio_min'])
    if filtros.get('precio_max') is not None:
        productos = productos.filter(precio_actual__lte=filtros['precio_max'])
    if filtros.get('oferta'):
        productos = productos.filter(oferta_vigente=True)
    if filtros.get('disponibles'):
        productos = productos.filter(comprable=True)

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
