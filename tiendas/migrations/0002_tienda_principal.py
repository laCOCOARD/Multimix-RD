from django.db import migrations
from django.utils.text import slugify

# Marca, contactos y forma de cobrar que antes eran de todo el sitio y ahora son de cada tienda.
CAMPOS_COPIADOS = [
    'logo', 'banner_titulo', 'banner_subtitulo', 'banner_texto_boton', 'banner_imagen',
    'correo', 'telefono', 'horario', 'whatsapp', 'direccion_tienda', 'facebook', 'instagram', 'tiktok',
    'permitir_contra_entrega',
]
MODELOS_CON_DATOS = [
    ('catalogo', 'Producto'), ('pedidos', 'Pedido'), ('pedidos', 'ZonaEnvio'),
    ('promociones', 'Cupon'), ('core', 'CuentaBancaria'),
]


def crear_tienda_principal(apps, schema_editor):
    """La tienda unica que existia pasa a ser la primera subtienda, con su marca y sus contactos.

    Conserva el prefijo MMX para que su numeracion de pedidos siga donde iba. En una instalacion
    nueva (sin configuracion ni datos) no crea nada.
    """
    Tienda = apps.get_model('tiendas', 'Tienda')
    if Tienda.objects.exists():
        return
    Configuracion = apps.get_model('core', 'ConfiguracionTienda')
    config = Configuracion.objects.filter(pk=1).first()
    hay_datos = any(apps.get_model(app, modelo).objects.exists() for app, modelo in MODELOS_CON_DATOS)
    if config is None and not hay_datos:
        return
    config = config or Configuracion()

    valores = {}
    for campo in CAMPOS_COPIADOS:
        valor = getattr(config, campo)
        # De las imagenes se copia la ruta: la tienda apunta al mismo archivo ya subido.
        valores[campo] = (valor.name or '') if hasattr(valor, 'name') else valor
    nombre = config.nombre or 'Multimix RD'
    Tienda.objects.create(nombre=nombre, slug=slugify(nombre)[:60] or 'tienda', prefijo='MMX', **valores)


class Migration(migrations.Migration):

    dependencies = [
        ('tiendas', '0001_tienda_inicial'),
        ('core', '0002_textos_de_marca'),
        ('catalogo', '0002_busqueda_sin_tildes'),
        ('pedidos', '0001_initial'),
        ('promociones', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_tienda_principal, migrations.RunPython.noop),
    ]
