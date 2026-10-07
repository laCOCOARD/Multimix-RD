from django.db import migrations

from tiendas.migraciones import asignar_a_la_tienda_principal


def copiar_secuencias(apps, schema_editor):
    """El contador unico de pedidos pasa a ser el de la tienda principal: su numeracion continua."""
    principal = apps.get_model('tiendas', 'Tienda').objects.order_by('pk').first()
    if principal is None:
        return
    SecuenciaTienda = apps.get_model('pedidos', 'SecuenciaTienda')
    for secuencia in apps.get_model('pedidos', 'SecuenciaPedido').objects.all():
        SecuenciaTienda.objects.update_or_create(
            tienda=principal, anio=secuencia.anio, defaults={'ultimo': secuencia.ultimo},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0002_tienda_inicial'),
        ('tiendas', '0002_tienda_principal'),
    ]

    operations = [
        migrations.RunPython(
            asignar_a_la_tienda_principal('pedidos', 'Pedido', 'ZonaEnvio'), migrations.RunPython.noop,
        ),
        migrations.RunPython(copiar_secuencias, migrations.RunPython.noop),
    ]
