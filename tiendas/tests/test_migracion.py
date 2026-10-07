"""Recorre las migraciones reales: un sitio de una sola tienda, con datos, pasa a tener su primera subtienda."""
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

# Estado de la base justo antes de que existieran las subtiendas.
ANTES = [
    ('tiendas', None),
    ('catalogo', '0002_busqueda_sin_tildes'),
    ('core', '0002_textos_de_marca'),
    ('pedidos', '0001_initial'),
    ('promociones', '0001_initial'),
]


def migrar(destinos):
    """Lleva la base a esas migraciones y devuelve los modelos tal como eran en ese punto."""
    ejecutor = MigrationExecutor(connection)
    ejecutor.migrate(destinos)
    return ejecutor.loader.project_state([destino for destino in destinos if destino[1]]).apps


def migrar_al_final():
    return migrar(MigrationExecutor(connection).loader.graph.leaf_nodes())


class DeUnaTiendaASubtiendasTests(TransactionTestCase):
    def setUp(self):
        # Pase lo que pase, la base vuelve al esquema actual para las demas pruebas.
        self.addCleanup(migrar_al_final)

    def test_lo_que_existia_pasa_a_la_primera_subtienda(self):
        anio = timezone.localdate().year
        antes = migrar(ANTES)
        antes.get_model('core', 'ConfiguracionTienda').objects.create(
            pk=1, nombre='Multimix RD', whatsapp='18095550123', horario='Lun a Sáb', logo='tienda/logo.png',
            direccion_tienda='Av. Winston Churchill #100', permitir_contra_entrega=True,
            banner_titulo='Tu tienda de bienestar',
        )
        categoria = antes.get_model('catalogo', 'Categoria').objects.create(nombre='Hogar', slug='hogar')
        antes.get_model('catalogo', 'Producto').objects.create(
            categoria=categoria, nombre='Lámpara', slug='lampara', sku='L1', precio=Decimal('1000'), stock_almacen=5,
        )
        antes.get_model('pedidos', 'ZonaEnvio').objects.create(nombre='Santiago', tarifa=Decimal('350'))
        antes.get_model('promociones', 'Cupon').objects.create(codigo='DIEZ', tipo='porcentaje', valor=Decimal('10'))
        antes.get_model('core', 'CuentaBancaria').objects.create(banco='Popular', numero='111', titular='Multimix')
        antes.get_model('pedidos', 'SecuenciaPedido').objects.create(anio=anio, ultimo=7)
        antes.get_model('pedidos', 'Pedido').objects.create(
            numero=f'MMX-{anio}-00007', nombre='Ana Pérez', telefono='8095551234', metodo_entrega='recoger',
            metodo_pago='transferencia', subtotal=Decimal('1000'), total=Decimal('1000'),
        )

        migrar_al_final()

        # A partir de aqui, los modelos de hoy.
        from catalogo.models import Producto
        from core.models import ConfiguracionTienda, CuentaBancaria
        from pedidos.models import Pedido, SecuenciaTienda, ZonaEnvio
        from pedidos.tests.utiles import pedido_de_prueba
        from promociones.models import Cupon
        from tiendas.models import Tienda

        tienda = Tienda.objects.get()
        self.assertEqual(
            (tienda.nombre, tienda.slug, tienda.prefijo, tienda.activa), ('Multimix RD', 'multimix-rd', 'MMX', True),
        )
        # La marca, los contactos y la forma de cobrar que eran del sitio quedan en la tienda.
        self.assertEqual(
            (tienda.whatsapp, tienda.horario, tienda.logo.name, tienda.direccion_tienda, tienda.banner_titulo),
            ('18095550123', 'Lun a Sáb', 'tienda/logo.png', 'Av. Winston Churchill #100', 'Tu tienda de bienestar'),
        )
        self.assertTrue(tienda.permitir_contra_entrega)
        self.assertEqual(ConfiguracionTienda.objects.get().whatsapp, '18095550123')

        for modelo in (Producto, Pedido, ZonaEnvio, Cupon, CuentaBancaria):
            self.assertEqual(list(modelo.objects.values_list('tienda_id', flat=True)), [tienda.pk], modelo.__name__)
        self.assertEqual(Pedido.objects.get().numero, f'MMX-{anio}-00007')

        # La numeracion de pedidos sigue donde iba.
        self.assertEqual(list(SecuenciaTienda.objects.values_list('tienda_id', 'anio', 'ultimo')), [(tienda.pk, anio, 7)])
        self.assertEqual(pedido_de_prueba(Producto.objects.get(), 1).numero, f'MMX-{anio}-00008')

    def test_una_instalacion_nueva_no_crea_tiendas(self):
        migrar(ANTES)
        migrar_al_final()

        from tiendas.models import Tienda

        self.assertFalse(Tienda.objects.exists())
