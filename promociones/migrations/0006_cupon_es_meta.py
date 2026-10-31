from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('promociones', '0005_usos_por_cliente'),
    ]

    operations = [
        migrations.AddField(
            model_name='cupon',
            name='es_meta',
            field=models.BooleanField(
                default=False,
                verbose_name='es cupón meta',
                help_text=(
                    'Se aplica automáticamente cuando el carrito llega a la compra mínima. '
                    'Una vez aplicado a un pedido, no se devuelve aunque el pedido se cancele.'
                ),
            ),
        ),
    ]
