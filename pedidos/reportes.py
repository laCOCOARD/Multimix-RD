"""Reporte de ventas del panel. Venta = pedido cobrado (con fecha de pago) que no fue cancelado ni reembolsado."""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import DetallePedido, Pedido

CERO = Decimal('0.00')
DIAS_POR_DEFECTO = 30
DIAS_MAXIMOS = 366


def rango(desde_texto, hasta_texto):
    """Fechas del reporte a partir de lo que llega por la URL; por defecto, los ultimos 30 dias."""
    hoy = timezone.localdate()

    def fecha(texto, defecto):
        try:
            return datetime.strptime(texto or '', '%Y-%m-%d').date()
        except ValueError:
            return defecto

    hasta = min(fecha(hasta_texto, hoy), hoy)
    desde = fecha(desde_texto, hasta - timedelta(days=DIAS_POR_DEFECTO - 1))
    if desde > hasta:
        desde = hasta
    if (hasta - desde).days > DIAS_MAXIMOS:
        desde = hasta - timedelta(days=DIAS_MAXIMOS)
    return desde, hasta


def reporte_de_ventas(pedidos, desde, hasta):
    """Resumen de las ventas de `pedidos` (ya limitados a las tiendas del usuario) entre dos fechas."""
    zona = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(desde, time.min), zona)
    fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min), zona)
    ventas = pedidos.filter(fecha_pago__gte=inicio, fecha_pago__lt=fin).exclude(estado__in=Pedido.ESTADOS_SIN_VENTA)

    totales = ventas.aggregate(cobrado=Sum('total'), pedidos=Count('id'), envios=Sum('costo_envio'), descuentos=Sum('descuento'))
    cantidad = totales['pedidos'] or 0
    cobrado = totales['cobrado'] or CERO
    # Al agrupar se ordena a mano: Django ignora el `ordering` del modelo.
    por_dia = list(
        ventas.annotate(dia=TruncDate('fecha_pago', tzinfo=zona)).order_by().values('dia')
        .annotate(pedidos=Count('id'), cobrado=Sum('total')).order_by('dia')
    )
    por_pago = [
        {**fila, 'metodo': Pedido.Pago(fila['metodo_pago']).label}
        for fila in ventas.order_by().values('metodo_pago').annotate(pedidos=Count('id'), cobrado=Sum('total')).order_by('-cobrado')
    ]
    productos = list(
        DetallePedido.objects.filter(pedido__in=ventas).order_by().values('nombre_producto')
        .annotate(unidades=Sum('cantidad'), ingresos=Sum('subtotal')).order_by('-ingresos', 'nombre_producto')[:10]
    )
    reembolsos = pedidos.filter(
        estado=Pedido.Estado.REEMBOLSADO, fecha_pago__gte=inicio, fecha_pago__lt=fin,
    ).aggregate(pedidos=Count('id'), monto=Sum('total'))
    return {
        'desde': desde, 'hasta': hasta,
        'cobrado': cobrado, 'pedidos': cantidad,
        'promedio': (cobrado / cantidad).quantize(Decimal('0.01')) if cantidad else CERO,
        'envios': totales['envios'] or CERO, 'descuentos': totales['descuentos'] or CERO,
        'por_dia': por_dia, 'por_pago': por_pago, 'productos': productos,
        'reembolsos': {'pedidos': reembolsos['pedidos'] or 0, 'monto': reembolsos['monto'] or CERO},
    }
