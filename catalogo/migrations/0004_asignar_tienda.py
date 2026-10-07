from django.db import migrations

from tiendas.migraciones import asignar_a_la_tienda_principal


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0003_tienda_inicial'),
        ('tiendas', '0002_tienda_principal'),
    ]

    operations = [
        migrations.RunPython(asignar_a_la_tienda_principal('catalogo', 'Producto'), migrations.RunPython.noop),
    ]
