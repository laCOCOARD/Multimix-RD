from datetime import timedelta

from django.db import migrations
from django.utils import timezone

# Pedido del dueño el 2026-10-28: el Estándar tiene 1 anuncio con foto; el Premium, 2 con foto y 1 video (3 juntos).
# Cada anuncio dura 7 dias desde que se aprueba. Solo se tocan los planes que siguen con los valores de fabrica.
DESCRIPCION_VIEJA = '600 pedidos al mes, 3 anuncios, 12 productos anunciados y 1 video en la portada.'
DESCRIPCION_NUEVA = '600 pedidos al mes, 2 anuncios con foto, 1 video y 12 productos anunciados en la portada.'


def ajustar(apps, schema_editor):
    Plan = apps.get_model('planes', 'Plan')
    Anuncio = apps.get_model('planes', 'Anuncio')
    premium = Plan.objects.filter(nombre='Premium').first()
    if premium is not None:
        if premium.anuncios_portada == 3:
            premium.anuncios_portada = 2
        if premium.videos_portada == 0:
            premium.videos_portada = 1
        if premium.descripcion == DESCRIPCION_VIEJA:
            premium.descripcion = DESCRIPCION_NUEVA
        premium.save()
    # Los anuncios ya aprobados sin fecha de fin empiezan a contar sus 7 dias hoy.
    ahora = timezone.now()
    Anuncio.objects.filter(aprobado=True, vigente_hasta__isnull=True).update(
        vigente_desde=ahora, vigente_hasta=ahora + timedelta(days=7),
    )


class Migration(migrations.Migration):
    dependencies = [('planes', '0005_texto_de_los_anuncios')]

    operations = [migrations.RunPython(ajustar, migrations.RunPython.noop)]
