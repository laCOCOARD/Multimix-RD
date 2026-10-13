from django.db import migrations

# La compra ya se completa en el sitio: el texto que decia que se compra por WhatsApp se actualiza,
# salvo que el dueño ya lo hubiera cambiado por uno propio.
ANTERIOR = 'Tiendas de emprendedores en un solo lugar. Compra directo a cada tienda por WhatsApp.'
NUEVA = 'Tiendas de emprendedores en un solo lugar. Compra en línea y recibe tu pedido en casa o recógelo en la tienda.'


def actualizar_descripcion(apps, schema_editor):
    apps.get_model('core', 'ConfiguracionTienda').objects.filter(descripcion=ANTERIOR).update(descripcion=NUEVA)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_itbis_y_sector'),
    ]

    operations = [
        migrations.RunPython(actualizar_descripcion, migrations.RunPython.noop),
    ]
