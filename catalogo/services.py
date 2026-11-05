"""Catalogo: secciones de la portada de cada tienda, filtros del listado y carga de fotos por SKU."""
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import CharField, Count, Exists, F, OuterRef, Q, Subquery, Sum, Value, Window
from django.db.models.functions import Coalesce, NullIf, RowNumber
from django.utils import timezone
from PIL import Image

from core.models import ConfiguracionTienda
from core.texto import normalizar
from core.validators import validar_imagen
from pedidos.models import DetallePedido, Pedido

from .models import Categoria, FotoProducto, Producto, q_comprable, q_oferta_vigente

logger = logging.getLogger('multimix.catalogo')


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
        .order_by('-producto__destacado', '-producto__creado', '-producto__id')
        .annotate(ruta=Coalesce(NullIf('miniatura', Value('')), 'imagen', output_field=CharField()))
        .values('ruta')[:1]
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
    if limite <= 0:
        return []
    return _repartidos_entre_tiendas(_base().filter(q_comprable()).exclude(pk__in=excluir), limite)


def ofertas_del_sitio(limite=10, excluir=()):
    """Ofertas vigentes de todas las tiendas que se pueden comprar, repartidas entre las tiendas."""
    return _repartidos_entre_tiendas(
        _base().filter(q_oferta_vigente()).filter(q_comprable()).exclude(pk__in=excluir), limite,
    )


def nuevos_del_sitio(limite=12, excluir=()):
    """Lo nuevo de todas las tiendas que se puede comprar, repartido entre las tiendas."""
    return _repartidos_entre_tiendas(_base().filter(q_comprable(), q_nuevos()).exclude(pk__in=excluir), limite)


def estantes_del_sitio(categorias, por_categoria=8):
    """Portada al estilo de las grandes tiendas (pedido del dueño el 2026-11-02): por cada categoria principal, sus
    productos que se pueden comprar, de todas las tiendas (con foto primero, despues destacados y lo nuevo).

    Devuelve {id de la categoria: [productos]}. Una consulta numera los candidatos y otra trae los elegidos.
    """
    ids = [categoria.pk for categoria in categorias]
    if not ids:
        return {}
    principal = Coalesce('categoria__padre_id', 'categoria_id')
    candidatos = (
        Producto.objects.activos().sin_variantes_repetidas().filter(q_comprable(), categoria__activa=True)
        .annotate(principal_id=principal, tiene_foto=Exists(FotoProducto.objects.filter(producto=OuterRef('pk'))))
        .filter(principal_id__in=ids)
        .annotate(puesto=Window(
            RowNumber(), partition_by=[principal],
            order_by=[F('tiene_foto').desc(), F('destacado').desc(), F('creado').desc(), F('id').desc()],
        ))
        .filter(puesto__lte=por_categoria)
        .order_by('principal_id', 'puesto')
        .values_list('pk', 'principal_id')
    )
    por_categoria_ids = {}
    for pk, categoria_id in candidatos:
        por_categoria_ids.setdefault(categoria_id, []).append(pk)
    encontrados = _base().in_bulk([pk for lista in por_categoria_ids.values() for pk in lista])
    return {
        categoria_id: [encontrados[pk] for pk in lista if pk in encontrados]
        for categoria_id, lista in por_categoria_ids.items()
    }


def patrocinados_del_sitio(limite=4):
    """Productos que las tiendas anuncian en la portada (planes, 2026-10-26): salen en el carrusel de promociones,
    marcados como anuncio. Cada tienda, hasta lo que permite su plan; una de cada tienda por vuelta."""
    productos = (
        _base().filter(q_comprable(), patrocinado=True, tienda__plan__productos_patrocinados__gt=0)
        .select_related('tienda__plan').order_by('-actualizado', '-id')[:200]
    )
    por_tienda = {}
    for producto in productos:
        lista = por_tienda.setdefault(producto.tienda_id, [])
        if len(lista) < producto.tienda.plan.productos_patrocinados:
            lista.append(producto)
    filas, elegidos = list(por_tienda.values()), []
    while len(elegidos) < limite and any(filas):
        for fila in filas:
            if fila and len(elegidos) < limite:
                elegidos.append(fila.pop(0))
    for producto in elegidos:
        producto.es_patrocinado = True
    return elegidos


# Vistos recientemente (como en las grandes tiendas): ids en la sesion, el mas reciente primero.
CLAVE_VISTOS = 'vistos'
MAXIMO_VISTOS = 12


CLAVE_INTERESES = 'intereses'
MAXIMO_INTERESES = 12
# Palabras que no dicen nada de lo que alguien busca.
PALABRAS_VACIAS = {'para', 'con', 'sin', 'los', 'las', 'del', 'una', 'uno', 'por', 'que', 'mas', 'muy'}


def recordar_busqueda(sesion, texto):
    """Guarda en la sesion las palabras de lo que el visitante busco (para ordenar las promociones de la portada).
    Solo en su sesion: no se guarda en la base ni se relaciona con su cuenta."""
    palabras = [p for p in normalizar(texto or '').split() if len(p) >= 3 and p not in PALABRAS_VACIAS]
    if not palabras:
        return
    anteriores = [p for p in sesion.get(CLAVE_INTERESES, []) if p not in palabras]
    sesion[CLAVE_INTERESES] = [*palabras, *anteriores][:MAXIMO_INTERESES]


def intereses(sesion, usuario=None):
    """Lo que el visitante busco, las categorias y tiendas de lo que miro hace poco y, si tiene cuenta, los gustos que
    contesto (clientes/gustos.py). Sirve para ordenar promociones, categorias y resultados."""
    from clientes import gustos as gustos_del_cliente

    gustos = gustos_del_cliente.de(usuario)
    ids = sesion.get(CLAVE_VISTOS, [])[:MAXIMO_VISTOS]
    vistos = Producto.objects.filter(pk__in=ids).values_list('categoria_id', 'categoria__padre_id', 'tienda_id')
    categorias, tiendas = set(), set()
    for categoria, padre, tienda in vistos:
        categorias.update(c for c in (categoria, padre) if c)
        tiendas.add(tienda)
    categorias.update(gustos.get('categorias', []))
    return {
        'palabras': list(sesion.get(CLAVE_INTERESES, [])), 'categorias': categorias, 'tiendas': tiendas,
        'gustos': gustos, 'categorias_preferidas': set(gustos.get('categorias', [])),
    }


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


def en_otras_tiendas(producto, limite=6):
    """El mismo producto vendido por otras tiendas (pedido del dueño el 2026-11-02: "tiendas que lo tengan mas
    barato"). Es el mismo si coincide el SKU o el nombre exacto (sin importar mayusculas). Solo lo que se puede
    comprar, del mas barato al mas caro; cada uno lleva `ahorro`: cuanto menos cuesta que el de esta ficha (0 si no)."""
    candidatos = list(
        _base(agrupar=False).filter(q_comprable())
        .filter(Q(sku__iexact=producto.sku) | Q(nombre__iexact=producto.nombre.strip()))
        .exclude(tienda_id=producto.tienda_id)[:50]
    )
    candidatos.sort(key=lambda otro: (otro.precio_final, otro.pk))
    for otro in candidatos:
        otro.ahorro = max(producto.precio_final - otro.precio_final, 0)
    return candidatos[:limite]


def similares_en_otras_tiendas(producto, limite=10, excluir=()):
    """Productos de la misma categoria principal en otras tiendas, para comparar (destacados y nuevos primero)."""
    principal = producto.categoria.padre_id or producto.categoria_id
    return list(
        _base().filter(q_comprable())
        .filter(Q(categoria_id=principal) | Q(categoria__padre_id=principal))
        .exclude(tienda_id=producto.tienda_id).exclude(pk__in=excluir)
        .order_by('-destacado', '-creado', '-id')[:limite]
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


# `RLJ-001-2.jpg`: la foto numero 2 del producto RLJ-001 (pedido del dueño el 2026-11-05).
SUFIJO_DE_FOTO = re.compile(r'^(?P<sku>.+)-(?P<numero>[2-9])$')


def asignar_foto_por_sku(archivo, tienda, reemplazar=False):
    """Pone el archivo como foto del producto de la tienda cuyo SKU es el nombre del archivo.

    `123785.jpg` va como foto principal del producto con SKU 123785; `123785-2.jpg` hasta `123785-9.jpg`, como sus
    fotos secundarias en ese orden (si no hay un producto cuyo SKU sea el nombre completo). Con `reemplazar`, la
    principal borra las fotos que ya tenia el producto salvo las secundarias numeradas, y cada secundaria reemplaza
    a la que tenia su mismo numero: asi se puede subir todo de una vez, en cualquier orden.
    """
    sku = Path(archivo.name).stem.strip().upper()
    productos = Producto.objects.filter(tienda=tienda) if tienda else Producto.objects.none()
    producto = productos.filter(sku=sku).first()
    numero = None
    if producto is None and (sufijo := SUFIJO_DE_FOTO.match(sku)):
        producto = productos.filter(sku=sufijo['sku']).first()
        numero = int(sufijo['numero']) if producto else None
        sku = sufijo['sku'] if producto else sku
    if producto is None:
        return FotoPorSku(archivo.name, sku, False, 'No hay ningún producto con ese SKU.')
    try:
        validar_imagen(archivo)
    except ValidationError as error:
        return FotoPorSku(archivo.name, sku, False, ' '.join(error.messages))
    if not _es_imagen(archivo):
        return FotoPorSku(archivo.name, sku, False, 'El archivo no es una imagen válida.')

    if numero:
        nueva = FotoProducto.objects.create(producto=producto, imagen=archivo, orden=numero)
        anteriores = producto.fotos.filter(orden=numero, principal=False)
    else:
        nueva = FotoProducto.objects.create(producto=producto, imagen=archivo, principal=True)
        anteriores = producto.fotos.filter(orden__lt=2)
    if reemplazar:
        # Se borran una a una para que tambien se elimine el archivo de cada foto.
        for anterior in anteriores.exclude(pk=nueva.pk):
            anterior.delete()
    detalle = f'{producto.nombre} (foto {numero})' if numero else producto.nombre
    return FotoPorSku(archivo.name, sku, True, detalle)


# --- Miniaturas de las fotos (Fase 4 del rediseño, 2026-10-27) ------------------------------

def crear_miniaturas_faltantes(limite=5):
    """Crea la miniatura de las fotos subidas antes de que existieran. Devuelve cuantas hizo.

    Lo llaman las tareas periodicas, de a pocas: cada una es una descarga, una conversion y una subida, y la visita que
    dispara la tarea espera a que terminen. Si la foto original ya no se puede leer, la miniatura apunta a ella misma
    para no intentarlo cada hora.
    """
    from io import BytesIO
    from uuid import uuid4

    from core.archivos import ERRORES_DE_ALMACENAMIENTO

    from .imagenes import LADO_MINIATURA, convertir_a_webp

    hechas = 0
    for foto in FotoProducto.objects.filter(miniatura='').exclude(imagen='').order_by('-principal', 'pk')[:limite]:
        try:
            datos = None
            if foto.imagen.storage.exists(foto.imagen.name):
                with foto.imagen.open('rb') as archivo:
                    datos = archivo.read()
        except ERRORES_DE_ALMACENAMIENTO:
            # Sin conexion con el almacenamiento: se intenta en la proxima vuelta.
            logger.exception('No se pudo leer la foto %s para su miniatura', foto.pk)
            break
        chica = None
        if datos:
            try:
                chica = convertir_a_webp(BytesIO(datos), lado_maximo=LADO_MINIATURA)
            except (OSError, ValueError):
                logger.warning('La foto %s no se pudo convertir: su miniatura sera la foto grande', foto.pk)
        if chica is None:
            # La foto ya no existe o no se puede abrir: se usa la grande y no se vuelve a intentar.
            nombre = foto.imagen.name
        else:
            try:
                nombre = foto.miniatura.storage.save(
                    FotoProducto._meta.get_field('miniatura').generate_filename(foto, f'{uuid4().hex}.webp'), chica,
                )
            except ERRORES_DE_ALMACENAMIENTO:
                logger.exception('No se pudo subir la miniatura de la foto %s', foto.pk)
                break
        FotoProducto.objects.filter(pk=foto.pk).update(miniatura=nombre)
        hechas += 1
    return hechas
