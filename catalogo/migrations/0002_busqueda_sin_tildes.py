from django.db import migrations, models

from core.texto import normalizar


def llenar_texto_busqueda(apps, schema_editor):
    Producto = apps.get_model('catalogo', 'Producto')
    for producto in Producto.objects.all().iterator():
        producto.texto_busqueda = normalizar(f'{producto.nombre} {producto.sku} {producto.descripcion}')
        producto.save(update_fields=['texto_busqueda'])


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='texto_busqueda',
            field=models.TextField(default='', editable=False, help_text='Nombre, SKU y descripción sin tildes; lo usa el buscador.'),
        ),
        migrations.RunPython(llenar_texto_busqueda, migrations.RunPython.noop),
    ]
