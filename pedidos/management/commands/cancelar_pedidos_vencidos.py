from django.core.management.base import BaseCommand

from pedidos.services import cancelar_pedidos_vencidos


class Command(BaseCommand):
    help = 'Cancela los pedidos pendientes más viejos que las horas definidas en Configuración y libera su stock.'

    def handle(self, *args, **options):
        cancelados = cancelar_pedidos_vencidos()
        if cancelados:
            self.stdout.write(self.style.SUCCESS(
                f'Pedidos cancelados: {len(cancelados)} ({", ".join(cancelados)})'
            ))
        else:
            self.stdout.write('No hay pedidos vencidos.')
