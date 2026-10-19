from django.db import migrations

# Pedido del dueño el 2026-10-19: la cuenta de vendedor de MaxFit quedo sin tienda (la tienda ya no existe) y seguia
# pudiendo entrar al panel. Solo se borra si sigue igual: sin tiendas y sin ser administrador.
VENDEDOR = 'Marcosfit'


def quitar_vendedor(apps, schema_editor):
    Usuario = apps.get_model('auth', 'User')
    Tienda = apps.get_model('tiendas', 'Tienda')
    usuario = Usuario.objects.filter(username=VENDEDOR, is_superuser=False).first()
    if usuario is not None and not Tienda.objects.filter(usuarios=usuario).exists():
        usuario.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('tiendas', '0012_remove_tienda_el_sitio_cobra'),
    ]

    operations = [
        migrations.RunPython(quitar_vendedor, migrations.RunPython.noop),
    ]
