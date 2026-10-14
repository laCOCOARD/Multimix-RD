from django.db import migrations


def quitar_itbis(apps, schema_editor):
    """El dueño decidio no cobrar ITBIS aparte: ninguna tienda lo suma. Los pedidos ya hechos no cambian."""
    apps.get_model('tiendas', 'Tienda').objects.exclude(itbis_porcentaje=0).update(itbis_porcentaje=0)


class Migration(migrations.Migration):

    dependencies = [
        ('tiendas', '0007_sin_itbis'),
    ]

    operations = [
        migrations.RunPython(quitar_itbis, migrations.RunPython.noop),
    ]
