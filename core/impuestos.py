"""ITBIS de un pedido. Los precios se publican sin impuesto y se suma al confirmar la compra."""
from decimal import ROUND_HALF_UP, Decimal

CERO = Decimal('0.00')
CENTAVO = Decimal('0.01')


def calcular_itbis(importes, descuento, porcentaje):
    """ITBIS de una compra.

    `importes` son pares (importe de la linea, exenta). El descuento se reparte entre todas las lineas
    en proporcion a su importe, asi que solo baja la base en la parte que toca a los productos gravados.
    El envio no entra en la base.
    """
    importes = list(importes)
    subtotal = sum((importe for importe, _ in importes), CERO)
    gravado = sum((importe for importe, exenta in importes if not exenta), CERO)
    if not porcentaje or porcentaje <= 0 or gravado <= 0:
        return CERO
    base = gravado - (descuento or CERO) * gravado / subtotal
    if base <= 0:
        return CERO
    return (base * Decimal(porcentaje) / Decimal('100')).quantize(CENTAVO, rounding=ROUND_HALF_UP)
