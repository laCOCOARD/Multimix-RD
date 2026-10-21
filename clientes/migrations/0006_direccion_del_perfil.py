from django.db import migrations


def pasar_a_direcciones(apps, schema_editor):
    """La direccion que guardaba el perfil pasa a ser la primera direccion guardada (y la principal)."""
    Perfil = apps.get_model('clientes', 'Perfil')
    Direccion = apps.get_model('clientes', 'Direccion')
    for perfil in Perfil.objects.exclude(direccion=''):
        if not Direccion.objects.filter(usuario_id=perfil.usuario_id).exists():
            Direccion.objects.create(
                usuario_id=perfil.usuario_id, nombre='Casa', sector=perfil.sector or '-', direccion=perfil.direccion,
                referencia=perfil.referencia, principal=True,
            )


class Migration(migrations.Migration):
    # En su propio archivo: PostgreSQL no deja alterar una tabla y actualizar sus filas en la misma transaccion.

    dependencies = [
        ('clientes', '0005_direcciones_y_carrito_guardado'),
    ]

    operations = [
        migrations.RunPython(pasar_a_direcciones, migrations.RunPython.noop),
    ]
