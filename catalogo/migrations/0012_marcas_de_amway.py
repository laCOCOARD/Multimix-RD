import re

from django.db import migrations

# Lineas de Amway que aparecen en el nombre de sus productos. El dueño pidio dejarlos marcados:
# con la linea como marca, el filtro del catalogo separa maquillaje, vitaminas, cabello...
LINEAS = [
    ('Nutrilite', re.compile(r'\bnutrilite\b', re.IGNORECASE)),
    ('Artistry', re.compile(r'\bartistry\b', re.IGNORECASE)),
    ('Satinique', re.compile(r'\bsatinique\b', re.IGNORECASE)),
    ('Glister', re.compile(r'\bglister\b', re.IGNORECASE)),
    ('g&h', re.compile(r'\bg&h\b', re.IGNORECASE)),
    ('XS', re.compile(r'\bXS\b')),
]


def linea_de(nombre):
    for linea, patron in LINEAS:
        if patron.search(nombre or ''):
            return linea
    return ''


def marcar_lineas(apps, schema_editor):
    """Pone la marca solo a los productos que no tienen y cuyo nombre trae una linea conocida."""
    Producto = apps.get_model('catalogo', 'Producto')
    from core.texto import normalizar

    for producto in Producto.objects.filter(marca=''):
        marca = linea_de(producto.nombre)
        if not marca:
            continue
        # El modelo historico no pasa por Producto.save(): el texto del buscador se arma aqui.
        producto.marca = marca
        producto.texto_busqueda = normalizar(f'{producto.nombre} {marca} {producto.sku} {producto.descripcion}')
        producto.save(update_fields=['marca', 'texto_busqueda'])


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0011_itbis_y_sector'),
    ]

    operations = [
        migrations.RunPython(marcar_lineas, migrations.RunPython.noop),
    ]
