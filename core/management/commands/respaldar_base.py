"""Guarda ya un respaldo de la base en el almacenamiento privado (el automatico es semanal, core/respaldos.py)."""
from django.core.management.base import BaseCommand, CommandError

from core import respaldos


class Command(BaseCommand):
    help = 'Guarda un respaldo de la base (.json.gz) en el almacenamiento privado y lista los que hay.'

    def handle(self, *args, **opciones):
        if not respaldos.disponible():
            raise CommandError('Falta SUPABASE_S3_BUCKET_PRIVADO: el respaldo no va al bucket publico.')
        ruta = respaldos.respaldar()
        self.stdout.write(self.style.SUCCESS(f'Guardado: {ruta}'))
        for _, nombre in respaldos.respaldos():
            self.stdout.write(f'  {nombre}')
