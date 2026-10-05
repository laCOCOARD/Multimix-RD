from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from pedidos.views import _ip_cliente


class IpClienteRenderTests(SimpleTestCase):
    @override_settings(CONFIAR_IP_PROXY=True)
    def test_usa_la_ip_cliente_de_x_forwarded_for_en_render(self):
        request = RequestFactory().get(
            '/',
            HTTP_X_FORWARDED_FOR='198.51.100.7, 10.0.0.2',
            REMOTE_ADDR='10.0.0.2',
        )
        with patch.dict('os.environ', {'RENDER_EXTERNAL_HOSTNAME': 'tienda.onrender.com'}):
            self.assertEqual(_ip_cliente(request), '198.51.100.7')

    @override_settings(CONFIAR_IP_PROXY=True)
    def test_no_agrupa_usuarios_por_ip_del_proxy_render(self):
        request = RequestFactory().get('/', REMOTE_ADDR='10.0.0.2')
        with patch.dict('os.environ', {'RENDER_EXTERNAL_HOSTNAME': 'tienda.onrender.com'}):
            self.assertIsNone(_ip_cliente(request))
