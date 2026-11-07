"""Tiendas: quien administra cual, el acceso de los vendedores al panel y el directorio publico."""
import logging

from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Banner, SolicitudTienda, Tienda

logger = logging.getLogger(__name__)

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

# Ayudante (2026-11-06): un empleado que solo atiende pedidos (confirmar pagos, prepararlos, entregarlos). No ve
# productos, dinero de la tienda, plan ni datos de la tienda. Lo agrega el dueño en "Personas de la tienda".
GRUPO_AYUDANTES = 'Ayudantes'
PERMISOS_AYUDANTE = {
    'pedidos': [
        'view_pedido', 'change_pedido', 'view_detallepedido', 'view_eventopedido',
        'view_solicituddevolucion', 'change_solicituddevolucion',
    ],
    'pagos': ['view_pago', 'change_pago'],
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
    grupos = {}
    for nombre, permisos in ((GRUPO_VENDEDORES, PERMISOS_VENDEDOR), (GRUPO_AYUDANTES, PERMISOS_AYUDANTE)):
        grupo, _ = Group.objects.using(using).get_or_create(name=nombre)
        # `set` y no `add`: un permiso que se quita de la lista tambien se le quita al grupo al migrar.
        filtro = Q()
        for app, codigos in permisos.items():
            filtro |= Q(content_type__app_label=app, codename__in=codigos)
        grupo.permissions.set(Permission.objects.using(using).filter(filtro))
        grupos[nombre] = grupo
    return grupos[GRUPO_VENDEDORES]


def _grupo(nombre):
    grupo = Group.objects.filter(name=nombre).first()
    if grupo is None:
        preparar_grupo_vendedores()
        grupo = Group.objects.get(name=nombre)
    return grupo


def dar_acceso_al_panel(usuarios):
    """Deja a los vendedores listos para entrar al panel: usuario del personal y grupo Vendedores. A un ayudante lo
    deja como ayudante (no lo vuelve dueño por guardar la tienda)."""
    grupo = _grupo(GRUPO_VENDEDORES)
    for usuario in usuarios:
        if not usuario.is_staff:
            usuario.is_staff = True
            usuario.save(update_fields=['is_staff'])
        if not usuario.groups.filter(name=GRUPO_AYUDANTES).exists():
            usuario.groups.add(grupo)


# --- Personas de la tienda: quien entra al panel y con que rol (2026-11-06) ------------------------------------

DUENO, AYUDANTE = 'dueno', 'ayudante'
ROLES = [
    (DUENO, 'Dueño: puede hacer todo'),
    (AYUDANTE, 'Ayudante: solo atiende pedidos'),
]


class PersonaError(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def es_ayudante(usuario):
    """Entra al panel solo para atender pedidos."""
    return (
        usuario.is_authenticated and not usuario.is_superuser
        and usuario.groups.filter(name=GRUPO_AYUDANTES).exists()
        and not usuario.groups.filter(name=GRUPO_VENDEDORES).exists()
    )


def rol_de(usuario):
    return AYUDANTE if es_ayudante(usuario) else DUENO


def puede_manejar_personas(usuario, tienda):
    """El administrador principal, o un dueño de esa tienda. Un ayudante no."""
    if ve_todas(usuario):
        return True
    return (
        usuario.is_authenticated and usuario.groups.filter(name=GRUPO_VENDEDORES).exists()
        and tienda.usuarios.filter(pk=usuario.pk).exists()
    )


def personas_de(tienda):
    """Quienes entran al panel de la tienda, con su rol."""
    personas = list(tienda.usuarios.order_by('first_name', 'username').prefetch_related('groups'))
    for persona in personas:
        nombres = {grupo.name for grupo in persona.groups.all()}
        persona.rol = AYUDANTE if GRUPO_AYUDANTES in nombres and GRUPO_VENDEDORES not in nombres else DUENO
        persona.rol_texto = 'Ayudante' if persona.rol == AYUDANTE else 'Dueño'
    return personas


def _poner_rol(usuario, rol):
    vendedores, ayudantes = _grupo(GRUPO_VENDEDORES), _grupo(GRUPO_AYUDANTES)
    if rol == AYUDANTE:
        usuario.groups.remove(vendedores)
        usuario.groups.add(ayudantes)
    else:
        usuario.groups.remove(ayudantes)
        usuario.groups.add(vendedores)


def _solo_en_esta_tienda(usuario, tienda):
    """El rol vale para todas las tiendas de la persona: un dueño solo lo cambia si la persona es solo de la suya."""
    return not usuario.tiendas.exclude(pk=tienda.pk).exists()


def agregar_persona(tienda, por, nombre, usuario, clave, rol, correo=''):
    """Crea la cuenta de una persona nueva y le da acceso al panel de la tienda con ese rol.

    Solo crea cuentas nuevas: asi nadie toma por esta via una cuenta que ya existe (la de un cliente u otra tienda).
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    from django.db import transaction

    if not puede_manejar_personas(por, tienda):
        raise PersonaError('Solo el dueño de la tienda puede agregar personas.')
    if rol not in (DUENO, AYUDANTE):
        raise PersonaError('Elige si será dueño o ayudante.')
    nombre, usuario, correo = (nombre or '').strip(), (usuario or '').strip(), (correo or '').strip()
    if not nombre or not usuario or not clave:
        raise PersonaError('Escribe el nombre, el usuario y la contraseña.')
    Usuario = get_user_model()
    campo = Usuario._meta.get_field(Usuario.USERNAME_FIELD)
    try:
        campo.run_validators(usuario)
    except ValidationError:
        raise PersonaError('El usuario solo puede llevar letras, números y @ . + - _ (sin espacios).')
    if Usuario.objects.filter(**{f'{Usuario.USERNAME_FIELD}__iexact': usuario}).exists():
        raise PersonaError(f'Ya existe una cuenta con el usuario "{usuario}". Elige otro.')
    nueva = Usuario(**{Usuario.USERNAME_FIELD: usuario}, first_name=nombre[:150], email=correo, is_staff=True)
    try:
        validate_password(clave, nueva)
    except ValidationError as error:
        raise PersonaError(' '.join(error.messages))
    with transaction.atomic():
        nueva.set_password(clave)
        nueva.save()
        _poner_rol(nueva, rol)
        tienda.usuarios.add(nueva)
    logger.info('Persona agregada a %s por %s: %s (%s)', tienda, por, nueva, rol)
    return nueva


def cambiar_rol(tienda, por, persona, rol):
    if not puede_manejar_personas(por, tienda):
        raise PersonaError('Solo el dueño de la tienda puede cambiar los permisos.')
    if rol not in (DUENO, AYUDANTE):
        raise PersonaError('Elige si será dueño o ayudante.')
    if persona.is_superuser or not tienda.usuarios.filter(pk=persona.pk).exists():
        raise PersonaError('Esa persona no es de esta tienda.')
    if persona.pk == por.pk:
        raise PersonaError('No puedes cambiar tu propio permiso.')
    if not ve_todas(por) and not _solo_en_esta_tienda(persona, tienda):
        raise PersonaError('Esa persona también trabaja en otra tienda: pídeselo al administrador del sitio.')
    _poner_rol(persona, rol)
    logger.info('Rol cambiado en %s por %s: %s -> %s', tienda, por, persona, rol)


def quitar_persona(tienda, por, persona):
    """Le quita el acceso al panel de esta tienda. Si ya no tiene ninguna, deja de entrar al panel."""
    if not puede_manejar_personas(por, tienda):
        raise PersonaError('Solo el dueño de la tienda puede quitar personas.')
    if persona.is_superuser or not tienda.usuarios.filter(pk=persona.pk).exists():
        raise PersonaError('Esa persona no es de esta tienda.')
    if persona.pk == por.pk:
        raise PersonaError('No puedes quitarte a ti mismo.')
    tienda.usuarios.remove(persona)
    if not persona.tiendas.exists():
        persona.groups.remove(_grupo(GRUPO_VENDEDORES), _grupo(GRUPO_AYUDANTES))
        persona.is_staff = False
        persona.save(update_fields=['is_staff'])
    logger.info('Persona quitada de %s por %s: %s', tienda, por, persona)


def banners_de(tienda):
    """Banners activos y dentro de su vigencia, en el orden que eligio la tienda."""
    ahora = timezone.now()
    return list(
        Banner.objects.filter(tienda=tienda, activo=True)
        .filter(Q(vigente_desde__isnull=True) | Q(vigente_desde__lte=ahora))
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=ahora))
    )


def tiendas_destacadas():
    """Tiendas activas marcadas como destacadas, en su orden, y las que lo estan por un premio del programa de
    referidos (referidos.services.NIVELES) mientras les dure."""
    premio_vigente = Q(premios_referidos__destacada_hasta__gte=timezone.localdate())
    return Tienda.objects.activas().filter(Q(destacada=True) | premio_vigente).distinct().order_by('orden', 'nombre')


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


def color_principal(archivo):
    """El color que mas se ve en la franja de abajo de una imagen (donde la foto se junta con la tarjeta), como
    '#rrggbb'. Si es casi blanco se oscurece un poco: la tarjeta no debe quedar blanca (pedido del dueño el
    2026-11-05)."""
    from PIL import Image

    with Image.open(archivo) as imagen:
        imagen = imagen.convert('RGB')
        imagen.thumbnail((120, 120))
        ancho, alto = imagen.size
        franja = imagen.crop((0, alto * 2 // 3, ancho, alto))
        paleta = franja.quantize(colors=5)
        cuenta, indice = max(paleta.getcolors())
        r, g, b = paleta.getpalette()[indice * 3:indice * 3 + 3]
    if luminancia(r, g, b) > .9:
        r, g, b = (round(c * .88) for c in (r, g, b))
    return f'#{r:02x}{g:02x}{b:02x}'


def luminancia(r, g, b):
    """De 0 (negro) a 1 (blanco), como la percibe el ojo."""
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def color_de_la_tarjeta(tienda):
    """El color del banner de la tienda; lo calcula la primera vez (y cuando cambia el banner) y lo guarda. Vacio si
    no tiene banner o no se pudo leer (entonces la tarjeta queda como siempre)."""
    if not tienda.banner_imagen:
        return ''
    nombre = tienda.banner_imagen.name
    if tienda.color_banner_de == nombre:
        return tienda.color_banner
    try:
        with tienda.banner_imagen.open('rb') as archivo:
            color = color_principal(archivo)
    except Exception:
        logger.warning('No se pudo leer el banner de %s para su color', tienda.nombre, exc_info=True)
        color = ''
    tienda.color_banner, tienda.color_banner_de = color, nombre
    Tienda.objects.filter(pk=tienda.pk).update(color_banner=color, color_banner_de=nombre)
    return color


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
        # La tarjeta toma el color de su banner; el texto va claro u oscuro segun ese color.
        tienda.color = color_de_la_tarjeta(tienda)
        if tienda.color:
            r, g, b = (int(tienda.color[i:i + 2], 16) for i in (1, 3, 5))
            tienda.color_claro = luminancia(r, g, b) > .55
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


def avisar_resultado_de_solicitud(solicitud):
    """Al negocio, cuando su solicitud pasa a aprobada o rechazada: un correo, sin las notas internas.

    El panel lo llama solo al cambiar el estado, asi que guardar otra vez la misma solicitud no lo repite.
    """
    from django.db import transaction

    from core.correo import enviar, url_absoluta
    from core.models import ConfiguracionTienda

    Estado = SolicitudTienda.Estado
    if solicitud.estado not in (Estado.APROBADA, Estado.RECHAZADA):
        return
    config = ConfiguracionTienda.obtener()
    contexto = {
        'solicitud': solicitud, 'sitio': config.nombre, 'correo_sitio': config.correo,
        'enlace_tienda': url_absoluta(solicitud.tienda.get_absolute_url()) if solicitud.tienda_id else '',
    }
    if solicitud.estado == Estado.APROBADA:
        asunto, plantilla = f'Tu tienda en {config.nombre}: solicitud aprobada', 'solicitante_aprobada'
    else:
        asunto, plantilla = f'Tu solicitud para vender en {config.nombre}', 'solicitante_rechazada'
    transaction.on_commit(lambda: enviar(asunto, plantilla, contexto, [solicitud.correo]))

