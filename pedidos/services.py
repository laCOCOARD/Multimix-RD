"""Reglas de negocio de los pedidos: totales, creacion, stock y cambios de estado."""
import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from catalogo.models import Categoria, Producto
from core.models import ConfiguracionTienda
from promociones.models import Cupon
from promociones.services import (
    CuponInvalido, calcular_descuento, devolver_uso, normalizar_codigo, registrar_uso, validar_cupon,
)

from .models import DetallePedido, Pedido, SecuenciaPedido, ZonaEnvio

logger = logging.getLogger('multimix.pedidos')

CERO = Decimal('0.00')
Estado = Pedido.Estado
Entrega = Pedido.Entrega
Pago = Pedido.Pago


class PedidoError(Exception):
    """Error de negocio con un mensaje listo para mostrar."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


class StockInsuficiente(PedidoError):
    pass


class TransicionInvalida(PedidoError):
    pass


# --- Totales y opciones del checkout -------------------------------------------------

@dataclass
class Totales:
    subtotal: Decimal
    descuento: Decimal
    costo_envio: Decimal
    cupon: Cupon | None = None
    aviso_cupon: str = ''

    @property
    def total(self):
        return self.subtotal - self.descuento + self.costo_envio


def costo_de_envio(metodo_entrega, zona):
    """Recoger en tienda no paga envio; a domicilio paga la tarifa de la zona."""
    if metodo_entrega == Entrega.ENVIO and zona is not None:
        return zona.tarifa
    return CERO


def calcular_totales(carrito, metodo_entrega=Entrega.RECOGER, zona=None):
    """Totales del carrito calculados en el servidor a partir de los precios actuales."""
    resumen = carrito.resumen()
    return Totales(
        subtotal=resumen.subtotal,
        descuento=resumen.descuento,
        costo_envio=costo_de_envio(metodo_entrega, zona),
        cupon=resumen.cupon,
        aviso_cupon=resumen.aviso_cupon,
    )


def metodos_pago_disponibles(metodo_entrega, config=None):
    """Formas de pago que aplican al metodo de entrega elegido."""
    config = config or ConfiguracionTienda.obtener()
    metodos = [Pago.TRANSFERENCIA]
    if metodo_entrega == Entrega.RECOGER:
        metodos.append(Pago.EFECTIVO_RECOGER)
    elif metodo_entrega == Entrega.ENVIO and config.permitir_contra_entrega:
        metodos.append(Pago.CONTRA_ENTREGA)
    return metodos


def supera_limite_por_ip(ip):
    """Anti-spam: True si esa IP ya creo demasiados pedidos en la ventana configurada."""
    if not ip:
        return False
    desde = timezone.now() - timedelta(minutes=settings.PEDIDOS_VENTANA_IP_MINUTOS)
    return Pedido.objects.filter(ip=ip, creado__gte=desde).count() >= settings.PEDIDOS_MAX_POR_IP


# --- Creacion del pedido -------------------------------------------------------------

def _siguiente_numero():
    """MMX-AAAA-NNNNN. Debe llamarse dentro de una transaccion."""
    anio = timezone.localdate().year
    SecuenciaPedido.objects.get_or_create(anio=anio)
    secuencia = SecuenciaPedido.objects.select_for_update().get(anio=anio)
    secuencia.ultimo += 1
    secuencia.save(update_fields=['ultimo'])
    return f'MMX-{anio}-{secuencia.ultimo:05d}'


def _validar_entrega_y_pago(datos):
    metodo_entrega = datos.get('metodo_entrega')
    zona = datos.get('zona')
    if metodo_entrega not in Entrega.values:
        raise PedidoError('Elige cómo quieres recibir tu pedido.')
    if metodo_entrega == Entrega.ENVIO:
        if zona is None or not zona.activa:
            raise PedidoError('Elige una zona de envío.')
        if not (datos.get('direccion') or '').strip():
            raise PedidoError('Escribe la dirección de entrega.')
    if datos.get('metodo_pago') not in metodos_pago_disponibles(metodo_entrega):
        raise PedidoError('Esa forma de pago no está disponible para la entrega elegida.')


@transaction.atomic
def crear_pedido(carrito, datos, ip=None):
    """Crea el pedido con los precios actuales, reserva el stock y registra el uso del cupon.

    `datos` trae los campos ya validados del checkout. Ningun monto viene del cliente.
    """
    cantidades = {int(pk): cantidad for pk, cantidad in carrito.items.items() if cantidad > 0}
    if not cantidades:
        raise PedidoError('Tu carrito está vacío.')
    _validar_entrega_y_pago(datos)

    productos = {
        p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=cantidades).order_by('pk')
    }
    categorias_activas = set(
        Categoria.objects.filter(pk__in={p.categoria_id for p in productos.values()}, activa=True)
        .values_list('pk', flat=True)
    )

    problemas = []
    for pk, cantidad in cantidades.items():
        producto = productos.get(pk)
        if producto is None or not producto.activo or producto.categoria_id not in categorias_activas:
            problemas.append('Un producto de tu carrito ya no está disponible.')
        elif cantidad > producto.stock_disponible:
            if producto.stock_disponible == 0:
                problemas.append(f'"{producto.nombre}" se agotó.')
            else:
                problemas.append(f'Solo quedan {producto.stock_disponible} de "{producto.nombre}".')
    if problemas:
        raise StockInsuficiente(' '.join(problemas))

    lineas = [(productos[pk], cantidad) for pk, cantidad in cantidades.items()]
    subtotal = sum((p.precio_final * cantidad for p, cantidad in lineas), CERO)

    cupon = None
    codigo = normalizar_codigo(carrito.codigo_cupon)
    if codigo:
        try:
            cupon = validar_cupon(codigo, subtotal, bloquear=True)
        except CuponInvalido as error:
            raise PedidoError(f'El cupón {codigo} ya no se puede usar: {error.mensaje}') from error
    descuento = calcular_descuento(cupon, subtotal)

    metodo_entrega = datos['metodo_entrega']
    a_domicilio = metodo_entrega == Entrega.ENVIO
    zona = datos.get('zona') if a_domicilio else None
    costo_envio = costo_de_envio(metodo_entrega, zona)
    por_transferencia = datos['metodo_pago'] == Pago.TRANSFERENCIA

    pedido = Pedido.objects.create(
        numero=_siguiente_numero(),
        nombre=datos['nombre'],
        telefono=datos['telefono'],
        correo=datos.get('correo') or '',
        metodo_entrega=metodo_entrega,
        zona=zona,
        direccion=(datos.get('direccion') or '').strip() if a_domicilio else '',
        referencia=(datos.get('referencia') or '').strip() if a_domicilio else '',
        metodo_pago=datos['metodo_pago'],
        transferencia_realizada=bool(datos.get('transferencia_realizada')) and por_transferencia,
        referencia_transferencia=(datos.get('referencia_transferencia') or '').strip() if por_transferencia else '',
        cupon=cupon,
        codigo_cupon=cupon.codigo if cupon else '',
        subtotal=subtotal,
        descuento=descuento,
        costo_envio=costo_envio,
        total=subtotal - descuento + costo_envio,
        notas_cliente=(datos.get('notas') or '').strip(),
        ip=ip,
    )
    DetallePedido.objects.bulk_create([
        DetallePedido(
            pedido=pedido, producto=producto, nombre_producto=producto.nombre,
            precio_unitario=producto.precio_final, cantidad=cantidad,
            subtotal=producto.precio_final * cantidad,
        )
        for producto, cantidad in lineas
    ])
    for producto, cantidad in lineas:
        producto.stock_reservado += cantidad
        producto.save(update_fields=['stock_reservado', 'actualizado'])
    if cupon:
        registrar_uso(cupon)

    logger.info('Pedido %s creado por RD$ %s (%s productos)', pedido.numero, pedido.total, len(lineas))
    return pedido


def marcar_transferencia(pedido, referencia=''):
    """El cliente avisa que ya transfirio. No cambia el estado: eso lo confirma el administrador."""
    if not pedido.paga_por_transferencia or pedido.estado != Estado.PENDIENTE:
        raise PedidoError('Este pedido ya no admite avisos de transferencia.')
    pedido.transferencia_realizada = True
    pedido.referencia_transferencia = (referencia or '').strip()[:60]
    pedido.save(update_fields=['transferencia_realizada', 'referencia_transferencia'])
    return pedido


# --- Estados y stock -----------------------------------------------------------------

def transiciones_permitidas(pedido):
    """Estados a los que puede pasar el pedido segun su estado, entrega y forma de pago."""
    despacho = Estado.LISTO if pedido.recoge_en_tienda else Estado.ENVIADO
    if pedido.estado == Estado.PENDIENTE:
        if pedido.paga_por_transferencia:
            return [Estado.PAGADO, Estado.CANCELADO]
        return [Estado.PAGADO, despacho, Estado.ENTREGADO, Estado.CANCELADO]
    if pedido.estado == Estado.PAGADO:
        return [despacho, Estado.ENTREGADO, Estado.CANCELADO]
    if pedido.estado == Estado.LISTO:
        return [Estado.ENTREGADO, Estado.CANCELADO]
    if pedido.estado == Estado.ENVIADO:
        return [Estado.ENTREGADO]
    return []


def _productos_bloqueados(pedido):
    detalles = list(pedido.detalles.all())
    productos = {
        p.pk: p for p in
        Producto.objects.select_for_update().filter(pk__in=[d.producto_id for d in detalles]).order_by('pk')
    }
    return [(productos[d.producto_id], d.cantidad) for d in detalles]


def _descontar_stock(pedido):
    """Saca las unidades del almacen y libera su reserva. Solo ocurre una vez por pedido."""
    if pedido.stock_descontado:
        return
    for producto, cantidad in _productos_bloqueados(pedido):
        producto.stock_almacen = max(producto.stock_almacen - cantidad, 0)
        producto.stock_reservado = max(producto.stock_reservado - cantidad, 0)
        producto.save(update_fields=['stock_almacen', 'stock_reservado', 'actualizado'])
    pedido.stock_descontado = True


def _liberar_reserva(pedido):
    if pedido.stock_descontado:
        return
    for producto, cantidad in _productos_bloqueados(pedido):
        producto.stock_reservado = max(producto.stock_reservado - cantidad, 0)
        producto.save(update_fields=['stock_reservado', 'actualizado'])


@transaction.atomic
def cambiar_estado(pedido, nuevo_estado):
    """Unica puerta para cambiar el estado de un pedido. Lanza TransicionInvalida si no procede."""
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if nuevo_estado not in transiciones_permitidas(pedido):
        destino = Estado(nuevo_estado).label if nuevo_estado in Estado.values else nuevo_estado
        raise TransicionInvalida(
            f'El pedido {pedido.numero} está "{pedido.get_estado_display()}" y no puede pasar a "{destino}".'
        )
    ahora = timezone.now()
    anterior = pedido.estado

    if nuevo_estado == Estado.PAGADO:
        pedido.fecha_pago = ahora
    elif nuevo_estado in (Estado.ENVIADO, Estado.ENTREGADO):
        _descontar_stock(pedido)
        if nuevo_estado == Estado.ENTREGADO:
            pedido.fecha_entrega = ahora
            # Los pedidos en efectivo se cobran al entregar.
            if pedido.fecha_pago is None:
                pedido.fecha_pago = ahora
    elif nuevo_estado == Estado.CANCELADO:
        _liberar_reserva(pedido)
        if pedido.cupon_id:
            devolver_uso(pedido.cupon)

    pedido.estado = nuevo_estado
    pedido.save(update_fields=['estado', 'fecha_pago', 'fecha_entrega', 'stock_descontado'])
    logger.info('Pedido %s: %s -> %s', pedido.numero, anterior, nuevo_estado)
    return pedido


@transaction.atomic
def eliminar_pedido(pedido):
    """Borra el pedido del historial y devuelve su numero.

    Si todavia se podia cancelar, antes lo cancela: asi libera su reserva y el uso del cupon.
    Lo enviado o entregado ya salio del almacen y se borra sin devolver stock.
    """
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    numero, estado = pedido.numero, pedido.estado
    if Estado.CANCELADO in transiciones_permitidas(pedido):
        pedido = cambiar_estado(pedido, Estado.CANCELADO)
    pedido.delete()
    logger.info('Pedido %s eliminado (estaba %s)', numero, estado)
    return numero


def cancelar_pedidos_vencidos():
    """Cancela los pendientes mas viejos que las horas configuradas. Devuelve sus numeros."""
    horas = ConfiguracionTienda.obtener().horas_vencimiento_pedido
    limite = timezone.now() - timedelta(hours=horas)
    cancelados = []
    for pedido in Pedido.objects.filter(estado=Estado.PENDIENTE, creado__lt=limite).order_by('creado'):
        try:
            cambiar_estado(pedido, Estado.CANCELADO)
        except TransicionInvalida:
            # Otro proceso lo cambio entre la consulta y el bloqueo.
            continue
        cancelados.append(pedido.numero)
    return cancelados


def zonas_activas():
    return ZonaEnvio.objects.filter(activa=True)
