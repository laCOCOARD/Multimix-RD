"""El arranque deja listo al administrador sin cerrar su sesion en cada despliegue (pedido del dueño el 2026-11-05)."""
import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

VARIABLES = {
    'DJANGO_SUPERUSER_USERNAME': 'MULTIMIX_ADMIN',
    'DJANGO_SUPERUSER_EMAIL': 'contacto@sitio.example',
    'DJANGO_SUPERUSER_PASSWORD': 'clave-segura-123',
}


def correr(**cambios):
    salida = StringIO()
    with patch.dict(os.environ, {**VARIABLES, **cambios}):
        call_command('asegurar_superusuario', stdout=salida)
    return salida.getvalue()


class AsegurarSuperusuarioTests(TestCase):
    def test_lo_crea_y_despues_no_cierra_su_sesion(self):
        self.assertIn('creado', correr())
        admin = get_user_model().objects.get(username='MULTIMIX_ADMIN')
        self.assertTrue(admin.is_superuser and admin.is_staff and admin.check_password('clave-segura-123'))
        self.client.force_login(admin)
        panel = self.client.get('/panel/')
        self.assertEqual(panel.status_code, 200)

        # Otro despliegue con la misma clave: la sesion sigue abierta.
        self.assertIn('no cambio', correr())
        self.assertEqual(self.client.get('/panel/').status_code, 200)

        # Con otra clave si cambia (y la sesion vieja se cierra, como debe ser).
        self.assertIn('contraseña cambiada', correr(DJANGO_SUPERUSER_PASSWORD='otra-clave-456'))
        self.assertEqual(self.client.get('/panel/').status_code, 302)

    def test_pone_el_correo_de_la_variable(self):
        correr()
        correr(DJANGO_SUPERUSER_EMAIL='nuevo@sitio.example')
        self.assertEqual(get_user_model().objects.get(username='MULTIMIX_ADMIN').email, 'nuevo@sitio.example')

    def test_sin_variables_avisa(self):
        with self.assertRaises(CommandError):
            correr(DJANGO_SUPERUSER_PASSWORD='')
