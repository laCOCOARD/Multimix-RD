from django.db import migrations


class Migration(migrations.Migration):
    """La portada del sitio deja de tener banner: del antiguo solo queda el subtitulo, como descripcion del sitio."""

    dependencies = [
        ('core', '0005_tienda_obligatoria'),
    ]

    operations = [
        migrations.RenameField(model_name='configuraciontienda', old_name='banner_subtitulo', new_name='descripcion'),
        migrations.RemoveField(model_name='configuraciontienda', name='banner_titulo'),
        migrations.RemoveField(model_name='configuraciontienda', name='banner_texto_boton'),
        migrations.RemoveField(model_name='configuraciontienda', name='banner_imagen'),
    ]
