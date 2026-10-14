"""Reseñas de productos: quien puede opinar, la compra verificada y lo que se publica."""
from django.db.models import Avg, Count

from pedidos.models import DetallePedido, Pedido

from .models import Resena

Estado = Resena.Estado
PUBLICADAS_POR_PRODUCTO = 20


class ResenaError(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def compro_el_producto(usuario, producto):
    """True si lo recibio en un pedido hecho con su cuenta. Es lo unico que se puede comprobar."""
    return DetallePedido.objects.filter(
        producto=producto, pedido__cliente=usuario, pedido__estado=Pedido.Estado.ENTREGADO,
    ).exists()


def guardar_resena(usuario, producto, estrellas, comentario):
    """Crea la reseña del cliente o cambia la que ya tenia. Siempre vuelve a revision antes de publicarse."""
    try:
        estrellas = int(estrellas)
    except (TypeError, ValueError):
        estrellas = 0
    comentario = ' '.join((comentario or '').split())
    if not 1 <= estrellas <= 5:
        raise ResenaError('Elige de 1 a 5 estrellas.')
    if len(comentario) < 10:
        raise ResenaError('Cuenta un poco más sobre el producto (al menos 10 letras).')
    resena, _ = Resena.objects.update_or_create(
        producto=producto, usuario=usuario,
        defaults={
            'tienda_id': producto.tienda_id, 'estrellas': estrellas, 'comentario': comentario[:1000],
            'estado': Estado.PENDIENTE, 'compra_verificada': compro_el_producto(usuario, producto),
        },
    )
    return resena


def publicadas(producto):
    return list(
        Resena.objects.filter(producto=producto, estado=Estado.APROBADA).select_related('usuario')[:PUBLICADAS_POR_PRODUCTO]
    )


def resumen(producto):
    """Cantidad y promedio de las reseñas publicadas; promedio None si no hay ninguna."""
    datos = Resena.objects.filter(producto=producto, estado=Estado.APROBADA).aggregate(
        total=Count('id'), promedio=Avg('estrellas'),
    )
    promedio = round(datos['promedio'], 1) if datos['promedio'] is not None else None
    return {'total': datos['total'], 'promedio': promedio}


def resena_de(usuario, producto):
    if not usuario.is_authenticated:
        return None
    return Resena.objects.filter(producto=producto, usuario=usuario).first()
