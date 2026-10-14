from django.db import migrations

# Las paginas de politicas que debe tener la tienda. Se crean vacias y SIN publicar: el texto lo escribe
# y lo revisa el dueño (son compromisos legales con los clientes), y solo entonces las publica.
PAGINAS = [
    ('privacidad', 'Política de privacidad'),
    ('entregas', 'Política de entrega'),
    ('cambios-y-devoluciones', 'Cambios y devoluciones'),
    ('reembolsos', 'Política de reembolsos'),
    ('garantias', 'Garantías'),
    ('metodos-de-pago', 'Métodos de pago'),
    ('contacto', 'Contacto y datos comerciales'),
]


def crear_paginas(apps, schema_editor):
    Pagina = apps.get_model('core', 'PaginaInformativa')
    for orden, (slug, titulo) in enumerate(PAGINAS, start=1):
        Pagina.objects.get_or_create(slug=slug, defaults={'titulo': titulo, 'orden': orden, 'publicada': False})


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_contenido'),
    ]

    operations = [
        migrations.RunPython(crear_paginas, migrations.RunPython.noop),
    ]
