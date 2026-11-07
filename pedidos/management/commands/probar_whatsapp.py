"""Manda un aviso de prueba por WhatsApp para comprobar la conexion con Meta (docs/WHATSAPP.md)."""
from django.core.management.base import BaseCommand, CommandError

from core.correo import url_absoluta
from core.telefonos import normalizar_telefono_rd
from pedidos import whatsapp_api


class Command(BaseCommand):
    help = 'Envia la plantilla de avisos de pedido a un telefono, con datos de ejemplo.'

    def add_arguments(self, parser):
        parser.add_argument('telefono', help='Telefono con WhatsApp, por ejemplo 809-555-1234.')

    def handle(self, *args, telefono, **opciones):
        if not whatsapp_api.configurado():
            raise CommandError('Faltan WHATSAPP_TOKEN y WHATSAPP_NUMERO_ID (docs/WHATSAPP.md).')
        try:
            numero = normalizar_telefono_rd(telefono)
        except ValueError as error:
            raise CommandError(str(error))
        parametros = ['Prueba', 'MMX-0000-00000', 'pagado', url_absoluta('/')]
        if not whatsapp_api.enviar_plantilla(numero, parametros, f'prueba a {numero}'):
            raise CommandError('Meta no lo acepto: el motivo esta en el registro (logs) justo arriba.')
        self.stdout.write(self.style.SUCCESS('Enviado. Revisa el WhatsApp de ese telefono.'))
