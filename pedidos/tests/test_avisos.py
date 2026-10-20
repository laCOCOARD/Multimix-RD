import io
import json
import urllib.error
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import EmailMessage
from django.test import TestCase, override_settings

from catalogo.tests.test_modelos import crear_producto
from core.models import ConfiguracionTienda
from pagos import services as pagos
from pedidos import avisos
from pedidos.models import Pedido
from pedidos.services import cambiar_estado, eliminar_pedido
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba

from .utiles import comprobante_de_prueba, pedido_de_prueba


@override_settings(SITIO_URL='https://multimix.example')
class AvisosPorCorreoTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.tienda.correo = 'ventas@tienda.example'
        self.tienda.save()
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))

    def pedido(self, **cambios):
        """Crea el pedido y deja salir los correos, como cuando la base confirma la operacion."""
        with self.captureOnCommitCallbacks(execute=True):
            pedido = pedido_de_prueba(self.producto, 2, **cambios)
        return pedido

    def test_pedido_nuevo_avisa_a_la_tienda_y_al_cliente(self):
        pedido = self.pedido()
        a_la_tienda, al_cliente = mail.outbox
        self.assertEqual((a_la_tienda.to, a_la_tienda.subject), (['ventas@tienda.example'], f'Nuevo pedido {pedido.numero}'))
        self.assertIn('2 x Lámpara: RD$ 2,000.00', a_la_tienda.body)
        self.assertIn('Ana Pérez · 809-555-1234', a_la_tienda.body)
        self.assertIn(f'https://multimix.example/panel/pedidos/pedido/{pedido.pk}/change/', a_la_tienda.body)

        self.assertEqual((al_cliente.to, al_cliente.subject), (['ana@example.com'], f'Recibimos tu pedido {pedido.numero}'))
        self.assertIn(f'https://multimix.example/pedido/{pedido.token}/', al_cliente.body)
        self.assertIn('Total: RD$ 2,000.00', al_cliente.body)
        # El enlace del panel es solo para la tienda.
        self.assertNotIn('/panel/', al_cliente.body)

    def test_sin_correo_del_cliente_solo_se_avisa_a_la_tienda(self):
        self.pedido(correo='')
        self.assertEqual([correo.to for correo in mail.outbox], [['ventas@tienda.example']])

    def test_a_quien_se_avisa_en_la_tienda(self):
        self.assertEqual(avisos.correos_de_la_tienda(self.tienda), ['ventas@tienda.example'])
        self.tienda.correo = ''
        Usuario = get_user_model()
        Usuario.objects.create_superuser('admin', 'admin@sitio.example', 'clave-segura-123')
        self.assertEqual(avisos.correos_de_la_tienda(self.tienda), ['admin@sitio.example'])
        configuracion = ConfiguracionTienda.obtener()
        configuracion.correo = 'hola@sitio.example'
        configuracion.save()
        self.assertEqual(avisos.correos_de_la_tienda(self.tienda), ['hola@sitio.example'])
        self.tienda.usuarios.add(Usuario.objects.create_user('vendedor', 'vendedor@tienda.example'))
        self.assertEqual(avisos.correos_de_la_tienda(self.tienda), ['vendedor@tienda.example'])

    def test_cada_cambio_de_estado_le_llega_al_cliente(self):
        pedido = self.pedido(metodo_entrega=Pedido.Entrega.RECOGER)
        mail.outbox.clear()
        for estado, texto in (('pagado', 'Confirmamos el pago'), ('listo', 'listo para recoger'), ('entregado', 'fue entregado')):
            with self.captureOnCommitCallbacks(execute=True):
                cambiar_estado(pedido, estado)
            correo = [correo for correo in mail.outbox if correo.to == ['ana@example.com']][-1]
            self.assertIn(texto, correo.body)
        # Tres al cliente y, al confirmarse la transferencia, uno a la tienda para que prepare el pedido.
        self.assertEqual([correo.to for correo in mail.outbox].count(['ventas@tienda.example']), 1)
        self.assertEqual(len(mail.outbox), 4)

    def test_comprobante_avisa_al_sitio_y_rechazo_al_cliente(self):
        configuracion = ConfiguracionTienda.obtener()
        configuracion.correo = 'hola@sitio.example'
        configuracion.save()
        pedido = self.pedido()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            pago = pagos.registrar_comprobante(pedido, comprobante_de_prueba(), 'REF-77')
        correo = mail.outbox[-1]
        # La transferencia llego a las cuentas del sitio: el aviso es para el dueño, no para la tienda.
        self.assertEqual(correo.to, ['hola@sitio.example'])
        self.assertIn('Referencia: REF-77', correo.body)
        self.assertIn(f'/panel/pagos/pago/{pago.pk}/change/', correo.body)

        with self.captureOnCommitCallbacks(execute=True):
            pagos.rechazar_pago(pago, nota='No aparece en el banco')
        correo = mail.outbox[-1]
        self.assertEqual(correo.to, ['ana@example.com'])
        self.assertIn('Motivo: No aparece en el banco', correo.body)

    def test_si_el_correo_falla_la_compra_sigue(self):
        entrar_como_cliente(self.client, 'ana@example.com')
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        with mock.patch('core.correo.send_mail', side_effect=OSError('sin conexion')):
            with self.captureOnCommitCallbacks(execute=True):
                respuesta = self.client.post(ruta('pedidos:checkout'), {
                    'nombre': 'Ana Pérez', 'telefono': '8095551234',
                    'metodo_entrega': 'recoger', 'metodo_pago': 'transferencia', 'acepta_terminos': 'on',
                })
        pedido = Pedido.objects.get()
        self.assertRedirects(respuesta, pedido.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(mail.outbox, [])

    def test_los_datos_del_cliente_no_se_interpretan_como_plantilla_ni_html(self):
        self.pedido(nombre='Ana <b>{{ pedido.token }}</b>', notas='{% load x %}')
        cuerpo = mail.outbox[0].body
        self.assertIn('Ana <b>{{ pedido.token }}</b>', cuerpo)
        self.assertIn('{% load x %}', cuerpo)

    def test_el_administrador_prueba_el_correo_desde_el_panel(self):
        Usuario = get_user_model()
        self.client.force_login(Usuario.objects.create_superuser('admin', 'admin@sitio.example', 'clave-segura-123'))
        url = '/panel/core/configuraciontienda/correo-de-prueba/'
        self.client.post(url)
        self.assertEqual(mail.outbox, [])  # sin servidor de correo no se intenta
        with override_settings(CORREO_CONFIGURADO=True):
            self.client.post(url)
            self.assertEqual(mail.outbox[-1].to, ['admin@sitio.example'])
            with mock.patch('core.admin.send_mail', side_effect=OSError('clave incorrecta')):
                respuesta = self.client.post(url, follow=True)
            self.assertContains(respuesta, 'No se pudo enviar: OSError: clave incorrecta')
        self.assertEqual(self.client.get(url).status_code, 405)

        self.client.force_login(Usuario.objects.create_user('vendedor', is_staff=True))
        self.assertEqual(self.client.post(url).status_code, 403)

    @override_settings(BREVO_API_KEY='clave-de-prueba', DEFAULT_FROM_EMAIL='Multimix RD <ventas@sitio.example>')
    def test_envio_por_la_api_de_brevo(self):
        from core.correo_brevo import URL_DE_ENVIO, BrevoBackend

        mensaje = EmailMessage('Nuevo pedido', 'Entró un pedido.', None, ['tienda@example.com'])
        with mock.patch('core.correo_brevo.urllib.request.urlopen') as abrir:
            abrir.return_value.__enter__.return_value.read.return_value = b'{"messageId": "<abc@smtp-relay>"}'
            with self.assertLogs('multimix.correo', 'INFO') as registro:
                self.assertEqual(BrevoBackend().send_messages([mensaje]), 1)
        # Queda el numero de Brevo para buscar el correo en su panel si no llega.
        self.assertIn('<abc@smtp-relay>', registro.output[0])
        peticion = abrir.call_args.args[0]
        self.assertEqual((peticion.full_url, peticion.get_method()), (URL_DE_ENVIO, 'POST'))
        self.assertEqual(peticion.get_header('Api-key'), 'clave-de-prueba')
        self.assertEqual(json.loads(peticion.data), {
            'sender': {'email': 'ventas@sitio.example', 'name': 'Multimix RD'},
            'to': [{'email': 'tienda@example.com'}], 'subject': 'Nuevo pedido', 'textContent': 'Entró un pedido.',
        })

        rechazo = urllib.error.HTTPError(URL_DE_ENVIO, 401, 'Unauthorized', None, io.BytesIO(b'{"message":"Key not found"}'))
        with mock.patch('core.correo_brevo.urllib.request.urlopen', side_effect=rechazo):
            with self.assertRaisesMessage(OSError, 'Brevo respondió 401: {"message":"Key not found"}'):
                BrevoBackend().send_messages([mensaje])
            self.assertEqual(BrevoBackend(fail_silently=True).send_messages([mensaje]), 0)

    def test_eliminar_un_pedido_no_manda_correo_de_cancelacion(self):
        pedido = self.pedido()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            eliminar_pedido(pedido)
        self.assertEqual(mail.outbox, [])
