from django.core.management.base import BaseCommand

from planes.services import revisar_cobros


class Command(BaseCommand):
    help = ('Crea las mensualidades y los cargos por pedidos de más, envía los recordatorios y cierra las tiendas que '
            'no pagaron a tiempo. En Render lo hacen solas las tareas periódicas; donde haya cron, una vez al día basta.')

    def handle(self, *args, **opciones):
        resultado = revisar_cobros()
        self.stdout.write(
            f'Mensualidades: {len(resultado["mensualidades"])} · pedidos de más: {len(resultado["excedentes"])} · '
            f'avisos: {resultado["avisos"]} · tiendas cerradas: {len(resultado["cerradas"])}'
        )
