from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tiendas', '0019_rubro_desde_la_categoria'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='solicitudtienda',
            name='categoria',
        ),
    ]
