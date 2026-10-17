from decimal import ROUND_HALF_UP, Decimal

from django.db.models import F
from django.utils import timezone

from core import limites
from core.templatetags.moneda import formatear_monto

from .models import Cupon

CENTAVO = Decimal('0.01')


class CuponInvalido(Exception):
    """El cupon no se puede aplicar; el mensaje esta listo para mostrar al cliente."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def normalizar_codigo(codigo):
    return (codigo or '').strip().upper()


def validar_cupon(codigo, subtotal, tienda, bloquear=False):
    """Devuelve el cupon de la tienda si aplica al subtotal; si no, lanza CuponInvalido.

    Con bloquear=True toma la fila con select_for_update (requiere una transaccion abierta).
    """
    codigo = normalizar_codigo(codigo)
    if not codigo:
        raise CuponInvalido('Escribe el código del cupón.')
    cupones = Cupon.objects.select_for_update() if bloquear else Cupon.objects
    cupon = cupones.filter(tienda=tienda, codigo=codigo).first()
    if cupon is None or not cupon.activo:
        raise CuponInvalido('Ese cupón no existe o no está activo.')
    ahora = timezone.now()
    if cupon.vigente_desde and cupon.vigente_desde > ahora:
        raise CuponInvalido('Ese cupón todavía no está vigente.')
    if cupon.vigente_hasta and cupon.vigente_hasta < ahora:
        raise CuponInvalido('Ese cupón ya venció.')
    if cupon.usos_maximos is not None and cupon.usos_actuales >= cupon.usos_maximos:
        raise CuponInvalido('Ese cupón ya alcanzó su límite de usos.')
    if subtotal < cupon.compra_minima:
        raise CuponInvalido(
            f'Este cupón aplica a compras desde {formatear_monto(cupon.compra_minima)}.'
        )
    return cupon


# Cupones que no aplican, por quien los prueba, cada 15 minutos: sin limite se podia adivinar un codigo corto
# probando uno tras otro. El de la tienda frena al que no deja ni sesion ni IP (ver core.red).
CUPONES_FALLIDOS_POR_PERSONA = 10
CUPONES_FALLIDOS_POR_TIENDA = 100


def probar_cupon(codigo, subtotal, tienda, quien):
    """`validar_cupon` para un codigo que escribio el cliente, con limite de intentos fallidos.

    `quien` son las formas de reconocer a la persona (cuenta, conexion, sesion); vale con que una llegue al limite.
    """
    claves = [('cupon', tienda.pk, *parte) for parte in quien] + [('cupon-tienda', tienda.pk)]
    maximos = [CUPONES_FALLIDOS_POR_PERSONA] * len(quien) + [CUPONES_FALLIDOS_POR_TIENDA]
    if any(limites.bloqueado(*clave, maximo=maximo) for clave, maximo in zip(claves, maximos)):
        raise CuponInvalido('Probaste muchos cupones seguidos. Espera 15 minutos y vuelve a intentarlo.')
    try:
        return validar_cupon(codigo, subtotal, tienda)
    except CuponInvalido:
        for clave in claves:
            limites.anotar_intento(*clave)
        raise


def calcular_descuento(cupon, subtotal):
    """Monto a descontar. Nunca supera el subtotal."""
    if cupon is None or subtotal <= 0:
        return Decimal('0.00')
    if cupon.tipo == Cupon.Tipo.PORCENTAJE:
        descuento = subtotal * cupon.valor / Decimal('100')
    else:
        descuento = cupon.valor
    descuento = descuento.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    return min(descuento, subtotal)


def registrar_uso(cupon):
    Cupon.objects.filter(pk=cupon.pk).update(usos_actuales=F('usos_actuales') + 1)


def devolver_uso(cupon):
    Cupon.objects.filter(pk=cupon.pk, usos_actuales__gt=0).update(usos_actuales=F('usos_actuales') - 1)
