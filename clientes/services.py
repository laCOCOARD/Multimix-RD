"""Cuentas de clientes: registro, limite de intentos y los datos que se recuerdan para la proxima compra."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.urls import reverse

from core import correo, limites
from core.correo import url_absoluta

from .models import Favorito, Perfil


def perfil_de(usuario):
    return Perfil.objects.get_or_create(usuario=usuario)[0]


@transaction.atomic
def registrar_cliente(nombre, correo, clave, telefono=''):
    """Crea la cuenta. El correo es tambien el nombre de usuario; nunca tiene acceso al panel."""
    usuario = get_user_model().objects.create_user(
        username=correo, email=correo, password=clave, first_name=nombre[:150],
    )
    Perfil.objects.create(usuario=usuario, telefono=telefono)
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
    """Lo que ya se sabe del cliente, para que no lo escriba otra vez."""
    perfil = perfil_de(usuario)
    return {
        'nombre': usuario.get_full_name() or usuario.first_name,
        'telefono': perfil.telefono,
        'sector': perfil.sector,
        'direccion': perfil.direccion,
        'referencia': perfil.referencia,
    }


def recordar_pedido(usuario, pedido):
    """Guarda el telefono y la direccion del pedido para la proxima compra del cliente."""
    perfil = perfil_de(usuario)
    perfil.telefono = pedido.telefono
    if not pedido.recoge_en_tienda:
        perfil.sector, perfil.direccion, perfil.referencia = pedido.sector, pedido.direccion, pedido.referencia
    perfil.save()


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
