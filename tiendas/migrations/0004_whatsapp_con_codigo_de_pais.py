from django.db import migrations

from tiendas.migraciones import poner_codigo_de_pais


class Migration(migrations.Migration):

    dependencies = [
        ('tiendas', '0003_ajustes_de_formulario'),
    ]

    operations = [
        migrations.RunPython(poner_codigo_de_pais('tiendas', 'Tienda'), migrations.RunPython.noop),
    ]
