from decimal import Decimal

from django.db import migrations

# Los tres planes que pidio el dueño el 2026-10-26. Los montos son una propuesta: se cambian en el panel
# (Planes). Ninguna tienda queda con un plan: a quien no tiene plan no se le cobra nada.
PLANES = [
    {
        'nombre': 'Básico', 'orden': 1, 'mensualidad': Decimal('500.00'), 'pedidos_incluidos': 50,
        'porcentaje_excedente': Decimal('5.00'), 'anuncios_portada': 0, 'productos_patrocinados': 0,
        'descripcion': 'Para empezar: 50 pedidos cobrados al mes incluidos.',
    },
    {
        'nombre': 'Estándar', 'orden': 2, 'mensualidad': Decimal('1200.00'), 'pedidos_incluidos': 200,
        'porcentaje_excedente': Decimal('4.00'), 'anuncios_portada': 1, 'productos_patrocinados': 4,
        'descripcion': '200 pedidos al mes, 1 anuncio y 4 productos anunciados en la portada.',
    },
    {
        'nombre': 'Premium', 'orden': 3, 'mensualidad': Decimal('2500.00'), 'pedidos_incluidos': 600,
        'porcentaje_excedente': Decimal('3.00'), 'anuncios_portada': 3, 'productos_patrocinados': 12,
        'descripcion': '600 pedidos al mes, 3 anuncios y 12 productos anunciados en la portada.',
    },
]


def crear_planes(apps, schema_editor):
    Plan = apps.get_model('planes', 'Plan')
    for datos in PLANES:
        Plan.objects.get_or_create(nombre=datos['nombre'], defaults=datos)


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_planes, migrations.RunPython.noop),
    ]
