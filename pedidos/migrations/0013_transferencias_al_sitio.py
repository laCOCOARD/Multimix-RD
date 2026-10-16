from django.db import migrations


def marcar(apps, schema_editor):
    """Los pedidos por transferencia que el cliente aun no pago van a ver las cuentas del sitio: los cobra el sitio."""
    Pedido = apps.get_model('pedidos', 'Pedido')
    Pedido.objects.filter(
        metodo_pago='transferencia', estado='pendiente', transferencia_realizada=False, fecha_pago__isnull=True,
    ).update(cobra_el_sitio=True)


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0012_cobra_el_sitio_datos'),
    ]

    operations = [migrations.RunPython(marcar, migrations.RunPython.noop)]
