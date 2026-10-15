from django.db import migrations


def completar(apps, schema_editor):
    """Liquidaciones anteriores: lo que cobro la tienda y la comision de esas ventas, sacado de sus pedidos.

    En un pedido que cobro la tienda, lo liquidado fue solo la comision en negativo.
    """
    Liquidacion = apps.get_model('pagos', 'Liquidacion')
    Pedido = apps.get_model('pedidos', 'Pedido')
    for liquidacion in Liquidacion.objects.all():
        de_la_tienda = Pedido.objects.filter(liquidacion=liquidacion, cobra_el_sitio=False)
        liquidacion.cobrado_por_la_tienda = liquidacion.ventas - liquidacion.cobrado_por_el_sitio
        liquidacion.comision_de_lo_cobrado_por_la_tienda = sum(-(p.monto_liquidado or 0) for p in de_la_tienda)
        liquidacion.save(update_fields=['cobrado_por_la_tienda', 'comision_de_lo_cobrado_por_la_tienda'])


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0004_cobrado_por_la_tienda'),
        ('pedidos', '0012_cobra_el_sitio_datos'),
    ]

    operations = [migrations.RunPython(completar, migrations.RunPython.noop)]
