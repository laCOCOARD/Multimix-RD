from django.db import migrations

# El dueño pidio el 2026-10-26 que el plan Premium permita "un video en la web para promocion de 15 segundos".
# Se cambia en el panel (Planes > Videos en la portada). Solo toca el plan si aun no tiene videos y la descripcion
# solo si sigue siendo la de planes/0002.
DESCRIPCION_ANTERIOR = '600 pedidos al mes, 3 anuncios y 12 productos anunciados en la portada.'
DESCRIPCION_NUEVA = '600 pedidos al mes, 3 anuncios, 12 productos anunciados y 1 video en la portada.'


def dar_video_al_premium(apps, schema_editor):
    Plan = apps.get_model('planes', 'Plan')
    for plan in Plan.objects.filter(nombre='Premium', videos_portada=0):
        plan.videos_portada = 1
        if plan.descripcion == DESCRIPCION_ANTERIOR:
            plan.descripcion = DESCRIPCION_NUEVA
        plan.save(update_fields=['videos_portada', 'descripcion'])


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0003_videos_de_las_tiendas'),
    ]

    operations = [
        migrations.RunPython(dar_video_al_premium, migrations.RunPython.noop),
    ]
