from django.db import migrations

CAMPOS = ['banco', 'tipo_cuenta', 'numero', 'titular', 'cedula_rnc', 'activa', 'orden']


def pasar_al_sitio(apps, schema_editor):
    """Las cuentas ya no son de cada tienda: todas las transferencias llegan al sitio.

    Se conservan las de la tienda mas antigua (la del dueño, la primera que hubo) como cuentas del sitio, para que
    el checkout no se quede sin cuentas al desplegar. Las de las demas tiendas se descartan: son de los vendedores.
    """
    CuentaDelSitio = apps.get_model('core', 'CuentaDelSitio')
    CuentaBancaria = apps.get_model('core', 'CuentaBancaria')
    Tienda = apps.get_model('tiendas', 'Tienda')
    primera = Tienda.objects.order_by('pk').first()
    if primera is None or CuentaDelSitio.objects.exists():
        return
    for cuenta in CuentaBancaria.objects.filter(tienda=primera).order_by('orden', 'pk'):
        CuentaDelSitio.objects.get_or_create(
            banco=cuenta.banco, numero=cuenta.numero, defaults={campo: getattr(cuenta, campo) for campo in CAMPOS},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_cuentadelsitio'),
        ('tiendas', '0011_alter_tienda_el_sitio_cobra'),
    ]

    operations = [migrations.RunPython(pasar_al_sitio, migrations.RunPython.noop)]
