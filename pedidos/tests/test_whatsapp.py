from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.test import TestCase

from catalogo.tests.test_modelos import crear_producto
from pedidos.models import Pedido
from pedidos.services import crear_pedido
from pedidos.whatsapp import construir_enlace, construir_mensaje, enlace_al_cliente, enlace_del_pedido
from promociones.models import Cupon

from .utiles import carrito_con, datos_pedido, zona_de_prueba


class MensajeWhatsAppTests(TestCase):
    def setUp(self):
        self.lampara = crear_producto(nombre='Lámpara LED', sku='L1', precio=Decimal('1000'))
        self.taza = crear_producto(nombre='Taza & plato', sku='T1', precio=Decimal('250.50'))

    def test_pedido_con_envio_cupon_y_transferencia(self):
        Cupon.objects.create(codigo='BIENVENIDO10', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('10'))
        pedido = crear_pedido(
            carrito_con((self.lampara, 2), (self.taza, 1), cupon='BIENVENIDO10'),
            datos_pedido(
                metodo_entrega=Pedido.Entrega.ENVIO, zona=zona_de_prueba('Santiago', '350'),
                direccion='Calle El Sol #12', referencia='Frente al parque',
                transferencia_realizada=True, referencia_transferencia='TRX-778', notas='Llamar antes de llegar',
            ),
        )
        mensaje = construir_mensaje(pedido)
        esperado = [
            f'*Nuevo pedido {pedido.numero}*',
            '*Cliente:* Ana Pérez',
            '*Teléfono:* 809-555-1234',
            '*Correo:* ana@example.com',
            '• 2 × Lámpara LED = RD$ 2,000.00',
            '• 1 × Taza & plato = RD$ 250.50',
            '*Subtotal:* RD$ 2,250.50',
            '*Cupón BIENVENIDO10:* -RD$ 225.05',
            '*Envío (Santiago):* RD$ 350.00',
            '*Total:* RD$ 2,375.45',
            '*Forma de pago:* Transferencia bancaria',
            '✅ Ya hice la transferencia (Ref.: TRX-778)',
            '*Dirección:* Calle El Sol #12',
            '*Referencia:* Frente al parque',
            '*Notas:* Llamar antes de llegar',
        ]
        lineas = mensaje.split('\n')
        posiciones = [lineas.index(linea) for linea in esperado]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_pedido_para_recoger_en_efectivo(self):
        pedido = crear_pedido(
            carrito_con((self.lampara, 1)),
            datos_pedido(metodo_pago=Pedido.Pago.EFECTIVO_RECOGER, correo=''),
        )
        mensaje = construir_mensaje(pedido)
        self.assertIn('*Entrega:* Recoger en tienda', mensaje)
        self.assertIn('*Forma de pago:* Efectivo al recoger', mensaje)
        self.assertIn('*Total:* RD$ 1,000.00', mensaje)
        for ausente in ('Cupón', 'Envío', 'Dirección', 'Referencia', 'Notas', 'Correo', 'transferencia'):
            self.assertNotIn(ausente, mensaje)

    def test_transferencia_sin_aviso_no_dice_que_pago(self):
        pedido = crear_pedido(carrito_con((self.lampara, 1)), datos_pedido())
        self.assertNotIn('Ya hice la transferencia', construir_mensaje(pedido))

    def test_enlace_codifica_el_mensaje(self):
        enlace = construir_enlace('1 (809) 555-0000', 'Hola & adiós\n¿50% = RD$ 1,250.00?')
        self.assertTrue(enlace.startswith('https://wa.me/18095550000?text='))
        codificado = enlace.split('?text=')[1]
        for caracter in (' ', '&', '\n', '?', '#', '='):
            self.assertNotIn(caracter, codificado)
        self.assertEqual(parse_qs(urlparse(enlace).query)['text'], ['Hola & adiós\n¿50% = RD$ 1,250.00?'])

    def test_enlace_del_pedido_lleva_el_mensaje_completo(self):
        pedido = crear_pedido(carrito_con((self.taza, 2)), datos_pedido())
        enlace = enlace_del_pedido(pedido, '18095550000')
        self.assertEqual(parse_qs(urlparse(enlace).query)['text'], [construir_mensaje(pedido)])

    def test_enlace_al_cliente_usa_codigo_de_pais(self):
        pedido = crear_pedido(carrito_con((self.taza, 1)), datos_pedido())
        self.assertTrue(enlace_al_cliente(pedido).startswith('https://wa.me/18095551234?text='))
