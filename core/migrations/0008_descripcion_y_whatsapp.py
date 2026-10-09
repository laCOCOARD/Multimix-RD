from django.db import migrations

from tiendas.migraciones import poner_codigo_de_pais

# Lemas de la tienda original que habian quedado como texto del sitio. Ese lema sigue en su tienda.
LEMAS_DE_LA_TIENDA = [
    '',
    'Productos de todas las categorías con entrega en todo el país.',
    'Salud, belleza y equilibrio: vitaminas, cuidado personal y más, con entrega en todo el país.',
]
DESCRIPCION_DEL_SITIO = 'Tiendas de emprendedores en un solo lugar. Compra directo a cada tienda por WhatsApp.'


def describir_el_sitio(apps, schema_editor):
    Configuracion = apps.get_model('core', 'ConfiguracionTienda')
    Configuracion.objects.filter(descripcion__in=LEMAS_DE_LA_TIENDA).update(descripcion=DESCRIPCION_DEL_SITIO)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_ajustes_de_formulario'),
    ]

    operations = [
        migrations.RunPython(describir_el_sitio, migrations.RunPython.noop),
        migrations.RunPython(poner_codigo_de_pais('core', 'ConfiguracionTienda'), migrations.RunPython.noop),
    ]
