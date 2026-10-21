"""Fecha estimada de entrega: lo que el cliente ve en la ficha, el checkout y su pedido.

Se cuentan dias habiles de lunes a sabado (el domingo no se entrega). Los plazos los pone cada tienda: los dias
para tener listo un pedido para recoger, los de cada zona de envio y los extra de los productos bajo pedido.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone
from django.utils.formats import date_format

DOMINGO = 6


def sumar_dias_habiles(desde, dias):
    """`desde` mas `dias` habiles. Con 0 es el mismo dia, salvo que caiga domingo (pasa al lunes)."""
    fecha = desde
    while fecha.weekday() == DOMINGO:
        fecha += timedelta(days=1)
    for _ in range(dias):
        fecha += timedelta(days=1)
        while fecha.weekday() == DOMINGO:
            fecha += timedelta(days=1)
    return fecha


def _dia(fecha, hoy, con_mes=True):
    if fecha == hoy:
        return 'hoy'
    if fecha == hoy + timedelta(days=1):
        return 'mañana'
    return 'el ' + date_format(fecha, 'l j \\d\\e F' if con_mes else 'l j')


@dataclass(frozen=True)
class Estimado:
    desde: date
    hasta: date
    hoy: date

    @property
    def texto(self):
        """"mañana", "el jueves 23 de octubre" o "entre el jueves 23 y el sábado 25 de octubre"."""
        if self.desde == self.hasta:
            return _dia(self.desde, self.hoy)
        mismo_mes = self.desde.month == self.hasta.month and self.desde > self.hoy + timedelta(days=1)
        return f'entre {_dia(self.desde, self.hoy, con_mes=not mismo_mes)} y {_dia(self.hasta, self.hoy)}'


def _hoy(hoy=None):
    return hoy or timezone.localdate()


def estimar(tienda, recoge, zona=None, bajo_pedido=False, hoy=None):
    """Plazo de un pedido. Sin zona, una entrega a domicilio no se puede estimar: devuelve None."""
    hoy = _hoy(hoy)
    extra = tienda.dias_bajo_pedido if bajo_pedido else 0
    if recoge:
        dias_min = dias_max = tienda.dias_para_recoger
    elif zona is None:
        return None
    else:
        dias_min, dias_max = zona.dias_entrega_min, max(zona.dias_entrega_max, zona.dias_entrega_min)
    return Estimado(sumar_dias_habiles(hoy, dias_min + extra), sumar_dias_habiles(hoy, dias_max + extra), hoy)


def estimar_envio(tienda, zonas, bajo_pedido=False, hoy=None):
    """Plazo a domicilio sin saber la zona: de la mas rapida a la mas lenta de las que tiene la tienda."""
    zonas = list(zonas)
    if not zonas:
        return None
    hoy = _hoy(hoy)
    extra = tienda.dias_bajo_pedido if bajo_pedido else 0
    dias_min = min(zona.dias_entrega_min for zona in zonas)
    dias_max = max(max(zona.dias_entrega_max, zona.dias_entrega_min) for zona in zonas)
    return Estimado(sumar_dias_habiles(hoy, dias_min + extra), sumar_dias_habiles(hoy, dias_max + extra), hoy)


def lleva_bajo_pedido(productos):
    return any(producto.bajo_pedido for producto in productos)
