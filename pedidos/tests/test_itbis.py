from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Producto
from catalogo.tests.test_modelos import crear_producto
from core.impuestos import calcular_itbis
from pedidos.models import Pedido
from pedidos.services import calcular_totales, crear_pedido
from pedidos.whatsapp import construir_mensaje
from tiendas.models import Tienda
from tiendas.tests.utiles import ruta, tienda_de_prueba

from .utiles import carrito_con, cupon_de_prueba, datos_pedido, zona_de_prueba

D = Decimal


class CalculoDeItbisTests(TestCase):
    def test_sobre_los_productos_gravados(self):
        self.assertEqual(calcular_itbis([(D('1000'), False), (D('500'), False)], D('0'), D('18')), D('270.00'))
        self.assertEqual(calcular_itbis([(D('1000'), False), (D('500'), True)], D('0'), D('18')), D('180.00'))

    def test_el_descuento_baja_la_base_en_proporcion(self):
        # 150 de descuento sobre 1,500: 100 tocan al producto gravado y 50 al exento.
        self.assertEqual(calcular_itbis([(D('1000'), False), (D('500'), True)], D('150'), D('18')), D('162.00'))
        self.assertEqual(calcular_itbis([(D('1000'), False)], D('1000'), D('18')), D('0.00'))

    def test_sin_porcentaje_o_todo_exento_no_hay_impuesto(self):
        self.assertEqual(calcular_itbis([(D('1000'), False)], D('0'), D('0')), D('0.00'))
        self.assertEqual(calcular_itbis([(D('1000'), True)], D('0'), D('18')), D('0.00'))
        self.assertEqual(calcular_itbis([], D('0'), D('18')), D('0.00'))

    def test_redondea_al_centavo(self):
        self.assertEqual(calcular_itbis([(D('99.99'), False)], D('0'), D('18')), D('18.00'))
        self.assertEqual(calcular_itbis([(D('33.33'), False)], D('0'), D('18')), D('6.00'))

    def test_una_tienda_nueva_no_cobra_itbis(self):
        self.assertEqual(Tienda.objects.create(nombre='Nueva').itbis_porcentaje, D('0.00'))


class PedidoConItbisTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba(itbis_porcentaje=D('18'))
        self.gravado = crear_producto(nombre='Lámpara', sku='G', precio=D('1000'))
        self.exento = crear_producto(nombre='Libro', sku='E', precio=D('500'), exento_itbis=True)

    def test_el_carrito_y_el_checkout_muestran_el_impuesto(self):
        carrito = carrito_con((self.gravado, 2), (self.exento, 1))
        resumen = carrito.resumen()
        self.assertEqual((resumen.subtotal, resumen.impuesto, resumen.total), (D('2500'), D('360.00'), D('2860.00')))
        totales = calcular_totales(carrito, Pedido.Entrega.ENVIO, zona_de_prueba())
        self.assertEqual((totales.impuesto, totales.costo_envio, totales.total), (D('360.00'), D('250.00'), D('3110.00')))

    def test_el_pedido_guarda_el_impuesto_y_el_envio_no_lo_paga(self):
        cupon_de_prueba('DIEZ')
        carrito = carrito_con((self.gravado, 2), (self.exento, 1), cupon='DIEZ')
        pedido = crear_pedido(carrito, datos_pedido(
            metodo_entrega=Pedido.Entrega.ENVIO, zona=zona_de_prueba(), sector='Naco', direccion='Calle 1',
        ))
        # 2,500 - 250 de cupon; base gravada 2,000 - 200 = 1,800; ITBIS 324; envio 250.
        self.assertEqual(
            (pedido.subtotal, pedido.descuento, pedido.impuesto, pedido.porcentaje_impuesto, pedido.costo_envio),
            (D('2500.00'), D('250.00'), D('324.00'), D('18.00'), D('250.00')),
        )
        self.assertEqual(pedido.total, D('2824.00'))
        self.assertIn('*ITBIS (18%):* RD$ 324.00', construir_mensaje(pedido))
        self.assertIn('*Dirección:* Calle 1, Naco', construir_mensaje(pedido))

    def test_el_impuesto_se_calcula_en_el_servidor(self):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.gravado.pk, 'cantidad': 1})
        respuesta = self.client.get(ruta('pedidos:checkout'))
        self.assertContains(respuesta, 'ITBIS (18%)')
        self.assertContains(respuesta, 'RD$ 1,180.00')
        self.client.post(ruta('pedidos:checkout'), {
            'nombre': 'Ana Pérez', 'telefono': '8095551234', 'metodo_entrega': 'recoger',
            'metodo_pago': 'transferencia', 'acepta_terminos': 'on', 'impuesto': '0', 'total': '1',
        })
        pedido = Pedido.objects.get()
        self.assertEqual((pedido.impuesto, pedido.total), (D('180.00'), D('1180.00')))
        pagina = self.client.get(pedido.get_absolute_url())
        self.assertContains(pagina, 'ITBIS (18%)')
        self.assertContains(pagina, 'RD$ 180.00')
        self.assertEqual(self.client.get(reverse('pedidos:factura', args=[pedido.token])).status_code, 200)

    def test_el_resumen_en_vivo_trae_el_impuesto(self):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.gravado.pk, 'cantidad': 1})
        datos = self.client.post(ruta('pedidos:totales'), {'metodo_entrega': 'recoger'}).json()
        self.assertEqual((datos['impuesto'], datos['hay_impuesto'], datos['total']), ('RD$ 180.00', True, 'RD$ 1,180.00'))
        carrito = self.client.post(
            ruta('carrito:actualizar'), {'producto_id': self.gravado.pk, 'cantidad': 2}, headers={'X-Requested-With': 'fetch'},
        ).json()
        self.assertEqual((carrito['impuesto'], carrito['total']), ('RD$ 360.00', 'RD$ 2,360.00'))

    def test_la_ficha_avisa_que_el_precio_no_trae_itbis(self):
        self.assertContains(self.client.get(self.gravado.get_absolute_url()), 'Precio sin ITBIS (18%)')
        self.assertNotContains(self.client.get(self.exento.get_absolute_url()), 'Precio sin ITBIS')

    def test_tienda_que_no_cobra_itbis(self):
        self.tienda.itbis_porcentaje = 0
        pedido = crear_pedido(carrito_con((self.gravado, 1), tienda=self.tienda), datos_pedido())
        self.assertEqual((pedido.impuesto, pedido.porcentaje_impuesto, pedido.total), (D('0.00'), D('0.00'), D('1000.00')))


class TerminosTests(TestCase):
    def test_sin_aceptar_los_terminos_no_hay_pedido(self):
        tienda_de_prueba()
        producto = crear_producto()
        self.client.post(ruta('carrito:agregar'), {'producto_id': producto.pk, 'cantidad': 1})
        respuesta = self.client.post(ruta('pedidos:checkout'), {
            'nombre': 'Ana Pérez', 'telefono': '8095551234', 'metodo_entrega': 'recoger', 'metodo_pago': 'transferencia',
        })
        self.assertIn('acepta_terminos', respuesta.context['formulario'].errors)
        self.assertFalse(Pedido.objects.exists())


class MarcasDeAmwayTests(TestCase):
    def test_marca_por_la_linea_del_nombre_sin_pisar_lo_que_ya_tiene_marca(self):
        crear_producto(sku='1', nombre='Vitamina E masticable Nutrilite')
        crear_producto(sku='2', nombre='Bálsamo labial Artistry Go Vibrant')
        crear_producto(sku='3', nombre='Loción rica para el cuerpo g&h Refresh')
        crear_producto(sku='4', nombre='Tubitos deportivos XS - Ponche de frutas')
        crear_producto(sku='5', nombre='Camiseta talla xs')
        crear_producto(sku='6', nombre='Lámpara de mesa')
        crear_producto(sku='7', nombre='Shampoo Satinique', marca='Otra')

        migracion = import_module('catalogo.migrations.0012_marcas_de_amway')
        migracion.marcar_lineas(apps, None)

        self.assertEqual(dict(Producto.objects.values_list('sku', 'marca')), {
            '1': 'Nutrilite', '2': 'Artistry', '3': 'g&h', '4': 'XS', '5': '', '6': '', '7': 'Otra',
        })
        respuesta = self.client.get(ruta('catalogo:lista'), {'marca': 'g&h'})
        self.assertEqual([p.sku for p in respuesta.context['pagina']], ['3'])
        self.assertEqual([p.sku for p in self.client.get(ruta('catalogo:lista'), {'q': 'nutrilite'}).context['pagina']], ['1'])
