from decimal import Decimal

from django.db import migrations


def corregir(apps, schema_editor):
    """Pedido del dueño el 2026-10-19: a la tienda le llegaron los RD$ 2,880.00 completos de la liquidacion 3; los
    RD$ 2.88 del banco los pago el sitio aparte (desde ahora siempre es asi). Solo toca esa fila si sigue igual."""
    apps.get_model('pagos', 'Liquidacion').objects.filter(
        pk=3, monto=Decimal('2877.12'), costo_transferencia=Decimal('2.88'),
    ).update(monto=Decimal('2880.00'))


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0007_comision_del_banco_la_paga_el_sitio'),
    ]

    operations = [
        migrations.RunPython(corregir, migrations.RunPython.noop),
    ]
