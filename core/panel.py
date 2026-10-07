"""Datos del resumen que se muestra en la portada del panel de administracion."""
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from catalogo.models import Producto
from pedidos.models import DetallePedido, Pedido
from tiendas.models import Tienda

from .models import ConfiguracionTienda


def _ventas_desde(pedidos, inicio):
    """Suma de pedidos cobrados (con fecha de pago) y no cancelados desde `inicio`."""
    return (
        pedidos.filter(fecha_pago__gte=inicio).exclude(estado=Pedido.Estado.CANCELADO)
        .aggregate(total=Sum('total'))['total'] or 0
    )


def _inicio_del_dia_y_del_mes():
    inicio_dia = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio_dia, inicio_dia.replace(day=1)


def resumen_panel(tiendas=None):
    """Resumen de ventas, pedidos y stock. `tiendas` lo limita a esas tiendas; None = todo el sitio."""
    inicio_dia, inicio_mes = _inicio_del_dia_y_del_mes()
    umbral = ConfiguracionTienda.obtener().umbral_stock_bajo

    pedidos = Pedido.objects.all()
    productos = Producto.objects.filter(activo=True)
    vendidos = DetallePedido.objects.filter(pedido__estado__in=Pedido.ESTADOS_VENTA)
    if tiendas is not None:
        pedidos = pedidos.filter(tienda__in=tiendas)
        productos = productos.filter(tienda__in=tiendas)
        vendidos = vendidos.filter(pedido__tienda__in=tiendas)

    productos = productos.annotate(disponible=F('stock_almacen') - F('stock_reservado'))
    stock_bajo = productos.filter(disponible__gt=0, disponible__lte=umbral).order_by('disponible', 'nombre')
    agotados = productos.filter(disponible__lte=0).order_by('nombre')
    pendientes = pedidos.filter(estado=Pedido.Estado.PENDIENTE)

    return {
        'ventas_dia': _ventas_desde(pedidos, inicio_dia),
        'ventas_mes': _ventas_desde(pedidos, inicio_mes),
        'pedidos_pendientes': pendientes.count(),
        'transferencias_por_verificar': pendientes.filter(transferencia_realizada=True).count(),
        'total_stock_bajo': stock_bajo.count(),
        'total_agotados': agotados.count(),
        'stock_bajo': stock_bajo[:8],
        'agotados': agotados[:8],
        'umbral_stock_bajo': umbral,
        'ultimos_pedidos': pedidos.select_related('tienda').order_by('-creado')[:8],
        'mas_vendidos': (
            vendidos.values('producto_id', 'producto__nombre')
            .annotate(unidades=Sum('cantidad'), ingresos=Sum('subtotal'))
            .order_by('-unidades', 'producto__nombre')[:5]
        ),
    }


def ventas_por_tienda():
    """Para el administrador principal: lo cobrado este mes y los pedidos pendientes de cada tienda."""
    _, inicio_mes = _inicio_del_dia_y_del_mes()
    cobrado = Q(pedidos__fecha_pago__gte=inicio_mes) & ~Q(pedidos__estado=Pedido.Estado.CANCELADO)
    return Tienda.objects.annotate(
        ventas_mes=Sum('pedidos__total', filter=cobrado),
        pedidos_mes=Count('pedidos', filter=cobrado),
        pendientes=Count('pedidos', filter=Q(pedidos__estado=Pedido.Estado.PENDIENTE)),
    ).order_by(F('ventas_mes').desc(nulls_last=True), 'nombre')
