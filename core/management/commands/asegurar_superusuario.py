"""Crea o pone al dia el administrador principal con DJANGO_SUPERUSER_USERNAME, _EMAIL y _PASSWORD (lo corre el
arranque en Render). La contraseña solo se cambia si es otra: cambiarla cierra la sesion abierta del administrador, y
antes eso pasaba en cada despliegue (pedido del dueño el 2026-11-05)."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crea o actualiza el superusuario con las variables DJANGO_SUPERUSER_* sin cerrar su sesion.'

    def handle(self, *args, **opciones):
        nombre = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        clave = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        if not nombre or not clave:
            raise CommandError('Faltan DJANGO_SUPERUSER_USERNAME o DJANGO_SUPERUSER_PASSWORD.')
        usuario, creado = get_user_model().objects.get_or_create(username=nombre)
        usuario.email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        usuario.is_staff = usuario.is_superuser = usuario.is_active = True
        cambio_la_clave = creado or not usuario.check_password(clave)
        if cambio_la_clave:
            usuario.set_password(clave)
        usuario.save()
        if creado:
            mensaje = 'Administrador creado.'
        elif cambio_la_clave:
            mensaje = 'Administrador al dia; contraseña cambiada.'
        else:
            mensaje = 'Administrador al dia; la contraseña no cambio.'
        self.stdout.write(mensaje)
