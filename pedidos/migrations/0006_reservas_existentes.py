from django.db import migrations


def marcar_reservas(apps, schema_editor):
    """Hasta ahora todo pedido apartaba stock: sus lineas quedan marcadas para liberarlo o descontarlo igual."""
    apps.get_model('pedidos', 'DetallePedido').objects.update(reserva_stock=True)


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0005_disponibilidad'),
    ]

    operations = [
        migrations.RunPython(marcar_reservas, migrations.RunPython.noop),
    ]
