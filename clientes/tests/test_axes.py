"""django-axes (pedido del dueño el 2026-11-02): 5 intentos fallidos con el mismo usuario desde la misma conexion
bloquean 1 hora la entrada, en las cuentas del sitio y en el panel. El limite propio del sitio (15 minutos) se apaga
aqui para probar solo el de axes."""
from unittest import mock

from axes.models import AccessAttempt
from axes.utils import reset
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

CLAVE = 'clave-segura-123'


@override_settings(AXES_ENABLED=True)
@mock.patch('clientes.services.entrada_bloqueada', return_value=False)
class LimiteDeIntentosTests(TestCase):
    def setUp(self):
        reset()
        Usuario = get_user_model()
        Usuario.objects.create_user('ana@example.com', 'ana@example.com', CLAVE)
        Usuario.objects.create_superuser('admin', 'admin@example.com', CLAVE)

    def entrar(self, url, usuario, clave):
        return self.client.post(url, {'username': usuario, 'password': clave})

    def test_cinco_fallos_bloquean_la_cuenta_del_sitio(self, _limite_del_sitio):
        url = reverse('clientes:entrar')
        for _ in range(4):
            self.assertEqual(self.entrar(url, 'ana@example.com', 'mala').status_code, 200)
        # El quinto fallo ya bloquea, y despues ni la contraseña correcta entra.
        self.assertEqual(self.entrar(url, 'ana@example.com', 'mala').status_code, 429)
        bloqueado = self.entrar(url, 'ana@example.com', CLAVE)
        self.assertEqual(bloqueado.status_code, 429)
        self.assertContains(bloqueado, 'Demasiados intentos', status_code=429)
        self.assertNotIn('_auth_user_id', self.client.session)
        # Cuenta tambien el intento hecho ya bloqueado.
        self.assertGreaterEqual(AccessAttempt.objects.get(username='ana@example.com').failures_since_start, 5)

    def test_cuatro_fallos_no_bloquean_y_entrar_bien_borra_la_cuenta(self, _limite_del_sitio):
        url = reverse('clientes:entrar')
        for _ in range(4):
            self.entrar(url, 'ana@example.com', 'mala')
        respuesta = self.entrar(url, 'ana@example.com', CLAVE)
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(AccessAttempt.objects.filter(username='ana@example.com').exists())

    def test_el_panel_tambien_se_bloquea(self, _limite_del_sitio):
        url = reverse('admin:login')
        for _ in range(5):
            self.entrar(url, 'admin', 'mala')
        self.assertEqual(self.entrar(url, 'admin', CLAVE).status_code, 429)
