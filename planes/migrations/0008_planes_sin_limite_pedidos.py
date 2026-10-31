from django.db import migrations

DESCRIPCIONES = {
    'Básico':    'Para empezar: mensualidad fija, ventas ilimitadas.',
    'Estándar':  'Ventas ilimitadas, 1 anuncio y 4 productos anunciados en la portada.',
    'Premium':   'Ventas ilimitadas, 2 anuncios, 12 productos anunciados y 1 video en la portada.',
}


def quitar_limite(apps, schema_editor):
    Plan = apps.get_model('planes', 'Plan')
    for plan in Plan.objects.all():
        plan.pedidos_incluidos = None
        plan.porcentaje_excedente = 0
        if plan.nombre in DESCRIPCIONES:
            plan.descripcion = DESCRIPCIONES[plan.nombre]
        plan.save()


def restaurar_limite(apps, schema_editor):
    # La reversa deja los planes sin limite; no vale la pena restaurar valores arbitrarios.
    pass


class Migration(migrations.Migration):
    dependencies = [('planes', '0007_deposito_del_cambio_de_plan')]

    operations = [migrations.RunPython(quitar_limite, restaurar_limite)]
