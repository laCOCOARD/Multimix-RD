from django.db import migrations

# Las solicitudes que ya habia guardan la categoria que eligieron en sus notas internas, antes de quitar el campo
# (tiendas/0020). En su propio archivo: PostgreSQL no deja alterar la tabla en la transaccion que cambio sus filas.


def conservar_categoria(apps, schema_editor):
    Solicitud = apps.get_model('tiendas', 'SolicitudTienda')
    for solicitud in Solicitud.objects.filter(categoria__isnull=False).select_related('categoria'):
        nota = f'Categoría elegida en la solicitud: {solicitud.categoria.nombre}.'
        solicitud.notas = '\n'.join(parte for parte in (solicitud.notas.strip(), nota) if parte)
        solicitud.save(update_fields=['notas'])


class Migration(migrations.Migration):

    dependencies = [
        ('tiendas', '0018_rubro_de_las_solicitudes'),
    ]

    operations = [
        migrations.RunPython(conservar_categoria, migrations.RunPython.noop),
    ]
