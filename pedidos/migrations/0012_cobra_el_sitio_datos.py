from django.db import migrations


def marcar(apps, schema_editor):
    """Los pedidos por transferencia de las tiendas en las que el sitio ya recibia los pagos los cobro el sitio."""
    Pedido = apps.get_model('pedidos', 'Pedido')
    Pedido.objects.filter(metodo_pago='transferencia', tienda__el_sitio_cobra=True).update(cobra_el_sitio=True)


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0011_pedido_cobra_el_sitio'),
        ('tiendas', '0011_alter_tienda_el_sitio_cobra'),
    ]

    operations = [migrations.RunPython(marcar, migrations.RunPython.noop)]
