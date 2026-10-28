"""Cuentas de clientes: registro, limite de intentos y los datos que se recuerdan para la proxima compra."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from core import correo, limites
from core.correo import url_absoluta

from .models import CarritoGuardado, Direccion, Favorito, Perfil


def perfil_de(usuario):
    return Perfil.objects.get_or_create(usuario=usuario)[0]


def guardar_gustos(usuario, gustos):
    """Guarda las respuestas (None = no contesto: se dejan como estaban) y no se le vuelve a preguntar."""
    perfil = perfil_de(usuario)
    if gustos is not None:
        perfil.gustos = gustos
    perfil.preguntar_gustos = False
    perfil.save(update_fields=['gustos', 'preguntar_gustos'])


@transaction.atomic
def registrar_cliente(nombre, correo, clave, telefono=''):
    """Crea la cuenta. El correo es tambien el nombre de usuario; nunca tiene acceso al panel."""
    usuario = get_user_model().objects.create_user(
        username=correo, email=correo, password=clave, first_name=nombre[:150],
    )
    # Al terminar de crear la cuenta se le pregunta una sola vez por sus gustos (clientes:gustos).
    Perfil.objects.create(usuario=usuario, telefono=telefono, preguntar_gustos=True)
    return usuario


# --- Confirmacion del correo -----------------------------------------------------------
# Sin confirmarlo, cualquiera podia crear una cuenta con el correo de otra persona y hacerle llegar sus avisos.
# El correo se confirma antes de la primera compra (pedidos.views.checkout).

SAL_CONFIRMACION = 'clientes.confirmar-correo'
DIAS_DEL_ENLACE = 3


def correo_confirmado(usuario):
    if not settings.VERIFICAR_CORREO or usuario.is_staff:
        return True
    return perfil_de(usuario).correo_verificado


def marcar_correo_confirmado(usuario):
    Perfil.objects.update_or_create(usuario=usuario, defaults={'correo_verificado': True})


def token_de_confirmacion(usuario):
    return signing.dumps({'u': usuario.pk, 'e': usuario.email.lower()}, salt=SAL_CONFIRMACION)


def confirmar_correo(token):
    """Marca confirmado el correo del enlace. Devuelve el usuario, o None si el enlace no vale o vencio."""
    try:
        datos = signing.loads(token, salt=SAL_CONFIRMACION, max_age=DIAS_DEL_ENLACE * 24 * 60 * 60)
    except signing.BadSignature:
        return None
    usuario = get_user_model().objects.filter(pk=datos.get('u'), is_active=True).first()
    # El enlace es de ese correo: si la cuenta cambio de correo despues, ya no sirve.
    if usuario is None or usuario.email.lower() != datos.get('e'):
        return None
    marcar_correo_confirmado(usuario)
    return usuario


def enviar_confirmacion(usuario):
    """Envia el enlace para confirmar el correo. False si ya se le enviaron varios en esta hora."""
    if not puede_recibir_enlace(usuario.email, 'confirmar'):
        return False
    enlace = url_absoluta(reverse('clientes:confirmar_correo', args=[token_de_confirmacion(usuario)]))
    contexto = {'usuario': usuario, 'enlace': enlace, 'dias': DIAS_DEL_ENLACE}
    transaction.on_commit(lambda: correo.enviar('Confirma tu correo', 'confirmar_correo', contexto, [usuario.email]))
    return True


def correo_en_uso(correo):
    Usuario = get_user_model()
    return Usuario.objects.filter(username__iexact=correo).exists() or Usuario.objects.filter(email__iexact=correo).exists()


def datos_para_el_checkout(usuario):
    """Lo que ya se sabe del cliente, para que no lo escriba otra vez: su telefono y su direccion principal."""
    perfil = perfil_de(usuario)
    direccion = direcciones_de(usuario).first()
    return {
        'nombre': usuario.get_full_name() or usuario.first_name,
        'telefono': perfil.telefono,
        'sector': direccion.sector if direccion else '',
        'direccion': direccion.direccion if direccion else '',
        'referencia': direccion.referencia if direccion else '',
    }


def recordar_pedido(usuario, pedido):
    """Guarda el telefono y, si es a domicilio, la direccion del pedido para la proxima compra del cliente."""
    perfil = perfil_de(usuario)
    perfil.telefono = pedido.telefono
    perfil.save(update_fields=['telefono'])
    if not pedido.recoge_en_tienda:
        guardar_direccion_usada(usuario, pedido.sector, pedido.direccion, pedido.referencia)


# --- Direcciones guardadas ------------------------------------------------------------

class DireccionError(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def direcciones_de(usuario):
    return Direccion.objects.filter(usuario=usuario)


def _misma(direccion, sector, calle):
    return direccion.direccion.casefold() == calle.casefold() and direccion.sector.casefold() == sector.casefold()


def guardar_direccion_usada(usuario, sector, calle, referencia=''):
    """Despues de un pedido a domicilio: si la direccion ya estaba, se marca como usada; si no, se guarda.

    La primera queda como principal. Pasado el maximo no se guardan mas (el cliente borra las que no use).
    """
    sector, calle = ' '.join((sector or '').split()), ' '.join((calle or '').split())
    if not calle:
        return None
    ahora = timezone.now()
    guardadas = list(direcciones_de(usuario))
    existente = next((d for d in guardadas if _misma(d, sector, calle)), None)
    if existente is not None:
        existente.usada, existente.referencia = ahora, referencia or existente.referencia
        existente.save(update_fields=['usada', 'referencia'])
        return existente
    if len(guardadas) >= Direccion.MAXIMO:
        return None
    nombre = 'Casa' if not guardadas else f'Dirección {len(guardadas) + 1}'
    return Direccion.objects.create(
        usuario=usuario, nombre=nombre, sector=sector or '-', direccion=calle, referencia=referencia or '',
        principal=not guardadas, usada=ahora,
    )


@transaction.atomic
def guardar_direccion(usuario, datos, direccion=None):
    """Crea o cambia una direccion del cliente desde su cuenta. `datos` viene validado por DireccionForm."""
    if direccion is None:
        if direcciones_de(usuario).count() >= Direccion.MAXIMO:
            raise DireccionError(f'Puedes guardar hasta {Direccion.MAXIMO} direcciones. Borra una que no uses.')
        direccion = Direccion(usuario=usuario)
    for campo in ('nombre', 'sector', 'direccion', 'referencia'):
        setattr(direccion, campo, datos[campo])
    primera = not direcciones_de(usuario).exclude(pk=direccion.pk).exists()
    direccion.principal = bool(datos.get('principal')) or primera or direccion.principal
    direccion.save()
    if direccion.principal:
        direcciones_de(usuario).exclude(pk=direccion.pk).update(principal=False)
    return direccion


@transaction.atomic
def marcar_principal(direccion):
    Direccion.objects.filter(usuario_id=direccion.usuario_id).update(principal=False)
    direccion.principal = True
    direccion.save(update_fields=['principal'])


@transaction.atomic
def borrar_direccion(direccion):
    """Si era la principal, pasa a serlo la usada mas recientemente."""
    usuario_id, era_principal = direccion.usuario_id, direccion.principal
    direccion.delete()
    if era_principal:
        siguiente = Direccion.objects.filter(usuario_id=usuario_id).first()
        if siguiente is not None:
            marcar_principal(siguiente)


# --- Carrito guardado en la cuenta ------------------------------------------------------
# El carrito vive en la sesion (carrito/carrito.py); con la sesion iniciada tambien se copia aqui, para recuperarlo
# al entrar desde otro equipo y para recordarle al cliente lo que dejo sin comprar.

def guardar_carrito(usuario, datos):
    con_algo = {tienda: carrito for tienda, carrito in datos.items() if carrito.get('items')}
    CarritoGuardado.objects.update_or_create(
        usuario=usuario, defaults={'datos': con_algo, 'actualizado': timezone.now()},
    )


def carrito_guardado(usuario):
    guardado = CarritoGuardado.objects.filter(usuario=usuario).first()
    return guardado.datos if guardado else {}


# Se recuerda pasado un dia sin tocar el carrito, y no despues de una semana (ya no le interesa).
RECORDAR_DESPUES = timedelta(hours=24)
RECORDAR_HASTA = timedelta(days=7)
SAL_RECORDATORIOS = 'clientes.recordatorios'


def token_recordatorios(usuario):
    return signing.dumps(usuario.pk, salt=SAL_RECORDATORIOS)


def apagar_recordatorios(token):
    """El enlace "no quiero estos correos" del recordatorio. Devuelve el usuario, o None si el enlace no vale."""
    try:
        usuario_id = signing.loads(token, salt=SAL_RECORDATORIOS)
    except signing.BadSignature:
        return None
    usuario = get_user_model().objects.filter(pk=usuario_id).first()
    if usuario is not None:
        Perfil.objects.update_or_create(usuario=usuario, defaults={'recordatorios': False})
    return usuario


def _lineas_guardadas(datos):
    """[(tienda, [productos a la venta])] del carrito guardado; lo que ya no se vende no se recuerda."""
    from catalogo.models import Producto, q_comprable
    from tiendas.models import Tienda

    claves = {int(clave): carrito for clave, carrito in datos.items() if str(clave).isdigit()}
    tiendas = Tienda.objects.activas().in_bulk(list(claves))
    resultado = []
    for clave, carrito in claves.items():
        ids = [int(pk) for pk in (carrito.get('items') or {}) if str(pk).isdigit()]
        if clave not in tiendas or not ids:
            continue
        productos = list(Producto.objects.activos().filter(q_comprable(), tienda_id=clave, pk__in=ids))
        if productos:
            resultado.append((tiendas[clave], productos))
    return resultado


def recordar_carritos_abandonados():
    """Un correo a quien dejo productos en el carrito hace mas de un dia. Uno solo por cada vez que lo deja."""
    ahora = timezone.now()
    pendientes = (
        CarritoGuardado.objects.filter(actualizado__lt=ahora - RECORDAR_DESPUES, actualizado__gt=ahora - RECORDAR_HASTA)
        .filter(Q(recordado__isnull=True) | Q(recordado__lt=F('actualizado')))
        .filter(usuario__is_active=True, usuario__is_staff=False)
        .exclude(usuario__perfil__recordatorios=False)
        .exclude(datos={}).select_related('usuario')
    )
    enviados = 0
    for guardado in pendientes:
        usuario = guardado.usuario
        lineas = _lineas_guardadas(guardado.datos)
        if lineas and usuario.email and correo_confirmado(usuario):
            contexto = {
                'usuario': usuario,
                'carritos': [
                    {'tienda': tienda, 'productos': productos,
                     'enlace': url_absoluta(reverse('carrito:detalle', args=[tienda.slug]))}
                    for tienda, productos in lineas
                ],
                'enlace_apagar': url_absoluta(
                    reverse('clientes:apagar_recordatorios', args=[token_recordatorios(usuario)]),
                ),
            }
            if correo.enviar('Dejaste productos en tu carrito', 'cliente_carrito', contexto, [usuario.email]):
                enviados += 1
        # Aunque no haya salido (nada a la venta), no se vuelve a mirar hasta que cambie el carrito.
        CarritoGuardado.objects.filter(pk=guardado.pk).update(recordado=ahora)
    return enviados


# --- Favoritos ------------------------------------------------------------------------

def es_favorito(usuario, producto):
    return usuario.is_authenticated and Favorito.objects.filter(usuario=usuario, producto=producto).exists()


def alternar_favorito(usuario, producto):
    """Lo guarda si no estaba y lo quita si estaba. Devuelve True si quedo guardado."""
    favorito, creado = Favorito.objects.get_or_create(usuario=usuario, producto=producto)
    if not creado:
        favorito.delete()
    return creado


def productos_favoritos(usuario):
    """Los favoritos que siguen a la venta, del mas reciente al mas antiguo."""
    from catalogo.models import Producto

    return (
        Producto.objects.activos().para_listado().filter(favoritos__usuario=usuario).order_by('-favoritos__creado')
    )


# --- Limite de intentos ---------------------------------------------------------------
# La IP la da el proxy y no siempre es fiable (ver core.red): todo limite que importa cuenta tambien por correo,
# que el atacante no puede cambiar si quiere probar contraseñas de una cuenta concreta.

INTENTOS_MAXIMOS = limites.INTENTOS_MAXIMOS
# Una cuenta, desde cualquier conexion: frena a quien prueba contraseñas cambiando de IP.
INTENTOS_POR_CUENTA = 10
# Cuentas nuevas en todo el sitio cada 15 minutos; vale aunque no se sepa la IP de nadie.
REGISTROS_DEL_SITIO = 30
# Enlaces de recuperacion o de confirmacion para un mismo correo en una hora: nadie llena el buzon de otro.
ENLACES_POR_CORREO = 3
UNA_HORA = 60 * 60


def entrada_bloqueada(ip, usuario):
    return (
        limites.bloqueado('entrar', ip or 'sin-ip', usuario)
        or limites.bloqueado('entrar-cuenta', usuario, maximo=INTENTOS_POR_CUENTA)
    )


def anotar_entrada_fallida(ip, usuario):
    limites.anotar_intento('entrar', ip or 'sin-ip', usuario)
    limites.anotar_intento('entrar-cuenta', usuario)


def olvidar_entradas(ip, usuario):
    limites.olvidar_intentos('entrar', ip or 'sin-ip', usuario)
    limites.olvidar_intentos('entrar-cuenta', usuario)


def registro_bloqueado(ip):
    return bool(ip and limites.bloqueado('registro', ip)) or limites.bloqueado('registro-sitio', maximo=REGISTROS_DEL_SITIO)


def anotar_registro(ip):
    if ip:
        limites.anotar_intento('registro', ip)
    limites.anotar_intento('registro-sitio')


def recuperacion_bloqueada(ip):
    return bool(ip) and limites.bloqueado('recuperar', ip)


def anotar_recuperacion(ip):
    if ip:
        limites.anotar_intento('recuperar', ip)


def puede_recibir_enlace(correo, tipo='recuperar'):
    """True si aun se le puede enviar un enlace a ese correo en esta hora, y lo cuenta."""
    if limites.bloqueado(f'enlace-{tipo}', correo, maximo=ENLACES_POR_CORREO, ventana=UNA_HORA):
        return False
    limites.anotar_intento(f'enlace-{tipo}', correo)
    return True
