import referidos.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CodigoReferido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(default=referidos.models._codigo_unico, max_length=12, unique=True, verbose_name='código')),
                ('clics', models.PositiveIntegerField(default=0, editable=False)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='codigo_referido',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='usuario',
                )),
            ],
            options={
                'verbose_name': 'código de referido',
                'verbose_name_plural': 'códigos de referido',
            },
        ),
        migrations.CreateModel(
            name='Referido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip', models.GenericIPAddressField(blank=True, editable=False, null=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('tienda_creada', models.BooleanField(default=False, verbose_name='creó tienda')),
                ('invitado', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='referido_por',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='invitado',
                )),
                ('referente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='referidos_hechos',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='referente',
                )),
            ],
            options={
                'verbose_name': 'referido',
                'verbose_name_plural': 'referidos',
            },
        ),
        migrations.AddConstraint(
            model_name='referido',
            constraint=models.UniqueConstraint(
                condition=models.Q(invitado__isnull=False),
                fields=['invitado'],
                name='referido_invitado_unico',
            ),
        ),
    ]
