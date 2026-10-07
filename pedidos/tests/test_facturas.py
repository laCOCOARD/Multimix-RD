from io import BytesIO
from unittest.mock import patch

import qrcode
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from catalogo.tests.test_modelos import crear_producto
from pedidos import factura
from pedidos.tests.utiles import pedido_de_prueba


class FacturaTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara de mesa', stock_almacen=10)
        self.pedido = pedido_de_prueba(
            self.producto,
            nombre='Cliente privado',
            telefono='8095551234',
        )

    def test_confirmacion_muestra_el_boton_factura(self):
        respuesta = self.client.get(reverse('pedidos:confirmacion', args=[self.pedido.token]))

        self.assertContains(respuesta, 'Factura')
        self.assertContains(
            respuesta,
            reverse('pedidos:factura', args=[self.pedido.token]),
        )

    def test_factura_devuelve_una_imagen_png_no_cacheable(self):
        respuesta = self.client.get(reverse('pedidos:factura', args=[self.pedido.token]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'image/png')
        self.assertTrue(respuesta['Content-Disposition'].startswith('inline;'))
        self.assertIn('no-store', respuesta['Cache-Control'])
        self.assertEqual(respuesta.content[:8], b'\x89PNG\r\n\x1a\n')
        imagen = Image.open(BytesIO(respuesta.content))
        self.assertGreater(imagen.width, 0)
        self.assertGreater(imagen.height, imagen.width)

    def test_sin_fuentes_del_sistema_escribe_sin_tildes(self):
        # La fuente incluida en Pillow no trae tildes: en vez de recuadros, el texto sale sin ellas.
        self.assertEqual(factura.sin_tildes('2 × Cupón ñandú'), '2 x Cupon nandu')
        escritos = []
        with patch.object(factura, 'FUENTES', []), \
                patch('PIL.ImageDraw.ImageDraw.text', lambda dibujo, xy, texto, **opciones: escritos.append(texto)):
            factura.generar_imagen_factura(self.pedido, 'Rincón Fitness', 'https://ejemplo.test/verificar/')
        self.assertIn('Rincon Fitness', escritos)
        self.assertNotIn('Rincón Fitness', escritos)
        self.assertTrue(all(texto == factura.sin_tildes(texto) for texto in escritos))

    def test_qr_es_unico_y_apunta_a_verificacion_publica(self):
        otro_pedido = pedido_de_prueba(
            self.producto,
            cantidad=1,
            nombre='Otra persona',
            telefono='8095551235',
        )
        urls_qr = []
        agregar_datos = qrcode.QRCode.add_data

        def capturar_url(codigo, datos, *args, **kwargs):
            urls_qr.append(datos)
            return agregar_datos(codigo, datos, *args, **kwargs)

        with patch.object(qrcode.QRCode, 'add_data', new=capturar_url):
            for pedido in (self.pedido, otro_pedido):
                self.client.get(reverse('pedidos:factura', args=[pedido.token]))

        self.assertEqual(len(urls_qr), 2)
        self.assertNotEqual(urls_qr[0], urls_qr[1])
        self.assertIn(reverse('pedidos:verificar_factura', args=[self.pedido.token]), urls_qr[0])
        self.assertIn(reverse('pedidos:verificar_factura', args=[otro_pedido.token]), urls_qr[1])

    def test_verificacion_no_expone_datos_personales(self):
        respuesta = self.client.get(reverse('pedidos:verificar_factura', args=[self.pedido.token]))

        self.assertContains(respuesta, self.pedido.numero)
        self.assertContains(respuesta, 'Pedido verificado')
        self.assertContains(respuesta, 'no acredita que el pago haya sido recibido')
        self.assertNotContains(respuesta, 'Cliente privado')
        self.assertNotContains(respuesta, '8095551234')
