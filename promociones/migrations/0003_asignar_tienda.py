from django.db import migrations

from tiendas.migraciones import asignar_a_la_tienda_principal


class Migration(migrations.Migration):

    dependencies = [
        ('promociones', '0002_tienda_inicial'),
        ('tiendas', '0002_tienda_principal'),
    ]

    operations = [
        migrations.RunPython(asignar_a_la_tienda_principal('promociones', 'Cupon'), migrations.RunPython.noop),
    ]
