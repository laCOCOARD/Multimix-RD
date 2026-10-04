"""Datos del resumen que se muestra en la portada del panel de administracion."""
from django.db.models import F, Sum
from django.utils import timezone

from catalogo.models import Producto
from pedidos.models import DetallePedido, Pedido

from .models import ConfiguracionTienda


def _ventas_desde(inicio):
    """Suma de pedidos cobrados (con fecha de pago) y no cancelados desde `inicio`."""
    return (
        Pedido.objects.filter(fecha_pago__gte=inicio).exclude(estado=Pedido.Estado.CANCELADO)
        .aggregate(total=Sum('total'))['total'] or 0
    )


def resumen_panel():
    ahora = timezone.localtime()
    inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_mes = inicio_dia.replace(day=1)
    umbral = ConfiguracionTienda.obtener().umbral_stock_bajo

    productos = Producto.objects.filter(activo=True).annotate(disponible=F('stock_almacen') - F('stock_reservado'))
    stock_bajo = productos.filter(disponible__gt=0, disponible__lte=umbral).order_by('disponible', 'nombre')
    agotados = productos.filter(disponible__lte=0).order_by('nombre')
    pendientes = Pedido.objects.filter(estado=Pedido.Estado.PENDIENTE)

    return {
        'ventas_dia': _ventas_desde(inicio_dia),
        'ventas_mes': _ventas_desde(inicio_mes),
        'pedidos_pendientes': pendientes.count(),
        'transferencias_por_verificar': pendientes.filter(transferencia_realizada=True).count(),
        'total_stock_bajo': stock_bajo.count(),
        'total_agotados': agotados.count(),
        'stock_bajo': stock_bajo[:8],
        'agotados': agotados[:8],
        'umbral_stock_bajo': umbral,
        'ultimos_pedidos': Pedido.objects.order_by('-creado')[:8],
        'mas_vendidos': (
            DetallePedido.objects.filter(pedido__estado__in=Pedido.ESTADOS_VENTA)
            .values('producto_id', 'producto__nombre')
            .annotate(unidades=Sum('cantidad'), ingresos=Sum('subtotal'))
            .order_by('-unidades', 'producto__nombre')[:5]
        ),
    }
