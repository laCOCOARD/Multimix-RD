from decimal import Decimal
from types import SimpleNamespace

from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.test import TestCase

from carrito.carrito import Carrito, CarritoError, cantidad_en_sesion
from catalogo.models import Producto
from catalogo.tests.test_modelos import crear_producto
from promociones.models import Cupon
from promociones.services import CuponInvalido


class CarritoTests(TestCase):
    def setUp(self):
        self.request = SimpleNamespace(session=SessionStore())
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), stock_almacen=5)
        self.otro = crear_producto(nombre='Taza', precio=Decimal('250'), precio_oferta=Decimal('200'), stock_almacen=20)

    def carrito(self):
        return Carrito(self.request)

    def test_agregar_suma_y_persiste_en_sesion(self):
        carrito = self.carrito()
        carrito.agregar(self.producto, 1)
        carrito.agregar(self.producto, 2)
        carrito.agregar(self.otro, 1)
        nuevo = self.carrito()
        self.assertEqual(len(nuevo), 4)
        self.assertEqual(nuevo.cantidad_de(self.producto.pk), 3)
        self.assertEqual(cantidad_en_sesion(self.request.session), 4)

    def test_subtotal_usa_el_precio_de_oferta(self):
        carrito = self.carrito()
        carrito.agregar(self.producto, 2)
        carrito.agregar(self.otro, 3)
        self.assertEqual(carrito.subtotal, Decimal('2600.00'))

    def test_no_pasa_del_stock_disponible(self):
        carrito = self.carrito()
        cantidad, ajustada = carrito.agregar(self.producto, 9)
        self.assertEqual((cantidad, ajustada), (5, True))
        cantidad, ajustada = carrito.agregar(self.producto, 2, reemplazar=True)
        self.assertEqual((cantidad, ajustada), (2, False))

    def test_no_agrega_agotados_ni_inactivos(self):
        Producto.objects.filter(pk=self.producto.pk).update(stock_reservado=5)
        self.producto.refresh_from_db()
        with self.assertRaises(CarritoError):
            self.carrito().agregar(self.producto)
        self.otro.activo = False
        with self.assertRaises(CarritoError):
            self.carrito().agregar(self.otro)

    def test_eliminar_y_vaciar(self):
        carrito = self.carrito()
        carrito.agregar(self.producto)
        carrito.agregar(self.otro)
        carrito.eliminar(self.producto.pk)
        self.assertEqual([linea.producto for linea in carrito.lineas()], [self.otro])
        carrito.vaciar()
        self.assertFalse(self.carrito())

    def test_sincronizar_ajusta_cuando_cambia_el_stock(self):
        carrito = self.carrito()
        carrito.agregar(self.producto, 4)
        carrito.agregar(self.otro, 2)
        Producto.objects.filter(pk=self.producto.pk).update(stock_almacen=2)
        Producto.objects.filter(pk=self.otro.pk).update(stock_almacen=0)
        avisos = self.carrito().sincronizar()
        self.assertEqual(len(avisos), 2)
        carrito = self.carrito()
        self.assertEqual(carrito.cantidad_de(self.producto.pk), 2)
        self.assertEqual(carrito.cantidad_de(self.otro.pk), 0)
        self.assertEqual(self.carrito().sincronizar(), [])

    def test_sincronizar_quita_productos_desactivados(self):
        carrito = self.carrito()
        carrito.agregar(self.producto)
        Producto.objects.filter(pk=self.producto.pk).update(activo=False)
        self.assertEqual(len(self.carrito().sincronizar()), 1)
        self.assertFalse(self.carrito())

    def test_cupon_aplicar_y_quitar(self):
        Cupon.objects.create(codigo='DIEZ', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('10'))
        carrito = self.carrito()
        carrito.agregar(self.producto, 2)
        carrito.aplicar_cupon('diez')
        resumen = self.carrito().resumen()
        self.assertEqual(resumen.descuento, Decimal('200.00'))
        self.assertEqual(resumen.total, Decimal('1800.00'))
        carrito = self.carrito()
        carrito.quitar_cupon()
        self.assertEqual(self.carrito().resumen().descuento, Decimal('0.00'))

    def test_cupon_invalido_no_se_guarda(self):
        carrito = self.carrito()
        carrito.agregar(self.producto)
        with self.assertRaises(CuponInvalido):
            carrito.aplicar_cupon('NOEXISTE')
        self.assertEqual(self.carrito().codigo_cupon, '')

    def test_cupon_se_quita_si_deja_de_cumplir_el_minimo(self):
        Cupon.objects.create(codigo='MIN', tipo=Cupon.Tipo.MONTO_FIJO, valor=Decimal('100'), compra_minima=Decimal('2000'))
        carrito = self.carrito()
        carrito.agregar(self.producto, 2)
        carrito.aplicar_cupon('MIN')
        carrito.agregar(self.producto, 1, reemplazar=True)
        resumen = carrito.resumen()
        self.assertIsNone(resumen.cupon)
        self.assertIn('MIN', resumen.aviso_cupon)
        self.assertEqual(self.carrito().codigo_cupon, '')
