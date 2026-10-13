"""Carrito de compras guardado en la sesion. Hay uno por tienda y nunca se mezclan:

{id_tienda: {'items': {id_producto: cantidad}, 'cupon': codigo}}
"""
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

from catalogo.models import Disponibilidad, Producto
from core.impuestos import calcular_itbis
from promociones.models import Cupon
from promociones.services import CuponInvalido, calcular_descuento, normalizar_codigo, validar_cupon


class CarritoError(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def aviso_no_comprable(producto):
    """Por que no se puede comprar ahora un producto que sigue publicado."""
    if producto.estado_venta == Disponibilidad.AGOTADO:
        return f'"{producto.nombre}" está agotado.'
    return f'"{producto.nombre}" no está disponible por ahora.'


def aviso_de_limite(producto, limite):
    """La cantidad pedida no cabe: por el stock si lleva inventario, o por el tope de unidades por pedido."""
    if producto.controla_stock and limite == producto.stock_disponible:
        return f'Solo quedan {limite} de "{producto.nombre}"; ajustamos la cantidad.'
    return f'Puedes llevar hasta {limite} de "{producto.nombre}" por pedido; ajustamos la cantidad.'


@dataclass
class LineaCarrito:
    producto: Producto
    cantidad: int

    @property
    def precio_unitario(self):
        return self.producto.precio_final

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad


@dataclass
class ResumenCarrito:
    subtotal: Decimal
    cupon: Cupon | None
    descuento: Decimal
    aviso_cupon: str = ''
    impuesto: Decimal = Decimal('0.00')

    @property
    def total(self):
        """Sin el envio, que se elige en el checkout."""
        return self.subtotal - self.descuento + self.impuesto


def _carritos(session):
    """Carritos de la sesion por id de tienda. Descarta el formato de cuando habia un solo carrito."""
    todos = session.get(settings.CARRITO_SESSION_ID)
    if not isinstance(todos, dict) or 'items' in todos:
        return {}
    return todos


def _carrito_de(session, tienda):
    datos = _carritos(session).get(str(tienda.pk))
    if not isinstance(datos, dict) or not isinstance(datos.get('items'), dict):
        return None
    return datos


def cantidad_en_sesion(session, tienda):
    """Unidades en el carrito de la tienda sin consultar la base; lo usa el contador del menu."""
    datos = _carrito_de(session, tienda)
    return sum(datos['items'].values()) if datos else 0


class Carrito:
    def __init__(self, request, tienda):
        self.session = request.session
        self.tienda = tienda
        self.datos = _carrito_de(self.session, tienda) or {'items': {}, 'cupon': ''}
        self._lineas = None

    def _guardar(self):
        todos = _carritos(self.session)
        todos[str(self.tienda.pk)] = self.datos
        self.session[settings.CARRITO_SESSION_ID] = todos
        self.session.modified = True
        self._lineas = None

    def _a_la_venta(self):
        return Producto.objects.activos().filter(tienda=self.tienda)

    @property
    def items(self):
        return self.datos['items']

    def __len__(self):
        return sum(self.items.values())

    def __bool__(self):
        return bool(self.items)

    def cantidad_de(self, producto_id):
        return self.items.get(str(producto_id), 0)

    def agregar(self, producto, cantidad=1, reemplazar=False):
        """Pone el producto en el carrito sin pasar de su limite de compra.

        Devuelve (cantidad_final, ajustada). Lanza CarritoError si no se puede comprar.
        """
        if producto.tienda_id != self.tienda.pk:
            raise CarritoError('Ese producto es de otra tienda.')
        if not producto.activo or not producto.categoria.activa:
            raise CarritoError('Este producto ya no está disponible.')
        limite = producto.limite_compra
        if limite <= 0:
            raise CarritoError(aviso_no_comprable(producto))
        clave = str(producto.pk)
        deseada = cantidad if reemplazar else self.items.get(clave, 0) + cantidad
        final = max(1, min(deseada, limite))
        self.items[clave] = final
        self._guardar()
        return final, final != deseada

    def eliminar(self, producto_id):
        if self.items.pop(str(producto_id), None) is not None:
            self._guardar()

    def vaciar(self):
        self.datos = {'items': {}, 'cupon': ''}
        self._guardar()

    def lineas(self):
        if self._lineas is None:
            productos = self._a_la_venta().para_listado().in_bulk([int(pk) for pk in self.items])
            self._lineas = [
                LineaCarrito(productos[int(pk)], cantidad)
                for pk, cantidad in self.items.items() if int(pk) in productos
            ]
        return self._lineas

    def sincronizar(self):
        """Ajusta el carrito a la disponibilidad actual. Devuelve los avisos para el cliente."""
        avisos = []
        if not self.items:
            return avisos
        productos = self._a_la_venta().in_bulk([int(pk) for pk in self.items])
        for clave, cantidad in list(self.items.items()):
            producto = productos.get(int(clave))
            if producto is None:
                del self.items[clave]
                avisos.append('Quitamos del carrito un producto que ya no está disponible.')
                continue
            limite = producto.limite_compra
            if limite <= 0:
                del self.items[clave]
                if producto.estado_venta == Disponibilidad.AGOTADO:
                    avisos.append(f'"{producto.nombre}" se agotó y lo quitamos del carrito.')
                else:
                    avisos.append(f'"{producto.nombre}" no está disponible por ahora y lo quitamos del carrito.')
            elif cantidad > limite:
                self.items[clave] = limite
                avisos.append(aviso_de_limite(producto, limite))
        if avisos:
            self._guardar()
        return avisos

    @property
    def subtotal(self):
        return sum((linea.subtotal for linea in self.lineas()), Decimal('0.00'))

    @property
    def codigo_cupon(self):
        return self.datos.get('cupon', '')

    def aplicar_cupon(self, codigo):
        """Valida el cupon de la tienda contra el subtotal actual y lo recuerda. Lanza CuponInvalido."""
        cupon = validar_cupon(codigo, self.subtotal, self.tienda)
        self.datos['cupon'] = cupon.codigo
        self._guardar()
        return cupon

    def quitar_cupon(self):
        if self.datos.get('cupon'):
            self.datos['cupon'] = ''
            self._guardar()

    def resumen(self):
        """Subtotal, descuento e ITBIS calculados en el servidor. Si el cupon dejo de aplicar, lo quita y avisa."""
        subtotal = self.subtotal
        codigo = normalizar_codigo(self.codigo_cupon)
        cupon, aviso = None, ''
        if codigo:
            try:
                cupon = validar_cupon(codigo, subtotal, self.tienda)
            except CuponInvalido as error:
                self.quitar_cupon()
                aviso = f'Quitamos el cupón {codigo}: {error.mensaje}'
        descuento = calcular_descuento(cupon, subtotal)
        impuesto = calcular_itbis(
            ((linea.subtotal, linea.producto.exento_itbis) for linea in self.lineas()),
            descuento, self.tienda.itbis_porcentaje,
        )
        return ResumenCarrito(subtotal, cupon, descuento, aviso, impuesto)
