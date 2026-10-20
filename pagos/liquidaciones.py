"""Reparto a las tiendas: cuanto le toca a cada una de lo vendido y registro de cada deposito.

Reglas:
- Entra en cuenta un pedido cobrado y ya entregado. Hasta entonces esta "en curso".
- La comision del sitio se calcula sobre los productos (subtotal menos descuento); el envio es de la tienda.
- Toda transferencia llega a las cuentas del sitio (`Pedido.cobra_el_sitio`): el dinero lo tiene el sitio y hay que
  depositarselo a la tienda menos la comision. Los pedidos de antes de esto, transferidos a las cuentas que tenia
  cada tienda, quedaron con `cobra_el_sitio` apagado y cuentan como cobrados por la tienda.
- El efectivo (y las transferencias de antes, a las cuentas que tenia cada tienda) lo cobra la tienda: no se le deposita, pero la
  comision del sitio si cuenta, porque fue una venta de la tienda. Esa parte la tienda se la debe al sitio.
- Saldo = lo que el sitio cobro por la tienda - la comision de todos sus pedidos - reembolsos ya depositados.
  Positivo: el sitio le deposita a la tienda. Negativo: la tienda le debe al sitio.
- Al depositar, lo que cobre el banco por la transferencia lo paga el sitio (pedido del dueño el 2026-10-19): se
  anota en la liquidacion como gasto del sitio, pero la tienda recibe su saldo completo.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum

from pedidos.models import Pedido

from .models import Liquidacion

CERO = Decimal('0.00')
CENTAVO = Decimal('0.01')


class LiquidacionError(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


@dataclass
class Grupo:
    """Pedidos por liquidar segun quien tiene el dinero: el sitio o la tienda."""
    pedidos: list = field(default_factory=list)
    ventas: Decimal = CERO
    comision: Decimal = CERO

    @property
    def neto(self):
        return self.ventas - self.comision


@dataclass
class Saldo:
    tienda: object
    pedidos: list = field(default_factory=list)
    del_sitio: Grupo = field(default_factory=Grupo)     # el cliente transfirio a las cuentas del sitio
    de_la_tienda: Grupo = field(default_factory=Grupo)  # efectivo o transferencia a la tienda: ya lo tiene ella
    reembolsados: list = field(default_factory=list)
    ventas: Decimal = CERO          # total de los pedidos por liquidar (productos + envios)
    productos: Decimal = CERO       # subtotal menos descuento: la base de la comision
    envios: Decimal = CERO          # lo que pago el cliente por el envio: va completo a la tienda
    cobrado_por_el_sitio: Decimal = CERO
    comision: Decimal = CERO
    ajustes: Decimal = CERO         # depositos de pedidos que despues se reembolsaron
    en_curso: Decimal = CERO        # cobrado pero aun sin entregar
    pedidos_en_curso: int = 0

    @property
    def monto(self):
        return self.cobrado_por_el_sitio - self.comision - self.ajustes

    @property
    def hay_movimientos(self):
        return bool(self.pedidos or self.reembolsados)


def comision_de(pedido, porcentaje):
    base = max(pedido.subtotal - pedido.descuento, CERO)
    return (base * porcentaje / Decimal('100')).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def monto_del_pedido(pedido, tienda):
    """Lo que el pedido suma (o resta) al saldo de la tienda."""
    cobrado = pedido.total if pedido.cobra_el_sitio else CERO
    return cobrado - comision_de(pedido, tienda.comision_porcentaje)


def _por_liquidar(tienda):
    return Pedido.objects.filter(
        tienda=tienda, estado=Pedido.Estado.ENTREGADO, fecha_pago__isnull=False, liquidacion__isnull=True,
    ).order_by('fecha_pago', 'id')


def _reembolsos_por_descontar(tienda):
    return Pedido.objects.filter(
        tienda=tienda, estado=Pedido.Estado.REEMBOLSADO, liquidacion__isnull=False, ajuste_liquidacion__isnull=True,
    ).order_by('id')


def saldo_de(tienda, bloquear=False):
    pedidos, reembolsados = _por_liquidar(tienda), _reembolsos_por_descontar(tienda)
    if bloquear:
        pedidos, reembolsados = pedidos.select_for_update(), reembolsados.select_for_update()
    saldo = Saldo(tienda=tienda, pedidos=list(pedidos), reembolsados=list(reembolsados))
    for pedido in saldo.pedidos:
        comision = comision_de(pedido, tienda.comision_porcentaje)
        saldo.ventas += pedido.total
        saldo.productos += max(pedido.subtotal - pedido.descuento, CERO)
        saldo.envios += pedido.costo_envio
        saldo.comision += comision
        saldo.cobrado_por_el_sitio += monto_del_pedido(pedido, tienda) + comision
        pedido.comision = comision
        grupo = saldo.del_sitio if pedido.cobra_el_sitio else saldo.de_la_tienda
        grupo.pedidos.append(pedido)
        grupo.ventas += pedido.total
        grupo.comision += comision
    saldo.ajustes = sum((pedido.monto_liquidado or CERO for pedido in saldo.reembolsados), CERO)
    en_curso = Pedido.objects.filter(tienda=tienda, fecha_pago__isnull=False, liquidacion__isnull=True).exclude(
        estado__in=(Pedido.Estado.ENTREGADO, *Pedido.ESTADOS_SIN_VENTA),
    )
    saldo.pedidos_en_curso = en_curso.count()
    saldo.en_curso = en_curso.aggregate(total=Sum('total'))['total'] or CERO
    return saldo


def _costo(valor):
    """Comision del banco por la transferencia: un monto en RD$, no negativo. La paga el sitio."""
    try:
        costo = Decimal(str(valor or '0').replace(',', '').strip() or '0').quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise LiquidacionError('Escribe la comisión de la transferencia como un monto. Ej.: 150.00') from error
    if costo < 0:
        raise LiquidacionError('La comisión de la transferencia no puede ser negativa.')
    return costo


@transaction.atomic
def liquidar(tienda, usuario=None, nota='', costo_transferencia=0):
    """Cierra el saldo de la tienda: registra el deposito y marca los pedidos para no pagarlos dos veces.

    `costo_transferencia` es lo que cobro el banco por enviar el deposito. Lo paga el sitio: queda anotado, pero no
    se le descuenta a la tienda.
    """
    saldo = saldo_de(tienda, bloquear=True)
    if not saldo.hay_movimientos:
        raise LiquidacionError(f'{tienda.nombre} no tiene pedidos entregados por liquidar.')
    costo = _costo(costo_transferencia)
    liquidacion = Liquidacion.objects.create(
        tienda=tienda, creada_por=usuario, nota=(nota or '').strip()[:255], pedidos_incluidos=len(saldo.pedidos),
        ventas=saldo.ventas, cobrado_por_el_sitio=saldo.cobrado_por_el_sitio, comision=saldo.comision,
        cobrado_por_la_tienda=saldo.de_la_tienda.ventas, comision_de_lo_cobrado_por_la_tienda=saldo.de_la_tienda.comision,
        ajustes=saldo.ajustes, costo_transferencia=costo, monto=saldo.monto,
        comision_porcentaje=tienda.comision_porcentaje,
    )
    for pedido in saldo.pedidos:
        pedido.liquidacion = liquidacion
        pedido.monto_liquidado = monto_del_pedido(pedido, tienda)
        pedido.save(update_fields=['liquidacion', 'monto_liquidado'])
    for pedido in saldo.reembolsados:
        pedido.ajuste_liquidacion = liquidacion
        pedido.save(update_fields=['ajuste_liquidacion'])
    return liquidacion
