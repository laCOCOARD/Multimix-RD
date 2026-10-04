from decimal import Decimal, InvalidOperation

from django import template

from core.telefonos import formatear_telefono

register = template.Library()


def formatear_monto(valor):
    """1250 -> 'RD$ 1,250.00'."""
    try:
        monto = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return ''
    return f'RD$ {monto:,.2f}'


@register.filter
def moneda(valor):
    return formatear_monto(valor)


@register.filter
def telefono(valor):
    return formatear_telefono(valor)
