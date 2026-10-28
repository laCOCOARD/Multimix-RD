"""Datos del resumen que se muestra en la portada del panel de administracion."""
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from catalogo.models import Producto, q_agotado, q_comprable
from pedidos.models import DetallePedido, Pedido
from tiendas.models import Tienda

from .models import ConfiguracionTienda


def _ventas_desde(pedidos, inicio):
    """Suma de pedidos cobrados (con fecha de pago) y no cancelados desde `inicio`."""
    return (
        pedidos.filter(fecha_pago__gte=inicio).exclude(estado__in=Pedido.ESTADOS_SIN_VENTA)
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

    # El stock bajo solo tiene sentido en los productos que llevan inventario.
    productos = productos.annotate(disponible=F('stock_almacen') - F('stock_reservado'))
    stock_bajo = (
        productos.filter(q_comprable(), controla_stock=True, disponible__lte=umbral).order_by('disponible', 'nombre')
    )
    agotados = productos.filter(q_agotado()).order_by('nombre')
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
    cobrado = Q(pedidos__fecha_pago__gte=inicio_mes) & ~Q(pedidos__estado__in=Pedido.ESTADOS_SIN_VENTA)
    return Tienda.objects.annotate(
        ventas_mes=Sum('pedidos__total', filter=cobrado),
        pedidos_mes=Count('pedidos', filter=cobrado),
        pendientes=Count('pedidos', filter=Q(pedidos__estado=Pedido.Estado.PENDIENTE)),
    ).order_by(F('ventas_mes').desc(nulls_last=True), 'nombre')


# --- Inicio del panel para el dueño de la tienda ----------------------------------------------------------------

def _enlace(nombre, filtros=''):
    from django.urls import reverse

    return reverse(f'admin:{nombre}') + (f'?{filtros}' if filtros else '')


def tareas_de_la_tienda(tiendas):
    """Lo que el vendedor tiene que hacer ahora, en el orden en que conviene hacerlo. Solo lo que tiene algo."""
    from catalogo.models import AvisoDisponible
    from opiniones.models import Pregunta
    from pedidos.models import SolicitudDevolucion

    pedidos = Pedido.objects.filter(tienda__in=tiendas)
    E = Pedido.Estado
    pendientes = pedidos.filter(estado=E.PENDIENTE)
    filas = [
        (pendientes.filter(transferencia_realizada=True).count(), 'transferencia por confirmar',
         'transferencias por confirmar', 'Mira el comprobante y, si el dinero llegó, márcalo como pagado.',
         _enlace('pedidos_pedido_changelist', 'estado__exact=pendiente&transferencia_realizada__exact=1'), True),
        (pendientes.filter(metodo_pago=Pedido.Pago.CONTRA_ENTREGA).count(), 'pedido contra entrega',
         'pedidos contra entrega', 'Prepáralo y cóbralo al entregarlo.',
         _enlace('pedidos_pedido_changelist', 'estado__exact=pendiente&metodo_pago__exact=contra_entrega'), True),
        (pedidos.filter(estado=E.PAGADO).count(), 'pedido pagado por preparar', 'pedidos pagados por preparar',
         'Ya están cobrados: prepáralos y cambia su estado.',
         _enlace('pedidos_pedido_changelist', 'estado__exact=pagado'), True),
        (pedidos.filter(estado=E.PREPARANDO).count(), 'pedido en preparación', 'pedidos en preparación',
         'Cuando esté listo, márcalo como listo para recoger o enviado.',
         _enlace('pedidos_pedido_changelist', 'estado__exact=preparando'), False),
        (pedidos.filter(estado__in=[E.LISTO, E.ENVIADO, E.EN_REPARTO]).count(), 'pedido por entregar',
         'pedidos por entregar', 'Márcalo como entregado cuando el cliente lo reciba.',
         _enlace('pedidos_pedido_changelist', 'estado__in=listo,enviado,en_reparto'), False),
        (SolicitudDevolucion.objects.filter(tienda__in=tiendas, estado=SolicitudDevolucion.Estado.PENDIENTE).count(),
         'devolución por revisar', 'devoluciones por revisar', 'Acéptala o recházala y explica por qué.',
         _enlace('pedidos_solicituddevolucion_changelist', 'estado__exact=pendiente'), True),
        (Pregunta.objects.filter(tienda__in=tiendas, estado=Pregunta.Estado.PENDIENTE).count(),
         'pregunta sin responder', 'preguntas sin responder', 'Respóndela: se publica en el producto.',
         _enlace('opiniones_pregunta_changelist', 'estado__exact=pendiente'), False),
        (AvisoDisponible.objects.filter(tienda__in=tiendas, avisado__isnull=True).count(),
         'cliente esperando un producto', 'clientes esperando un producto',
         'Cuando lo vuelvas a tener, márcalo como disponible: les llega un correo.',
         _enlace('catalogo_avisodisponible_changelist', 'avisado__isempty=1'), False),
    ]
    return [
        {'cantidad': n, 'texto': uno if n == 1 else varios, 'ayuda': ayuda, 'url': url, 'urgente': urgente}
        for n, uno, varios, ayuda, url, urgente in filas if n
    ]


def primeros_pasos(tienda):
    """Lo minimo para que la tienda venda. Devuelve los pasos con `hecho`; la portada los muestra mientras falte alguno."""
    from catalogo.models import FotoProducto

    con_foto = FotoProducto.objects.filter(producto__tienda=tienda, producto__activo=True).exists()
    from django.urls import reverse

    datos = reverse('admin:tiendas_tienda_change', args=[tienda.pk])
    entrega = bool(tienda.direccion_tienda) or tienda.zonas_envio.filter(activa=True).exists()
    return [
        {'texto': 'Pon tu número de WhatsApp', 'hecho': bool(tienda.whatsapp), 'url': datos},
        {'texto': 'Agrega una cuenta de banco para recibir transferencias',
         'hecho': tienda.cuentas.filter(activa=True).exists(), 'url': _enlace('tiendas_cuentabancaria_add')},
        {'texto': 'Publica tu primer producto con foto', 'hecho': con_foto, 'url': _enlace('catalogo_producto_add')},
        {'texto': 'Di cómo entregas: dirección para recoger o zonas de envío', 'hecho': entrega,
         'url': _enlace('pedidos_zonaenvio_changelist')},
    ]
