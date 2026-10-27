from django.core.management.base import BaseCommand

from catalogo.models import FotoProducto
from catalogo.services import crear_miniaturas_faltantes


class Command(BaseCommand):
    help = 'Crea las miniaturas de las fotos de producto que no la tienen (las tareas periodicas lo hacen de a cinco).'

    def handle(self, *args, **opciones):
        total = 0
        while True:
            hechas = crear_miniaturas_faltantes(limite=20)
            total += hechas
            if not hechas:
                break
        faltan = FotoProducto.objects.filter(miniatura='').exclude(imagen='').count()
        self.stdout.write(f'Miniaturas creadas: {total}. Sin miniatura todavia: {faltan}.')
