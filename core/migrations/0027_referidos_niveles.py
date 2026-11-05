"""Escalera de premios del programa de referidos (pedido del dueño el 2026-11-05): cambia en "Condiciones para
vendedores" la regla de los premios por la de los niveles. Si la linea se cambio a mano, no toca nada."""
from django.db import migrations

ANTES = (
    '- Por cada 2 tiendas invitadas que cuentan, ganas 25% de descuento en tu próxima mensualidad y 1 anuncio extra '
    'en la portada por 30 días.'
)
AHORA = """- Con 2 tiendas invitadas que cuentan ganas 25% de descuento en tu próxima mensualidad y 1 anuncio extra en la portada por 30 días.
- Con 4 ganas 50% en tu próxima mensualidad y tu tienda sale entre las tiendas destacadas de la portada por 15 días.
- Con 6 ganas un mes gratis y la insignia "Tienda embajadora", que no se quita. El mes gratis se da una sola vez.
- Después, cada 2 tiendas más ganas otra vez 25% y 1 anuncio extra por 30 días.
- Se usa un premio por mensualidad y el descuento nunca pasa del 100%."""


def cambiar(apps, schema_editor):
    PaginaInformativa = apps.get_model('core', 'PaginaInformativa')
    pagina = PaginaInformativa.objects.filter(slug='condiciones-para-vendedores').first()
    if pagina is None or ANTES not in pagina.contenido:
        return
    pagina.contenido = pagina.contenido.replace(ANTES, AHORA)
    pagina.save(update_fields=['contenido'])


class Migration(migrations.Migration):
    dependencies = [('core', '0026_precio_en_vender')]
    operations = [migrations.RunPython(cambiar, migrations.RunPython.noop)]
