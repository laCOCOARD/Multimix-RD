"""Cuentas de clientes: registro, limite de intentos y los datos que se recuerdan para la proxima compra."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from .models import Favorito, Perfil

INTENTOS_MAXIMOS = 5
VENTANA_SEGUNDOS = 15 * 60


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

def _clave(accion, *partes):
    return 'intentos:' + accion + ':' + ':'.join(str(parte).lower() for parte in partes)


def bloqueado(accion, *partes):
    return cache.get(_clave(accion, *partes), 0) >= INTENTOS_MAXIMOS


def anotar_intento(accion, *partes):
    clave = _clave(accion, *partes)
    # add + incr: el contador vence a los 15 minutos del primer intento.
    if not cache.add(clave, 1, VENTANA_SEGUNDOS):
        try:
            cache.incr(clave)
        except ValueError:
            cache.set(clave, 1, VENTANA_SEGUNDOS)


def olvidar_intentos(accion, *partes):
    cache.delete(_clave(accion, *partes))
