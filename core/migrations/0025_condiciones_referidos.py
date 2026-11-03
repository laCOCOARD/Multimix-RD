"""Programa de referidos entre tiendas (pedido del dueño el 2026-11-02): agrega sus reglas al final de "Condiciones para
vendedores". Solo si la pagina existe y todavia no las tiene; si el texto se cambio a mano, igual se agrega al final."""
from django.db import migrations

TITULO = 'Programa de referidos'
SECCION = f"""{TITULO}
Cada tienda tiene un enlace para invitar a otros negocios. Las reglas son:
- Una tienda invitada cuenta cuando abre su tienda con tu enlace o tu código y paga su primera mensualidad.
- Por cada 2 tiendas invitadas que cuentan, ganas 25% de descuento en tu próxima mensualidad y 1 anuncio extra en la portada por 30 días.
- El descuento se aplica solo en tu mensualidad y se usa dentro de los 90 días siguientes; si no, se pierde. No se cambia por dinero.
- La tienda invitada recibe 10% de descuento en su primera mensualidad.
- Un premio ya ganado no se quita aunque después una tienda invitada se vaya.
- Una tienda no puede invitarse a sí misma. Si vemos invitaciones falsas, podemos anular los premios."""


def agregar(apps, schema_editor):
    PaginaInformativa = apps.get_model('core', 'PaginaInformativa')
    pagina = PaginaInformativa.objects.filter(slug='condiciones-para-vendedores').first()
    if pagina is None or TITULO in pagina.contenido:
        return
    pagina.contenido = pagina.contenido.rstrip() + '\n\n' + SECCION
    pagina.save(update_fields=['contenido'])


class Migration(migrations.Migration):
    dependencies = [('core', '0024_privacidad_gustos')]
    operations = [migrations.RunPython(agregar, migrations.RunPython.noop)]
