from django.db import migrations, models

TITULO_ANTERIOR = 'Todo lo que buscas, en un solo lugar'
SUBTITULO_ANTERIOR = 'Productos de todas las categorías con entrega en todo el país.'
TITULO = 'Tu tienda de bienestar'
SUBTITULO = 'Salud, belleza y equilibrio: vitaminas, cuidado personal y más, con entrega en todo el país.'


def aplicar_marca(apps, schema_editor):
    """Pone los textos de la marca si siguen los de fabrica y quita las imagenes cuyo archivo ya no existe."""
    Configuracion = apps.get_model('core', 'ConfiguracionTienda')
    for config in Configuracion.objects.all():
        cambios = []
        if config.banner_titulo == TITULO_ANTERIOR:
            config.banner_titulo = TITULO
            cambios.append('banner_titulo')
        if config.banner_subtitulo == SUBTITULO_ANTERIOR:
            config.banner_subtitulo = SUBTITULO
            cambios.append('banner_subtitulo')
        # El logo y el banner subidos cuando los archivos se guardaban en el disco del servidor
        # se perdieron en un despliegue: la tienda mostraba una imagen rota.
        for campo in ('logo', 'banner_imagen'):
            archivo = getattr(config, campo)
            if not archivo:
                continue
            try:
                existe = archivo.storage.exists(archivo.name)
            except Exception:
                continue  # si no se puede consultar el almacenamiento, no se toca nada
            if not existe:
                setattr(config, campo, '')
                cambios.append(campo)
        if cambios:
            config.save(update_fields=cambios)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='configuraciontienda',
            name='banner_subtitulo',
            field=models.CharField(blank=True, default=SUBTITULO, max_length=220, verbose_name='subtítulo del banner'),
        ),
        migrations.AlterField(
            model_name='configuraciontienda',
            name='banner_titulo',
            field=models.CharField(default=TITULO, max_length=120, verbose_name='título del banner'),
        ),
        migrations.RunPython(aplicar_marca, migrations.RunPython.noop),
    ]
