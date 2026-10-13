from decimal import Decimal
from importlib import import_module

import tablib
from django.apps import apps
from django.conf import settings
from django.test import TestCase

from carrito.carrito import CarritoError
from catalogo.models import Disponibilidad, Producto
from catalogo.resources import COLUMNAS, ProductoResource
from catalogo.services import filtrar_catalogo
from core.panel import resumen_panel
from pedidos.models import Pedido
from pedidos.services import PedidoError, cambiar_estado, crear_pedido
from pedidos.tests.utiles import carrito_con, datos_pedido, pedido_de_prueba
from tiendas.tests.utiles import ruta, tienda_de_prueba

from .test_modelos import crear_producto


def sin_inventario(**datos):
    """Producto como los de una tienda que no cuenta unidades: stock en cero y sin llevar inventario."""
    return crear_producto(controla_stock=False, stock_almacen=0, **datos)


class DisponibilidadTests(TestCase):
    def test_sin_inventario_se_compra_aunque_el_stock_sea_cero(self):
        producto = sin_inventario()
        self.assertTrue(producto.se_puede_comprar)
        self.assertFalse(producto.agotado)
        self.assertFalse(producto.stock_bajo)
        self.assertEqual(producto.estado_venta, Disponibilidad.DISPONIBLE)
        self.assertEqual(producto.limite_compra, settings.CARRITO_MAX_POR_PRODUCTO)

    def test_bajo_pedido_se_compra_y_se_anuncia(self):
        producto = sin_inventario(disponibilidad=Disponibilidad.BAJO_PEDIDO)
        self.assertTrue(producto.se_puede_comprar)
        self.assertTrue(producto.bajo_pedido)

    def test_agotado_y_no_disponible_no_se_compran(self):
        for valor in (Disponibilidad.AGOTADO, Disponibilidad.NO_DISPONIBLE):
            producto = sin_inventario(sku=valor, disponibilidad=valor)
            self.assertFalse(producto.se_puede_comprar, valor)
            self.assertEqual(producto.estado_venta, valor)
            self.assertEqual(producto.limite_compra, 0)

    def test_con_inventario_sin_unidades_se_ve_agotado(self):
        producto = crear_producto(stock_almacen=0)
        self.assertFalse(producto.se_puede_comprar)
        self.assertEqual(producto.estado_venta, Disponibilidad.AGOTADO)

    def test_el_vendedor_puede_apagar_un_producto_con_stock(self):
        producto = crear_producto(stock_almacen=10, disponibilidad=Disponibilidad.NO_DISPONIBLE)
        self.assertFalse(producto.se_puede_comprar)
        self.assertEqual(producto.estado_venta, Disponibilidad.NO_DISPONIBLE)

    def test_filtro_solo_disponibles(self):
        sin_inventario(sku='SI')
        sin_inventario(sku='PEDIDO', disponibilidad=Disponibilidad.BAJO_PEDIDO)
        sin_inventario(sku='NO', disponibilidad=Disponibilidad.AGOTADO)
        crear_producto(sku='VACIO', stock_almacen=0)
        crear_producto(sku='LLENO', stock_almacen=4)
        skus = {p.sku for p in filtrar_catalogo({'disponibles': True}, tienda=tienda_de_prueba())}
        self.assertEqual(skus, {'SI', 'PEDIDO', 'LLENO'})


class CarritoSinInventarioTests(TestCase):
    def test_agrega_hasta_el_tope_por_producto(self):
        producto = sin_inventario()
        carrito = carrito_con((producto, 3))
        self.assertEqual(carrito.cantidad_de(producto.pk), 3)
        final, ajustada = carrito.agregar(producto, 500)
        self.assertEqual((final, ajustada), (settings.CARRITO_MAX_POR_PRODUCTO, True))

    def test_no_agrega_lo_que_no_esta_en_venta(self):
        agotado = sin_inventario(sku='A', nombre='Taza', disponibilidad=Disponibilidad.AGOTADO)
        apagado = sin_inventario(sku='B', nombre='Vaso', disponibilidad=Disponibilidad.NO_DISPONIBLE)
        carrito = carrito_con()
        with self.assertRaisesMessage(CarritoError, 'agotado'):
            carrito.agregar(agotado)
        with self.assertRaisesMessage(CarritoError, 'no está disponible por ahora'):
            carrito.agregar(apagado)

    def test_sincronizar_quita_lo_que_dejo_de_venderse(self):
        producto = sin_inventario(nombre='Taza')
        carrito = carrito_con((producto, 2))
        Producto.objects.filter(pk=producto.pk).update(disponibilidad=Disponibilidad.NO_DISPONIBLE)
        avisos = carrito.sincronizar()
        self.assertEqual(len(carrito), 0)
        self.assertIn('no está disponible por ahora', avisos[0])

    def test_la_ficha_ofrece_comprar(self):
        producto = sin_inventario(nombre='Taza')
        respuesta = self.client.get(producto.get_absolute_url())
        self.assertContains(respuesta, 'Agregar al carrito')
        self.assertNotContains(respuesta, 'Agotado')
        self.assertContains(respuesta, f'max="{settings.CARRITO_MAX_POR_PRODUCTO}"')

        Producto.objects.filter(pk=producto.pk).update(disponibilidad=Disponibilidad.BAJO_PEDIDO)
        respuesta = self.client.get(producto.get_absolute_url())
        self.assertContains(respuesta, 'Bajo pedido')
        self.assertContains(respuesta, 'Agregar al carrito')

        Producto.objects.filter(pk=producto.pk).update(disponibilidad=Disponibilidad.NO_DISPONIBLE)
        respuesta = self.client.get(producto.get_absolute_url())
        self.assertContains(respuesta, 'Temporalmente no disponible')
        self.assertNotContains(respuesta, 'Agregar al carrito')

    def test_agregar_desde_la_tienda(self):
        producto = sin_inventario()
        self.client.post(ruta('carrito:agregar'), {'producto_id': producto.pk, 'cantidad': 2})
        self.assertContains(self.client.get(ruta('carrito:detalle')), producto.nombre)


class PedidoSinInventarioTests(TestCase):
    def test_el_pedido_no_aparta_ni_descuenta_stock(self):
        producto = sin_inventario()
        pedido = pedido_de_prueba(producto, 3, metodo_pago=Pedido.Pago.EFECTIVO_RECOGER)
        producto.refresh_from_db()
        self.assertEqual((producto.stock_almacen, producto.stock_reservado), (0, 0))
        self.assertFalse(pedido.detalles.get().reserva_stock)
        self.assertEqual(pedido.total, Decimal('3000.00'))

        cambiar_estado(pedido, Pedido.Estado.ENTREGADO)
        producto.refresh_from_db()
        self.assertEqual((producto.stock_almacen, producto.stock_reservado), (0, 0))

    def test_cancelar_no_libera_reservas_de_otros_pedidos(self):
        """El producto empieza a llevar inventario despues: el pedido viejo no aparto nada y no libera nada."""
        producto = sin_inventario()
        viejo = pedido_de_prueba(producto, 2)
        Producto.objects.filter(pk=producto.pk).update(controla_stock=True, stock_almacen=10)
        producto.refresh_from_db()
        pedido_de_prueba(producto, 4)
        cambiar_estado(viejo, Pedido.Estado.CANCELADO)
        producto.refresh_from_db()
        self.assertEqual((producto.stock_almacen, producto.stock_reservado), (10, 4))

    def test_pedido_mixto_solo_aparta_lo_que_lleva_inventario(self):
        contado = crear_producto(sku='CON', stock_almacen=5)
        libre = sin_inventario(sku='SIN')
        pedido = crear_pedido(carrito_con((contado, 2), (libre, 7)), datos_pedido())
        contado.refresh_from_db()
        libre.refresh_from_db()
        self.assertEqual((contado.stock_reservado, libre.stock_reservado), (2, 0))
        self.assertEqual(
            dict(pedido.detalles.values_list('producto__sku', 'reserva_stock')), {'CON': True, 'SIN': False},
        )

    def test_no_se_confirma_si_dejo_de_venderse(self):
        producto = sin_inventario(nombre='Taza')
        carrito = carrito_con((producto, 1))
        Producto.objects.filter(pk=producto.pk).update(disponibilidad=Disponibilidad.NO_DISPONIBLE)
        with self.assertRaises(PedidoError) as error:
            crear_pedido(carrito, datos_pedido())
        self.assertIn('no está disponible por ahora', error.exception.mensaje)
        self.assertFalse(Pedido.objects.exists())

    def test_el_resumen_del_panel_no_cuenta_como_agotado_lo_que_no_lleva_inventario(self):
        sin_inventario(sku='LIBRE')
        sin_inventario(sku='MARCADO', disponibilidad=Disponibilidad.AGOTADO)
        crear_producto(sku='VACIO', stock_almacen=0)
        crear_producto(sku='POCO', stock_almacen=2)
        resumen = resumen_panel()
        self.assertEqual({p.sku for p in resumen['agotados']}, {'MARCADO', 'VACIO'})
        self.assertEqual({p.sku for p in resumen['stock_bajo']}, {'POCO'})


class MigracionDeDisponibilidadTests(TestCase):
    def test_solo_sigue_con_inventario_la_tienda_que_tenia_unidades(self):
        con_unidades = tienda_de_prueba()
        en_cero = tienda_de_prueba('Fitnes RD')
        crear_producto(sku='A', stock_almacen=5, controla_stock=False)
        crear_producto(sku='B', stock_almacen=0, controla_stock=False)
        crear_producto(sku='C', stock_almacen=0, controla_stock=False, tienda=en_cero)

        migracion = import_module('catalogo.migrations.0008_inventario_donde_ya_se_usaba')
        migracion.conservar_inventario(apps, None)

        self.assertEqual(Producto.objects.filter(tienda=con_unidades, controla_stock=True).count(), 2)
        producto = Producto.objects.get(tienda=en_cero)
        self.assertFalse(producto.controla_stock)
        self.assertTrue(producto.se_puede_comprar)


    def test_en_una_tienda_sin_pedidos_el_cero_no_es_un_agotado(self):
        """La tienda cargo unidades a un producto antes de migrar: los demas no deben quedar agotados."""
        nueva = tienda_de_prueba('Fitnes RD')
        crear_producto(sku='CARGADO', stock_almacen=500, tienda=nueva)
        crear_producto(sku='CERO', stock_almacen=0, tienda=nueva)
        vendido = crear_producto(sku='VENDIDO', stock_almacen=2)
        crear_producto(sku='AGOTADO', stock_almacen=0)
        pedido_de_prueba(vendido, 1)

        migracion = import_module('catalogo.migrations.0009_sin_inventario_si_nunca_se_cargo')
        migracion.soltar_inventario_vacio(apps, None)

        inventario = dict(Producto.objects.values_list('sku', 'controla_stock'))
        self.assertEqual(inventario, {'CARGADO': True, 'CERO': False, 'VENDIDO': True, 'AGOTADO': True})
        self.assertTrue(Producto.objects.get(sku='CERO').se_puede_comprar)


class ImportarDisponibilidadTests(TestCase):
    def test_el_excel_trae_disponibilidad_e_inventario(self):
        tienda = tienda_de_prueba()
        crear_producto(sku='BASE')
        datos = tablib.Dataset(headers=COLUMNAS)
        datos.append(['P-1', 'Proteína', 'General', '', '900', '', '', '', 'bajo_pedido', 0, 0, 0, 0, 1, 'Nutrilite'])
        datos.append(['P-2', 'Creatina', 'General', '', '700', '', '', '', 'disponible', 1, 12, 0, 0, 1, ''])
        resultado = ProductoResource(tienda=tienda).import_data(datos, dry_run=False)
        self.assertFalse(resultado.has_errors() or resultado.has_validation_errors())
        proteina, creatina = Producto.objects.get(sku='P-1'), Producto.objects.get(sku='P-2')
        self.assertTrue(proteina.bajo_pedido)
        self.assertEqual(proteina.marca, 'Nutrilite')
        self.assertEqual((creatina.controla_stock, creatina.stock_disponible), (True, 12))

    def test_rechaza_una_disponibilidad_que_no_existe(self):
        crear_producto(sku='BASE')
        datos = tablib.Dataset(headers=COLUMNAS)
        datos.append(['P-1', 'Proteína', 'General', '', '900', '', '', '', 'quizas', 0, 0, 0, 0, 1, ''])
        resultado = ProductoResource(tienda=tienda_de_prueba()).import_data(datos, dry_run=True)
        self.assertTrue(resultado.has_validation_errors())
