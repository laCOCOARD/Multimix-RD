from django.test import RequestFactory, SimpleTestCase, override_settings

from core.red import ip_del_cliente


class IpDelClienteTests(SimpleTestCase):
    @override_settings(CONFIAR_IP_PROXY=True, CABECERA_IP='HTTP_CF_CONNECTING_IP')
    def test_lee_la_cabecera_del_proxy(self):
        request = RequestFactory().get('/', HTTP_CF_CONNECTING_IP='198.51.100.7', REMOTE_ADDR='10.0.0.2')
        self.assertEqual(ip_del_cliente(request), '198.51.100.7')

    @override_settings(CONFIAR_IP_PROXY=True, CABECERA_IP='HTTP_CF_CONNECTING_IP')
    def test_no_cree_lo_que_el_visitante_escribe_en_x_forwarded_for_ni_en_x_real_ip(self):
        request = RequestFactory().get(
            '/', HTTP_X_FORWARDED_FOR='203.0.113.99, 198.51.100.7', HTTP_X_REAL_IP='203.0.113.98',
            HTTP_CF_CONNECTING_IP='198.51.100.7', REMOTE_ADDR='10.0.0.2',
        )
        self.assertEqual(ip_del_cliente(request), '198.51.100.7')

    @override_settings(CONFIAR_IP_PROXY=True, CABECERA_IP='HTTP_CF_CONNECTING_IP')
    def test_sin_la_cabecera_no_agrupa_a_todos_por_la_ip_del_proxy(self):
        request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='203.0.113.99', REMOTE_ADDR='10.0.0.2')
        self.assertIsNone(ip_del_cliente(request))

    @override_settings(CONFIAR_IP_PROXY=False)
    def test_sin_proxy_usa_la_conexion(self):
        request = RequestFactory().get('/', HTTP_CF_CONNECTING_IP='198.51.100.7', REMOTE_ADDR='192.0.2.5')
        self.assertEqual(ip_del_cliente(request), '192.0.2.5')
