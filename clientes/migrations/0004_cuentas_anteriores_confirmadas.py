from django.db import migrations


def confirmar_las_anteriores(apps, schema_editor):
    """Las cuentas de antes ya venian comprando y recibiendo sus avisos: no se les pide confirmar el correo."""
    apps.get_model('clientes', 'Perfil').objects.update(correo_verificado=True)


class Migration(migrations.Migration):
    # En su propio archivo: PostgreSQL no deja alterar una tabla y actualizar sus filas en la misma transaccion.

    dependencies = [
        ('clientes', '0003_correo_verificado'),
    ]

    operations = [
        migrations.RunPython(confirmar_las_anteriores, migrations.RunPython.noop),
    ]
