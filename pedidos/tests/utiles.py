from decimal import Decimal
from types import SimpleNamespace

from django.contrib.sessions.backends.signed_cookies import SessionStore

from carrito.carrito import Carrito
from pedidos.models import Pedido, ZonaEnvio
from pedidos.services import crear_pedido
from promociones.models import Cupon
from tiendas.tests.utiles import tienda_de_prueba


def carrito_con(*lineas, cupon='', tienda=None):
    """Carrito en una sesion de prueba. `lineas` son tuplas (producto, cantidad) de una misma tienda."""
    tienda = tienda or (lineas[0][0].tienda if lineas else tienda_de_prueba())
    carrito = Carrito(SimpleNamespace(session=SessionStore()), tienda)
    for producto, cantidad in lineas:
        carrito.agregar(producto, cantidad)
    if cupon:
        carrito.aplicar_cupon(cupon)
    return carrito


def datos_pedido(**cambios):
    datos = {
        'nombre': 'Ana Pérez',
        'telefono': '8095551234',
        'correo': 'ana@example.com',
        'metodo_entrega': Pedido.Entrega.RECOGER,
        'zona': None,
        'direccion': '',
        'referencia': '',
        'metodo_pago': Pedido.Pago.TRANSFERENCIA,
        'transferencia_realizada': False,
        'referencia_transferencia': '',
        'notas': '',
    }
    datos.update(cambios)
    return datos


def zona_de_prueba(nombre='Santo Domingo', tarifa='250.00', tienda=None):
    return ZonaEnvio.objects.get_or_create(
        tienda=tienda or tienda_de_prueba(), nombre=nombre, defaults={'tarifa': Decimal(tarifa)},
    )[0]


def cupon_de_prueba(codigo='DIEZ', tienda=None, **datos):
    """Cupon de la tienda; por defecto 10 % de descuento."""
    valores = {'tipo': Cupon.Tipo.PORCENTAJE, 'valor': Decimal('10')}
    valores.update(datos)
    return Cupon.objects.create(tienda=tienda or tienda_de_prueba(), codigo=codigo, **valores)


def pedido_de_prueba(producto, cantidad=2, cupon='', **cambios):
    return crear_pedido(carrito_con((producto, cantidad), cupon=cupon), datos_pedido(**cambios))
