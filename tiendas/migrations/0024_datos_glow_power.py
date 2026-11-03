"""Correcciones de datos pedidas por el dueño el 2026-11-02: correo, provincia y horario de la tienda glow-power, el
horario del pie de pagina (ConfiguracionTienda) y el titulo "prueba" del video de la portada.

Solo cambia lo que siga exactamente como estaba: si alguien ya lo corrigio en el panel, no se toca.
"""
from django.db import migrations

HORARIO = 'Lunes a sábado, 9:00 a. m. – 6:00 p. m.'
HORARIO_VIEJO = 'LUNES A SÁBADOS 9:00 a.m a 6:00 p.m'


def corregir(apps, schema_editor):
    Tienda = apps.get_model('tiendas', 'Tienda')
    ConfiguracionTienda = apps.get_model('core', 'ConfiguracionTienda')
    Video = apps.get_model('planes', 'Video')

    tienda = Tienda.objects.filter(slug='glow-power').first()
    if tienda is not None:
        cambios = []
        if 'gmial.com' in tienda.correo:
            tienda.correo = tienda.correo.replace('gmial.com', 'gmail.com')
            cambios.append('correo')
        if tienda.direccion_tienda == 'Sosúa, puerto plata':
            tienda.direccion_tienda = 'Sosúa, Puerto Plata'
            cambios.append('direccion_tienda')
        if tienda.horario == HORARIO_VIEJO:
            tienda.horario = HORARIO
            cambios.append('horario')
        if cambios:
            tienda.save(update_fields=cambios)

    ConfiguracionTienda.objects.filter(horario=HORARIO_VIEJO).update(horario=HORARIO)

    # "prueba" no es un titulo para los clientes: se usa el nombre del producto del video (o uno generico).
    for video in Video.objects.filter(titulo__iexact='prueba').select_related('producto'):
        video.titulo = (video.producto.nombre if video.producto_id else 'Conoce nuestra tienda')[:80]
        video.save(update_fields=['titulo'])


class Migration(migrations.Migration):
    dependencies = [
        ('tiendas', '0023_solicitudtienda_codigo_referido'),
        ('core', '0025_condiciones_referidos'),
        ('planes', '0009_alter_cargo_tipo'),
    ]
    operations = [migrations.RunPython(corregir, migrations.RunPython.noop)]
