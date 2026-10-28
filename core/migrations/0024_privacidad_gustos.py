from django.db import migrations

# Los gustos del cliente (2026-10-27): se dice en la politica de privacidad que se preguntan y para que se usan. Solo si
# la frase del texto estandar sigue tal cual (lo que el dueño reescribio en el panel se respeta).

ANTES = '- Las reseñas, preguntas, favoritos y solicitudes de devolución que hagas.'
AHORA = (
    ANTES + '\n- Si respondes las preguntas sobre tus gustos al crear tu cuenta: qué te gusta comprar, qué buscas, cuánto '
    'sueles gastar y cómo prefieres recibir tus compras. Solo las usamos para ordenar los productos y las promociones que '
    'te mostramos y para marcar tu forma de entrega preferida; no las compartimos con las tiendas. Puedes cambiarlas o '
    'borrarlas en "Mi cuenta".'
)


def agregar(apps, schema_editor):
    Pagina = apps.get_model('core', 'PaginaInformativa')
    pagina = Pagina.objects.filter(slug='privacidad').first()
    if pagina and ANTES in pagina.contenido and 'preguntas sobre tus gustos' not in pagina.contenido:
        pagina.contenido = pagina.contenido.replace(ANTES, AHORA, 1)
        pagina.save(update_fields=['contenido', 'actualizado'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_politicas_al_dia'),
    ]

    operations = [
        migrations.RunPython(agregar, migrations.RunPython.noop),
    ]
