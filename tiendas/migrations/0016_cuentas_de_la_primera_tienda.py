from django.db import migrations


def copiar_cuentas(apps, schema_editor):
    """Desde el 2026-10-26 cada tienda cobra en sus propias cuentas. La tienda mas antigua es la del dueño (la que
    tenia las cuentas antes de que pasaran al sitio en core/0017): recibe una copia de las del sitio para que sus
    clientes sigan pudiendo transferir. Las demas tiendas registran las suyas en el panel."""
    Tienda = apps.get_model('tiendas', 'Tienda')
    CuentaBancaria = apps.get_model('tiendas', 'CuentaBancaria')
    CuentaDelSitio = apps.get_model('core', 'CuentaDelSitio')
    primera = Tienda.objects.order_by('pk').first()
    if primera is None or CuentaBancaria.objects.filter(tienda=primera).exists():
        return
    for cuenta in CuentaDelSitio.objects.order_by('orden', 'pk'):
        CuentaBancaria.objects.create(
            tienda=primera, banco=cuenta.banco, tipo_cuenta=cuenta.tipo_cuenta, numero=cuenta.numero,
            titular=cuenta.titular, cedula_rnc=cuenta.cedula_rnc, activa=cuenta.activa, orden=cuenta.orden,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('tiendas', '0015_planes_y_cuentas'),
        ('core', '0020_cobro_a_las_tiendas'),
    ]

    operations = [
        migrations.RunPython(copiar_cuentas, migrations.RunPython.noop),
    ]
