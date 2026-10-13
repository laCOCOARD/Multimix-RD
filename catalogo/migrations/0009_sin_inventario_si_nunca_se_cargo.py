from django.db import migrations


def soltar_inventario_vacio(apps, schema_editor):
    """Corrige la 0008 en las tiendas que apenas empezaban a cargar unidades.

    Bastaba un producto con stock para que toda la tienda quedara llevando inventario, y los demas
    (en cero porque nunca se les cargo nada) seguian saliendo agotados. En una tienda que todavia no
    tiene pedidos, un producto en cero y sin reservas no es un agotado real: pasa a venderse por su
    disponibilidad. Las tiendas con pedidos no se tocan; ahi el cero si puede ser un agotado.
    """
    Producto = apps.get_model('catalogo', 'Producto')
    Pedido = apps.get_model('pedidos', 'Pedido')
    con_pedidos = Pedido.objects.values_list('tienda_id', flat=True).distinct()
    (
        Producto.objects.filter(controla_stock=True, stock_almacen=0, stock_reservado=0)
        .exclude(tienda_id__in=list(con_pedidos)).update(controla_stock=False)
    )


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0008_inventario_donde_ya_se_usaba'),
        ('pedidos', '0006_reservas_existentes'),
    ]

    operations = [
        migrations.RunPython(soltar_inventario_vacio, migrations.RunPython.noop),
    ]
