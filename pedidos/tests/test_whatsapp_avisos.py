"""Avisos del estado del pedido por WhatsApp: a mano desde el panel y automaticos con la API de Meta."""
import json
from decimal import Decimal
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto
from pedidos import whatsapp_api
from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from tiendas.tests.utiles import entrar_como_cliente, ruta

from .utiles import pedido_de_prueba

CONECTADO = {'WHATSAPP_TOKEN': 'token-de-prueba', 'WHATSAPP_NUMERO_ID': '123456'}


class RespuestaDeMeta:
    def __enter__(self):
        return self

    def __exit__(self, *datos):
        return False

    def read(self):
        return b'{"messages": [{"id": "wamid.1"}]}'


class AvisoAManoTests(TestCase):
    def test_el_panel_ofrece_el_mensaje_del_estado_ya_escrito(self):
        producto = crear_producto(precio=Decimal('500'))
        pedido = pedido_de_prueba(producto, 1, nombre='Ana Pérez', telefono='8095551234')
        cambiar_estado(pedido, Pedido.Estado.PAGADO)
        admin = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'clave-segura-123')
        self.client.force_login(admin)
        pagina = self.client.get(reverse('admin:pedidos_pedido_change', args=[pedido.pk]))
        enlace = pagina.context['aviso_whatsapp']
        self.assertTrue(enlace.startswith('https://wa.me/18095551234?text='))
        texto = parse_qs(urlparse(enlace).query)['text'][0]
        self.assertIn('confirmamos el pago de tu pedido', texto)
        self.assertIn(pedido.get_absolute_url(), texto)
        self.assertContains(pagina, 'Avisar al cliente por WhatsApp')


class AvisoAutomaticoTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('500'), controla_stock=False)
        entrar_como_cliente(self.client)

    def comprar(self, **extra):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        self.client.post(ruta('pedidos:checkout'), {
            'nombre': 'Ana Pérez', 'telefono': '8095551234', 'metodo_entrega': 'recoger',
            'metodo_pago': 'efectivo_recoger', 'acepta_terminos': 'on', **extra,
        })
        return Pedido.objects.latest('id')

    def test_apagado_sin_configurar(self):
        self.assertNotContains(self.client.get(ruta('carrito:detalle')), 'avisos_whatsapp')
        with mock.patch('pedidos.whatsapp_api.urllib.request.urlopen') as urlopen:
            pedido = self.comprar(avisos_whatsapp='on')
        self.assertFalse(pedido.avisos_whatsapp)
        urlopen.assert_not_called()

    @override_settings(**CONECTADO)
    def test_solo_a_quien_lo_acepto_y_con_la_plantilla(self):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        self.assertContains(self.client.get(ruta('pedidos:checkout')), 'name="avisos_whatsapp"')

        with mock.patch('pedidos.whatsapp_api.urllib.request.urlopen', return_value=RespuestaDeMeta()) as urlopen:
            with self.captureOnCommitCallbacks(execute=True):
                sin_aceptar = self.comprar()
            urlopen.assert_not_called()

            with self.captureOnCommitCallbacks(execute=True):
                pedido = self.comprar(avisos_whatsapp='on')
            self.assertTrue(pedido.avisos_whatsapp)
            self.assertEqual(urlopen.call_count, 1)

            with self.captureOnCommitCallbacks(execute=True):
                cambiar_estado(pedido, Pedido.Estado.LISTO)
            self.assertEqual(urlopen.call_count, 2)

        self.assertFalse(sin_aceptar.avisos_whatsapp)
        peticion = urlopen.call_args.args[0]
        self.assertEqual(peticion.full_url, 'https://graph.facebook.com/v21.0/123456/messages')
        self.assertEqual(peticion.get_header('Authorization'), 'Bearer token-de-prueba')
        cuerpo = json.loads(peticion.data)
        self.assertEqual(cuerpo['to'], '18095551234')
        self.assertEqual(cuerpo['template']['name'], 'estado_pedido')
        textos = [parametro['text'] for parametro in cuerpo['template']['components'][0]['parameters']]
        self.assertEqual(textos[:3], ['Ana', pedido.numero, 'listo para recoger'])
        self.assertTrue(textos[3].endswith(pedido.get_absolute_url()))

    @override_settings(**CONECTADO)
    def test_si_meta_falla_el_pedido_sigue(self):
        with mock.patch('pedidos.whatsapp_api.urllib.request.urlopen', side_effect=OSError('sin red')):
            with self.captureOnCommitCallbacks(execute=True):
                pedido = self.comprar(avisos_whatsapp='on')
            self.assertFalse(whatsapp_api.enviar_estado(pedido))
        self.assertEqual(pedido.estado, Pedido.Estado.PENDIENTE)
