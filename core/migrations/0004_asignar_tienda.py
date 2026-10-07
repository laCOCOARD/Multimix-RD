from django.db import migrations

from tiendas.migraciones import asignar_a_la_tienda_principal


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_tienda_inicial'),
        ('tiendas', '0002_tienda_principal'),
    ]

    operations = [
        migrations.RunPython(asignar_a_la_tienda_principal('core', 'CuentaBancaria'), migrations.RunPython.noop),
    ]
