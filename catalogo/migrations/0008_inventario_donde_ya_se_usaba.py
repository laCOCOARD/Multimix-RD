from django.db import migrations


def conservar_inventario(apps, schema_editor):
    """Todos los productos quedan "Disponible" (el valor por defecto del campo nuevo).

    La tienda que ya tenia unidades cargadas sigue llevando inventario en todos sus productos; la que
    tenia todo en cero no lo usaba, y sus productos pasan a venderse por disponibilidad.
    """
    Producto = apps.get_model('catalogo', 'Producto')
    con_unidades = Producto.objects.filter(stock_almacen__gt=0).values_list('tienda_id', flat=True).distinct()
    Producto.objects.filter(tienda_id__in=list(con_unidades)).update(controla_stock=True)


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0007_disponibilidad'),
    ]

    operations = [
        migrations.RunPython(conservar_inventario, migrations.RunPython.noop),
    ]
