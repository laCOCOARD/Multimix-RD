"""Tiendas: quien administra cual, el acceso de los vendedores al panel y el directorio publico."""
from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Banner, SolicitudTienda, Tienda

GRUPO_VENDEDORES = 'Vendedores'

# Lo que un vendedor puede hacer en el panel. El panel ademas le muestra solo lo de sus tiendas
# (tiendas.panel.AdminDeTienda); las categorias y la configuracion general quedan para el administrador.
PERMISOS_VENDEDOR = {
    # Desde el 2026-10-26 cada tienda cobra en sus propias cuentas: las registra el vendedor.
    'tiendas': [
        'view_tienda', 'change_tienda', 'view_banner', 'add_banner', 'change_banner', 'delete_banner',
        'view_cuentabancaria', 'add_cuentabancaria', 'change_cuentabancaria', 'delete_cuentabancaria',
    ],
    'catalogo': [
        'view_producto', 'add_producto', 'change_producto', 'delete_producto',
        'view_fotoproducto', 'add_fotoproducto', 'change_fotoproducto', 'delete_fotoproducto',
        'view_avisodisponible',
    ],
    'pedidos': [
        'view_pedido', 'change_pedido', 'delete_pedido', 'view_detallepedido', 'view_eventopedido',
        'view_solicituddevolucion', 'change_solicituddevolucion',
        'view_zonaenvio', 'add_zonaenvio', 'change_zonaenvio', 'delete_zonaenvio',
    ],
    'promociones': ['view_cupon', 'add_cupon', 'change_cupon', 'delete_cupon'],
    # Los pagos se revisan (aprobar o rechazar); no se crean ni se borran a mano.
    'pagos': ['view_pago', 'change_pago', 'view_liquidacion'],
    # Las reseñas se ven; publicarlas o rechazarlas es del administrador principal. Las preguntas las responde
    # la tienda.
    'opiniones': ['view_resena', 'view_pregunta', 'change_pregunta'],
    # Su plan lo asigna el administrador; la tienda ve los planes, sube el comprobante de lo que debe al sitio (no lo
    # aprueba) y maneja sus anuncios y sus videos, que se publican cuando el administrador los aprueba.
    'planes': [
        'view_plan', 'view_cargo', 'change_cargo',
        'view_anuncio', 'add_anuncio', 'change_anuncio', 'delete_anuncio',
        'view_video', 'add_video', 'change_video', 'delete_video',
    ],
    # Sin 'core': las cuentas del sitio (a donde le pagan las tiendas) las registra solo el administrador principal.
}


def ve_todas(usuario):
    """Solo el administrador principal (superusuario) ve y administra todas las tiendas."""
    return usuario.is_active and usuario.is_superuser


def tiendas_de(usuario):
    """Tiendas que el usuario puede administrar en el panel."""
    if ve_todas(usuario):
        return Tienda.objects.all()
    if not usuario.is_authenticated:
        return Tienda.objects.none()
    return Tienda.objects.filter(usuarios=usuario)


def preparar_grupo_vendedores(using=DEFAULT_DB_ALIAS, **kwargs):
    """Crea el grupo Vendedores con sus permisos. Corre despues de cada `migrate`."""
    if Group._meta.db_table not in connections[using].introspection.table_names():
        return None
    # Los permisos de cada app se crean al terminar su migracion; aqui se adelantan los que falten.
    for app in PERMISOS_VENDEDOR:
        create_permissions(apps.get_app_config(app), verbosity=0, using=using)
    grupo, _ = Group.objects.using(using).get_or_create(name=GRUPO_VENDEDORES)
    # `set` y no `add`: un permiso que se quita de la lista tambien se le quita al grupo al migrar.
    filtro = Q()
    for app, codigos in PERMISOS_VENDEDOR.items():
        filtro |= Q(content_type__app_label=app, codename__in=codigos)
    grupo.permissions.set(Permission.objects.using(using).filter(filtro))
    return grupo


def dar_acceso_al_panel(usuarios):
    """Deja a los vendedores listos para entrar al panel: usuario del personal y grupo Vendedores."""
    grupo = Group.objects.filter(name=GRUPO_VENDEDORES).first() or preparar_grupo_vendedores()
    for usuario in usuarios:
        if not usuario.is_staff:
            usuario.is_staff = True
            usuario.save(update_fields=['is_staff'])
        usuario.groups.add(grupo)


def banners_de(tienda):
    """Banners activos y dentro de su vigencia, en el orden que eligio la tienda."""
    ahora = timezone.now()
    return list(
        Banner.objects.filter(tienda=tienda, activo=True)
        .filter(Q(vigente_desde__isnull=True) | Q(vigente_desde__lte=ahora))
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=ahora))
    )


def directorio():
    """Tiendas activas con la cantidad de productos que muestra su catalogo.

    Como en los listados, de cada grupo de variantes cuenta solo el principal (o sus variantes, si el principal no
    se vende): una camisa en tres tallas es un producto.
    """
    a_la_venta = Q(productos__activo=True, productos__categoria__activa=True) & (
        Q(productos__variante_de__isnull=True) | Q(productos__variante_de__activo=False)
    )
    # El orden se pide a mano: al agrupar, Django no aplica el `ordering` del modelo.
    return (
        Tienda.objects.activas().annotate(total_productos=Count('productos', filter=a_la_venta))
        .order_by('orden', 'nombre')
    )


TONOS_DE_TARJETA = 4


def para_el_directorio(tiendas, categorias=3):
    """Prepara las tarjetas del directorio con una sola consulta para todas las tiendas.

    Pone en cada tienda `categorias_principales` (los nombres de las categorias en las que tiene mas productos a la
    venta) y `tono`, el degradado de su franja cuando no tiene banner, para que no se vean todas iguales.
    """
    from catalogo.models import Producto

    tiendas = list(tiendas)
    filas = (
        Producto.objects.activos().sin_variantes_repetidas().filter(tienda__in=tiendas)
        .annotate(principal=Coalesce('categoria__padre__nombre', 'categoria__nombre'))
        .order_by().values('tienda_id', 'principal').annotate(total=Count('id'))
        .order_by('tienda_id', '-total', 'principal')
    )
    por_tienda = {}
    for fila in filas:
        nombres = por_tienda.setdefault(fila['tienda_id'], [])
        if len(nombres) < categorias:
            nombres.append(fila['principal'])
    for tienda in tiendas:
        tienda.categorias_principales = por_tienda.get(tienda.pk, [])
        tienda.tono = tienda.pk % TONOS_DE_TARJETA
    return tiendas


def como_vender(plataforma, paginas_publicadas=()):
    """A donde escribe quien quiere vender en el sitio, o None si el sitio no tiene a donde.

    Las tiendas las crea el administrador, asi que el camino es pedirla: el WhatsApp del sitio con el mensaje listo,
    su correo o, si no hay ninguno, la pagina de contacto publicada.
    """
    from urllib.parse import quote

    from pedidos.whatsapp import construir_enlace

    if plataforma.whatsapp:
        mensaje = f'Hola, quiero vender mis productos en {plataforma.nombre}. ¿Cómo abro mi tienda?'
        return {'url': construir_enlace(plataforma.whatsapp, mensaje), 'medio': 'whatsapp'}
    if plataforma.correo:
        asunto = quote(f'Quiero vender en {plataforma.nombre}')
        return {'url': f'mailto:{plataforma.correo}?subject={asunto}', 'medio': 'correo'}
    if 'contacto' in paginas_publicadas:
        from django.urls import reverse

        return {'url': reverse('core:pagina', args=['contacto']), 'medio': 'pagina'}
    return None



def buscar_tiendas(texto, limite=6):
    """Tiendas activas cuyo nombre, descripcion o categorias principales contienen todas las palabras escritas (sin
    tildes ni mayusculas). Las tiendas son pocas: se comparan en Python, con las mismas tarjetas del directorio."""
    from core.texto import normalizar

    palabras = normalizar(texto or '').split()
    if not palabras or max(len(palabra) for palabra in palabras) < 2:
        return []
    encontradas = []
    for tienda in para_el_directorio(directorio()):
        donde = normalizar(' '.join([tienda.nombre, tienda.banner_subtitulo, *tienda.categorias_principales]))
        if all(palabra in donde for palabra in palabras):
            encontradas.append(tienda)
            if len(encontradas) == limite:
                break
    return encontradas

def tienda_principal():
    """La tienda mas antigua que siga activa: recibe los enlaces de cuando habia una sola tienda."""
    return Tienda.objects.activas().order_by('pk').first()


# --- Solicitudes de tiendas (Fase 2 del rediseño, 2026-10-27) -----------------------------
# Quien quiere vender llena el formulario de /vender/solicitar/. Queda pendiente hasta que el administrador principal
# la revisa: no se crean cuentas ni se da acceso al panel; la tienda la sigue creando el administrador.

SOLICITUDES_POR_CONEXION = 3       # por hora, desde una misma IP
SOLICITUDES_POR_CORREO = 2         # por dia, con un mismo correo
SOLICITUDES_DEL_SITIO = 40         # por dia, en todo el sitio (por si llegan bots desde muchas IP)
HORA, DIA = 60 * 60, 24 * 60 * 60


def solicitud_bloqueada(ip, correo):
    from core import limites

    return (
        bool(ip and limites.bloqueado('solicitud-tienda', ip, maximo=SOLICITUDES_POR_CONEXION, ventana=HORA))
        or limites.bloqueado('solicitud-tienda-correo', correo, maximo=SOLICITUDES_POR_CORREO, ventana=DIA)
        or limites.bloqueado('solicitud-tienda-sitio', maximo=SOLICITUDES_DEL_SITIO, ventana=DIA)
    )


def _anotar_solicitud(ip, correo):
    from core import limites

    if ip:
        limites.anotar_intento('solicitud-tienda', ip)
    limites.anotar_intento('solicitud-tienda-correo', correo)
    limites.anotar_intento('solicitud-tienda-sitio')


def registrar_solicitud(datos, ip=None):
    """Guarda la solicitud como pendiente y avisa al sitio (con el enlace para revisarla) y a quien la envio."""
    from django.db import transaction
    from django.urls import reverse

    from core.correo import enviar, url_absoluta
    from core.models import ConfiguracionTienda
    from pedidos.avisos import correos_del_sitio

    solicitud = SolicitudTienda.objects.create(**datos)
    _anotar_solicitud(ip, solicitud.correo)
    sitio = ConfiguracionTienda.obtener().nombre

    def avisar():
        contexto = {'solicitud': solicitud, 'sitio': sitio}
        enviar(
            f'Solicitud de tienda: {solicitud.nombre_comercial}', 'sitio_solicitud_tienda',
            {**contexto, 'enlace': url_absoluta(reverse('admin:tiendas_solicitudtienda_change', args=[solicitud.pk]))},
            correos_del_sitio(),
        )
        enviar(f'Recibimos tu solicitud para vender en {sitio}', 'solicitante_tienda', contexto, [solicitud.correo])
    transaction.on_commit(avisar)
    return solicitud


def solicitudes_pendientes():
    return SolicitudTienda.objects.filter(estado=SolicitudTienda.Estado.PENDIENTE).count()


def revisar_solicitud(solicitud, usuario):
    """Anota quien y cuando cambio el estado (lo llama el panel al guardar un estado nuevo)."""
    solicitud.revisada_por = usuario
    solicitud.revisada_el = timezone.now()

