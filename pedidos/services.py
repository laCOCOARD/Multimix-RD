"""Reglas de negocio de los pedidos: totales, creacion, stock y cambios de estado."""
import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from catalogo.models import Categoria, Disponibilidad, Producto
from core.impuestos import calcular_itbis
from core.models import ConfiguracionTienda
from promociones.models import Cupon
from promociones.services import (
    CuponInvalido, calcular_descuento, devolver_uso, normalizar_codigo, registrar_uso, validar_cupon,
)
from tiendas.services import ve_todas

from . import avisos
from .models import DetallePedido, EventoPedido, Pedido, SecuenciaTienda, SolicitudDevolucion, ZonaEnvio

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
    impuesto: Decimal = CERO

    @property
    def total(self):
        return self.subtotal - self.descuento + self.impuesto + self.costo_envio


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
        impuesto=resumen.impuesto,
    )


def metodos_pago_disponibles(metodo_entrega, tienda):
    """Formas de pago que la tienda acepta para el metodo de entrega elegido."""
    metodos = [Pago.TRANSFERENCIA]
    if metodo_entrega == Entrega.RECOGER:
        metodos.append(Pago.EFECTIVO_RECOGER)
    elif metodo_entrega == Entrega.ENVIO and tienda.permitir_contra_entrega:
        metodos.append(Pago.CONTRA_ENTREGA)
    return metodos


def supera_limite_por_ip(ip):
    """Anti-spam: True si esa IP ya creo demasiados pedidos en la ventana configurada."""
    if not ip:
        return False
    desde = timezone.now() - timedelta(minutes=settings.PEDIDOS_VENTANA_IP_MINUTOS)
    return Pedido.objects.filter(ip=ip, creado__gte=desde).count() >= settings.PEDIDOS_MAX_POR_IP


def supera_limite_por_cuenta(cliente):
    """Anti-spam que no depende de la IP: pedidos de una misma cuenta dentro de la ventana configurada."""
    desde = timezone.now() - timedelta(minutes=settings.PEDIDOS_VENTANA_IP_MINUTOS)
    return Pedido.objects.filter(cliente=cliente, creado__gte=desde).count() >= settings.PEDIDOS_MAX_POR_CUENTA


# --- Creacion del pedido -------------------------------------------------------------

def _siguiente_numero(tienda):
    """PREFIJO-AAAA-NNNNN, con un contador por tienda y año. Debe llamarse dentro de una transaccion."""
    anio = timezone.localdate().year
    SecuenciaTienda.objects.get_or_create(tienda=tienda, anio=anio)
    secuencia = SecuenciaTienda.objects.select_for_update().get(tienda=tienda, anio=anio)
    secuencia.ultimo += 1
    secuencia.save(update_fields=['ultimo'])
    return f'{tienda.prefijo}-{anio}-{secuencia.ultimo:05d}'


def _validar_entrega_y_pago(datos, tienda):
    metodo_entrega = datos.get('metodo_entrega')
    zona = datos.get('zona')
    if metodo_entrega not in Entrega.values:
        raise PedidoError('Elige cómo quieres recibir tu pedido.')
    if metodo_entrega == Entrega.ENVIO:
        if zona is None or not zona.activa or zona.tienda_id != tienda.pk:
            raise PedidoError('Elige una zona de envío.')
        if not (datos.get('direccion') or '').strip():
            raise PedidoError('Escribe la dirección de entrega.')
    if datos.get('metodo_pago') not in metodos_pago_disponibles(metodo_entrega, tienda):
        raise PedidoError('Esa forma de pago no está disponible para la entrega elegida.')


@transaction.atomic
def crear_pedido(carrito, datos, ip=None, cliente=None):
    """Crea el pedido de la tienda del carrito con los precios actuales, reserva el stock y cuenta el cupon.

    `datos` trae los campos ya validados del checkout. Ningun monto viene del cliente. Productos,
    zona y cupon deben ser de esa misma tienda. Solo se aparta el stock de los productos que llevan
    inventario; los demas se venden por su disponibilidad.
    """
    tienda = carrito.tienda
    cantidades = {int(pk): cantidad for pk, cantidad in carrito.items.items() if cantidad > 0}
    if not cantidades:
        raise PedidoError('Tu carrito está vacío.')
    _validar_entrega_y_pago(datos, tienda)

    productos = {
        p.pk: p for p in
        Producto.objects.select_for_update().filter(tienda=tienda, pk__in=cantidades).order_by('pk')
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
        elif not producto.se_puede_comprar:
            if producto.estado_venta == Disponibilidad.AGOTADO:
                problemas.append(f'"{producto.nombre}" se agotó.')
            else:
                problemas.append(f'"{producto.nombre}" no está disponible por ahora.')
        elif producto.controla_stock and cantidad > producto.stock_disponible:
            problemas.append(f'Solo quedan {producto.stock_disponible} de "{producto.nombre}".')
    if problemas:
        raise StockInsuficiente(' '.join(problemas))

    lineas = [(productos[pk], cantidad) for pk, cantidad in cantidades.items()]
    subtotal = sum((p.precio_final * cantidad for p, cantidad in lineas), CERO)

    cupon = None
    codigo = normalizar_codigo(carrito.codigo_cupon)
    if codigo:
        try:
            cupon = validar_cupon(codigo, subtotal, tienda, bloquear=True, cliente=cliente)
        except CuponInvalido as error:
            raise PedidoError(f'El cupón {codigo} ya no se puede usar: {error.mensaje}') from error
    descuento = calcular_descuento(cupon, subtotal)
    impuesto = calcular_itbis(
        ((p.precio_final * cantidad, p.exento_itbis) for p, cantidad in lineas), descuento, tienda.itbis_porcentaje,
    )

    metodo_entrega = datos['metodo_entrega']
    a_domicilio = metodo_entrega == Entrega.ENVIO
    zona = datos.get('zona') if a_domicilio else None
    costo_envio = costo_de_envio(metodo_entrega, zona)
    por_transferencia = datos['metodo_pago'] == Pago.TRANSFERENCIA

    pedido = Pedido.objects.create(
        tienda=tienda,
        cliente=cliente,
        numero=_siguiente_numero(tienda),
        nombre=datos['nombre'],
        telefono=datos['telefono'],
        correo=datos.get('correo') or '',
        metodo_entrega=metodo_entrega,
        zona=zona,
        sector=(datos.get('sector') or '').strip() if a_domicilio else '',
        direccion=(datos.get('direccion') or '').strip() if a_domicilio else '',
        referencia=(datos.get('referencia') or '').strip() if a_domicilio else '',
        metodo_pago=datos['metodo_pago'],
        transferencia_realizada=bool(datos.get('transferencia_realizada')) and por_transferencia,
        referencia_transferencia=(datos.get('referencia_transferencia') or '').strip() if por_transferencia else '',
        cobra_el_sitio=por_transferencia,
        cupon=cupon,
        codigo_cupon=cupon.codigo if cupon else '',
        subtotal=subtotal,
        descuento=descuento,
        impuesto=impuesto,
        porcentaje_impuesto=tienda.itbis_porcentaje if impuesto else CERO,
        costo_envio=costo_envio,
        total=subtotal - descuento + impuesto + costo_envio,
        notas_cliente=(datos.get('notas') or '').strip(),
        ip=ip,
    )
    DetallePedido.objects.bulk_create([
        DetallePedido(
            pedido=pedido, producto=producto, nombre_producto=producto.nombre,
            precio_unitario=producto.precio_final, cantidad=cantidad,
            subtotal=producto.precio_final * cantidad, reserva_stock=producto.controla_stock,
        )
        for producto, cantidad in lineas
    ])
    for producto, cantidad in lineas:
        if not producto.controla_stock:
            continue
        producto.stock_reservado += cantidad
        producto.save(update_fields=['stock_reservado', 'actualizado'])
    if cupon:
        registrar_uso(cupon)
    # Se importa aqui: pagos.services usa este modulo para cambiar el estado del pedido.
    from pagos.services import pago_vigente
    pago_vigente(pedido)
    EventoPedido.objects.create(pedido=pedido, estado=Estado.PENDIENTE, nota='Pedido recibido')
    avisos.pedido_creado(pedido)

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

def transiciones_permitidas(pedido, usuario=None):
    """Estados a los que puede pasar el pedido segun su estado, entrega y forma de pago.

    Con `usuario` se quitan los que no le tocan: si el pedido lo cobra el sitio, el dinero esta en las cuentas del
    dueño y solo el administrador principal confirma el pago, lo reembolsa o cancela un pedido que el cliente dice
    haber transferido.
    """
    estados = _transiciones(pedido)
    if usuario is not None and pedido.cobra_el_sitio and not ve_todas(usuario):
        reservados = [Estado.PAGADO, Estado.REEMBOLSADO]
        # Cancelar un pedido cuyo dinero ya esta (o dicen que esta) en las cuentas del dueño obliga a devolverlo:
        # lo decide el administrador.
        if pedido.fecha_pago or (pedido.estado == Estado.PENDIENTE and pedido.transferencia_realizada):
            reservados.append(Estado.CANCELADO)
        estados = [estado for estado in estados if estado not in reservados]
    return estados


def _transiciones(pedido):
    despacho = Estado.LISTO if pedido.recoge_en_tienda else Estado.ENVIADO
    if pedido.estado == Estado.PENDIENTE:
        if pedido.paga_por_transferencia:
            return [Estado.PAGADO, Estado.CANCELADO]
        return [Estado.PAGADO, Estado.PREPARANDO, despacho, Estado.ENTREGADO, Estado.CANCELADO]
    if pedido.estado == Estado.PAGADO:
        return [Estado.PREPARANDO, despacho, Estado.ENTREGADO, Estado.CANCELADO]
    if pedido.estado == Estado.PREPARANDO:
        return [despacho, Estado.ENTREGADO, Estado.CANCELADO]
    if pedido.estado == Estado.LISTO:
        return [Estado.ENTREGADO, Estado.CANCELADO]
    if pedido.estado == Estado.ENVIADO:
        return [Estado.EN_REPARTO, Estado.ENTREGADO]
    if pedido.estado == Estado.EN_REPARTO:
        return [Estado.ENTREGADO]
    # Lo cobrado se puede devolver: despues de entregado, o si se cancelo cuando ya estaba pagado.
    if pedido.estado in (Estado.ENTREGADO, Estado.CANCELADO) and pedido.fecha_pago:
        return [Estado.REEMBOLSADO]
    return []


def _productos_bloqueados(pedido):
    """Productos del pedido que apartaron stock, bloqueados, con su cantidad."""
    detalles = list(pedido.detalles.filter(reserva_stock=True))
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
def cambiar_estado(pedido, nuevo_estado, usuario=None, nota=''):
    """Unica puerta para cambiar el estado de un pedido. Lanza TransicionInvalida si no procede.

    `usuario` es quien lo cambia desde el panel y `nota` un comentario que vera el cliente en el seguimiento.
    Un reembolso no devuelve stock: lo entregado se repone a mano si vuelve a la tienda.
    """
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if nuevo_estado in _transiciones(pedido) and nuevo_estado not in transiciones_permitidas(pedido, usuario):
        raise TransicionInvalida(
            f'El pago del pedido {pedido.numero} lo recibe el sitio en sus cuentas: lo confirma el administrador '
            'principal.'
        )
    if nuevo_estado not in transiciones_permitidas(pedido):
        destino = Estado(nuevo_estado).label if nuevo_estado in Estado.values else nuevo_estado
        raise TransicionInvalida(
            f'El pedido {pedido.numero} está "{pedido.get_estado_display()}" y no puede pasar a "{destino}".'
        )
    ahora = timezone.now()
    anterior = pedido.estado

    if nuevo_estado == Estado.PAGADO:
        pedido.fecha_pago = ahora
    elif nuevo_estado in (Estado.ENVIADO, Estado.EN_REPARTO, Estado.ENTREGADO):
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
    EventoPedido.objects.create(pedido=pedido, estado=nuevo_estado, nota=(nota or '')[:255], usuario=usuario)
    from pagos.services import sincronizar_con_pedido
    sincronizar_con_pedido(pedido)
    avisos.estado_cambiado(pedido)
    if nuevo_estado == Estado.PAGADO and pedido.cobra_el_sitio:
        avisos.pago_confirmado_a_la_tienda(pedido)
    logger.info('Pedido %s: %s -> %s', pedido.numero, anterior, nuevo_estado)
    return pedido


def puede_eliminar(pedido, usuario=None):
    """Un pedido con dinero de por medio (cobrado, con la transferencia avisada o ya liquidado) es el registro de
    ese dinero y de la comision del sitio: solo lo borra el administrador principal. `usuario` vacio es el sistema."""
    if usuario is None or ve_todas(usuario):
        return True
    return (
        pedido.fecha_pago is None and not pedido.transferencia_realizada
        and pedido.liquidacion_id is None and pedido.ajuste_liquidacion_id is None
    )


@transaction.atomic
def eliminar_pedido(pedido, usuario=None):
    """Borra el pedido del historial y devuelve su numero.

    Si todavia se podia cancelar, antes lo cancela: asi libera su reserva y el uso del cupon.
    Lo enviado o entregado ya salio del almacen y se borra sin devolver stock.
    """
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if not puede_eliminar(pedido, usuario):
        raise PedidoError(
            f'El pedido {pedido.numero} ya tiene un pago registrado o avisado: solo el administrador principal puede '
            'eliminarlo.'
        )
    numero, estado = pedido.numero, pedido.estado
    if Estado.CANCELADO in transiciones_permitidas(pedido):
        pedido = cambiar_estado(pedido, Estado.CANCELADO)
    pedido.delete()
    logger.info('Pedido %s eliminado (estaba %s)', numero, estado)
    return numero


def cancelar_pedidos_vencidos():
    """Cancela los pendientes mas viejos que las horas configuradas. Devuelve sus numeros.

    Nunca los que tienen la transferencia avisada: el cliente dice que ya pago y su comprobante espera a que lo
    revisen. Esos solo los cancela una persona desde el panel, despues de mirar el banco.
    """
    horas = ConfiguracionTienda.obtener().horas_vencimiento_pedido
    limite = timezone.now() - timedelta(hours=horas)
    vencidos = Pedido.objects.filter(estado=Estado.PENDIENTE, creado__lt=limite, transferencia_realizada=False)
    cancelados = []
    for pedido in vencidos.order_by('creado'):
        with transaction.atomic():
            # Se mira otra vez con el pedido bloqueado: el cliente pudo avisar la transferencia (o la tienda
            # cambiar el estado) entre la consulta y este momento.
            pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
            if pedido.estado != Estado.PENDIENTE or pedido.transferencia_realizada:
                continue
            try:
                cambiar_estado(pedido, Estado.CANCELADO, nota='Cancelado porque venció el plazo para pagar')
            except TransicionInvalida:
                continue
        cancelados.append(pedido.numero)
    return cancelados


# --- Lo que puede hacer el cliente con su pedido ------------------------------------------------

def puede_cancelar_el_cliente(pedido):
    """Solo antes de pagar: pendiente y sin haber avisado que ya transfirio."""
    return pedido.estado == Estado.PENDIENTE and not pedido.transferencia_realizada and pedido.fecha_pago is None


def cancelar_por_cliente(pedido):
    if not puede_cancelar_el_cliente(pedido):
        raise PedidoError('Este pedido ya no se puede cancelar desde aquí. Escribe a la tienda.')
    return cambiar_estado(pedido, Estado.CANCELADO, nota='Cancelado por el cliente')


def devolucion_abierta(pedido):
    """La solicitud de devolucion que el cliente ya hizo, si no fue rechazada."""
    return pedido.devoluciones.exclude(estado=SolicitudDevolucion.Estado.RECHAZADA).order_by('-id').first()


def puede_pedir_devolucion(pedido):
    dias = ConfiguracionTienda.obtener().dias_devolucion
    if not dias or pedido.estado != Estado.ENTREGADO or pedido.fecha_entrega is None:
        return False
    if timezone.now() > pedido.fecha_entrega + timedelta(days=dias):
        return False
    return devolucion_abierta(pedido) is None


@transaction.atomic
def solicitar_devolucion(pedido, motivo):
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    motivo = (motivo or '').strip()
    if not puede_pedir_devolucion(pedido):
        raise PedidoError('Este pedido ya no admite solicitudes de devolución.')
    if len(motivo) < 10:
        raise PedidoError('Cuéntale a la tienda por qué quieres devolver el pedido.')
    solicitud = SolicitudDevolucion.objects.create(tienda_id=pedido.tienda_id, pedido=pedido, motivo=motivo[:600])
    avisos.devolucion_solicitada(solicitud)
    return solicitud


@transaction.atomic
def responder_devolucion(solicitud, aceptar, usuario=None, respuesta=''):
    """La tienda acepta o rechaza. Aceptar no mueve dinero: el reembolso se registra en el pedido."""
    solicitud = SolicitudDevolucion.objects.select_for_update().get(pk=solicitud.pk)
    if solicitud.estado != SolicitudDevolucion.Estado.PENDIENTE:
        raise PedidoError(f'La solicitud del pedido {solicitud.pedido.numero} ya fue respondida.')
    solicitud.estado = SolicitudDevolucion.Estado.ACEPTADA if aceptar else SolicitudDevolucion.Estado.RECHAZADA
    solicitud.respuesta = (respuesta or solicitud.respuesta or '')[:255]
    solicitud.resuelto_en = timezone.now()
    solicitud.resuelto_por = usuario
    solicitud.save()
    avisos.devolucion_respondida(solicitud)
    return solicitud


def zonas_activas(tienda):
    return ZonaEnvio.objects.filter(tienda=tienda, activa=True)


# --- Clientes ------------------------------------------------------------------------

def clientes(pedidos, busqueda=''):
    """Clientes de esos pedidos: una fila por tienda y telefono, de la compra mas reciente a la mas antigua.

    No hay tabla de clientes: salen de los pedidos. Quien compra en dos tiendas aparece en cada una.
    `comprado` suma lo cobrado (con fecha de pago y sin cancelar), igual que las ventas del panel.
    """
    busqueda = (busqueda or '').strip()
    if busqueda:
        digitos = ''.join(c for c in busqueda if c.isdigit())
        filtro = Q(nombre__icontains=busqueda)
        if digitos:
            filtro |= Q(telefono__contains=digitos)
        pedidos = pedidos.filter(filtro)
    vigente = ~Q(estado__in=Pedido.ESTADOS_SIN_VENTA)
    return (
        pedidos.order_by().values('tienda_id', 'telefono')
        .annotate(
            total_pedidos=Count('id', filter=vigente),
            comprado=Sum('total', filter=vigente & Q(fecha_pago__isnull=False)),
            ultima_compra=Max('creado'),
        )
        .order_by('-ultima_compra', 'telefono')
    )


def completar_clientes(filas, pedidos):
    """Agrega a cada fila de `clientes` el nombre y correo de su pedido mas reciente y el nombre de la tienda."""
    filas = list(filas)
    recientes = {}
    datos = (
        pedidos.filter(telefono__in={fila['telefono'] for fila in filas})
        .order_by('creado', 'id').values_list('tienda_id', 'telefono', 'nombre', 'correo', 'tienda__nombre')
    )
    for tienda_id, telefono, nombre, correo, tienda in datos:
        anterior = recientes.get((tienda_id, telefono), {})
        recientes[tienda_id, telefono] = {
            'nombre': nombre, 'correo': correo or anterior.get('correo', ''), 'tienda': tienda,
        }
    for fila in filas:
        fila.update(recientes.get((fila['tienda_id'], fila['telefono']), {}))
        fila['comprado'] = fila['comprado'] or CERO
    return filas
