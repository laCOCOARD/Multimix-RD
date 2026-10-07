from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from catalogo.models import Producto
from catalogo.tests.test_modelos import crear_producto
from core.models import ConfiguracionTienda
from pedidos import services
from pedidos.models import DetallePedido, Pedido
from pedidos.services import PedidoError, StockInsuficiente, TransicionInvalida, cambiar_estado, crear_pedido
from promociones.models import Cupon
from tiendas.tests.utiles import tienda_de_prueba

from .utiles import carrito_con, cupon_de_prueba, datos_pedido, pedido_de_prueba, zona_de_prueba

Estado = Pedido.Estado
Entrega = Pedido.Entrega
Pago = Pedido.Pago


class BaseServicios(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), stock_almacen=10)
        # La misma instancia que usa el carrito de las pruebas: los cambios se ven sin recargar.
        self.tienda = self.producto.tienda
        self.zona = zona_de_prueba()

    def stock(self):
        self.producto.refresh_from_db()
        return self.producto.stock_almacen, self.producto.stock_reservado


class TotalesTests(BaseServicios):
    def test_recoger_no_paga_envio(self):
        totales = services.calcular_totales(carrito_con((self.producto, 2)), Entrega.RECOGER, self.zona)
        self.assertEqual(totales.costo_envio, Decimal('0.00'))
        self.assertEqual(totales.total, Decimal('2000.00'))

    def test_envio_suma_la_tarifa_de_la_zona(self):
        totales = services.calcular_totales(carrito_con((self.producto, 2)), Entrega.ENVIO, self.zona)
        self.assertEqual(totales.costo_envio, Decimal('250.00'))
        self.assertEqual(totales.total, Decimal('2250.00'))

    def test_el_descuento_no_aplica_al_envio(self):
        cupon_de_prueba('TODO', tipo=Cupon.Tipo.MONTO_FIJO, valor=Decimal('5000'))
        totales = services.calcular_totales(carrito_con((self.producto, 1), cupon='TODO'), Entrega.ENVIO, self.zona)
        self.assertEqual(totales.descuento, Decimal('1000.00'))
        self.assertEqual(totales.total, Decimal('250.00'))

    def test_metodos_de_pago_segun_entrega(self):
        tienda = self.tienda
        self.assertEqual(
            services.metodos_pago_disponibles(Entrega.RECOGER, tienda), [Pago.TRANSFERENCIA, Pago.EFECTIVO_RECOGER],
        )
        self.assertEqual(services.metodos_pago_disponibles(Entrega.ENVIO, tienda), [Pago.TRANSFERENCIA])
        tienda.permitir_contra_entrega = True
        self.assertEqual(
            services.metodos_pago_disponibles(Entrega.ENVIO, tienda), [Pago.TRANSFERENCIA, Pago.CONTRA_ENTREGA],
        )


class CrearPedidoTests(BaseServicios):
    def test_crea_pedido_y_reserva_stock(self):
        pedido = pedido_de_prueba(self.producto, 3)
        self.assertRegex(pedido.numero, rf'^MMX-{timezone.localdate().year}-\d{{5}}$')
        self.assertEqual(pedido.estado, Estado.PENDIENTE)
        self.assertEqual(pedido.total, Decimal('3000.00'))
        self.assertEqual(self.stock(), (10, 3))
        self.assertEqual(self.producto.stock_disponible, 7)
        detalle = pedido.detalles.get()
        self.assertEqual((detalle.nombre_producto, detalle.precio_unitario, detalle.subtotal),
                         ('Lámpara', Decimal('1000.00'), Decimal('3000.00')))

    def test_numeros_consecutivos(self):
        primero = pedido_de_prueba(self.producto, 1)
        segundo = pedido_de_prueba(self.producto, 1)
        self.assertEqual(int(segundo.numero[-5:]), int(primero.numero[-5:]) + 1)

    def test_el_detalle_conserva_el_precio_de_la_compra(self):
        pedido = pedido_de_prueba(self.producto, 1)
        Producto.objects.filter(pk=self.producto.pk).update(precio=Decimal('5000'), nombre='Otro nombre')
        detalle = pedido.detalles.get()
        self.assertEqual(detalle.precio_unitario, Decimal('1000.00'))
        self.assertEqual(detalle.nombre_producto, 'Lámpara')

    def test_usa_el_precio_de_oferta_vigente(self):
        Producto.objects.filter(pk=self.producto.pk).update(precio_oferta=Decimal('800'))
        self.producto.refresh_from_db()
        self.assertEqual(pedido_de_prueba(self.producto, 2).total, Decimal('1600.00'))

    def test_stock_insuficiente_no_crea_nada(self):
        carrito = carrito_con((self.producto, 5))
        Producto.objects.filter(pk=self.producto.pk).update(stock_almacen=3)
        with self.assertRaises(StockInsuficiente):
            crear_pedido(carrito, datos_pedido())
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(self.stock(), (3, 0))

    def test_lo_reservado_no_se_puede_volver_a_vender(self):
        pedido_de_prueba(self.producto, 8)
        carrito = carrito_con((self.producto, 2))
        carrito.items[str(self.producto.pk)] = 3
        with self.assertRaises(StockInsuficiente):
            crear_pedido(carrito, datos_pedido())

    def test_carrito_vacio_o_producto_inactivo(self):
        with self.assertRaises(PedidoError):
            crear_pedido(carrito_con(), datos_pedido())
        carrito = carrito_con((self.producto, 1))
        Producto.objects.filter(pk=self.producto.pk).update(activo=False)
        with self.assertRaises(PedidoError):
            crear_pedido(carrito, datos_pedido())

    def test_envio_requiere_zona_y_direccion(self):
        carrito = carrito_con((self.producto, 1))
        with self.assertRaises(PedidoError):
            crear_pedido(carrito, datos_pedido(metodo_entrega=Entrega.ENVIO, direccion='Calle 1'))
        with self.assertRaises(PedidoError):
            crear_pedido(carrito, datos_pedido(metodo_entrega=Entrega.ENVIO, zona=self.zona))
        pedido = crear_pedido(carrito, datos_pedido(
            metodo_entrega=Entrega.ENVIO, zona=self.zona, direccion='Calle 1 #5', referencia='Portón azul',
        ))
        self.assertEqual(pedido.costo_envio, Decimal('250.00'))
        self.assertEqual(pedido.total, Decimal('1250.00'))

    def test_zona_y_productos_deben_ser_de_la_tienda_del_carrito(self):
        otra = tienda_de_prueba('Otra tienda')
        zona_ajena = zona_de_prueba('Lejos', tienda=otra)
        ajeno = crear_producto(nombre='Ajeno', sku='A1', tienda=otra)
        carrito = carrito_con((self.producto, 1))
        with self.assertRaises(PedidoError):
            crear_pedido(carrito, datos_pedido(metodo_entrega=Entrega.ENVIO, zona=zona_ajena, direccion='Calle 1'))
        # Aunque alguien altere la sesion, un producto de otra tienda no entra al pedido ni reserva stock.
        carrito.items[str(ajeno.pk)] = 1
        with self.assertRaises(PedidoError):
            crear_pedido(carrito, datos_pedido())
        self.assertEqual(Pedido.objects.count(), 0)
        ajeno.refresh_from_db()
        self.assertEqual((ajeno.stock_reservado, self.stock()), (0, (10, 0)))

    def test_cada_tienda_lleva_su_numeracion(self):
        otra = tienda_de_prueba('Fitnes RD')
        ajeno = crear_producto(nombre='Pesas', sku='P1', tienda=otra)
        anio = timezone.localdate().year
        numeros = [pedido_de_prueba(producto, 1).numero for producto in (self.producto, ajeno, ajeno, self.producto)]
        self.assertEqual(numeros, [
            f'MMX-{anio}-00001', f'FIT-{anio}-00001', f'FIT-{anio}-00002', f'MMX-{anio}-00002',
        ])

    def test_recoger_ignora_zona_y_direccion(self):
        pedido = pedido_de_prueba(self.producto, 1, zona=self.zona, direccion='Calle 1')
        self.assertIsNone(pedido.zona)
        self.assertEqual(pedido.direccion, '')
        self.assertEqual(pedido.costo_envio, Decimal('0.00'))

    def test_formas_de_pago_no_permitidas(self):
        carrito = carrito_con((self.producto, 1))
        envio = {'metodo_entrega': Entrega.ENVIO, 'zona': self.zona, 'direccion': 'Calle 1'}
        with self.assertRaises(PedidoError):
            crear_pedido(carrito, datos_pedido(metodo_pago=Pago.EFECTIVO_RECOGER, **envio))
        with self.assertRaises(PedidoError):
            crear_pedido(carrito, datos_pedido(metodo_pago=Pago.CONTRA_ENTREGA, **envio))
        self.tienda.permitir_contra_entrega = True
        self.tienda.save()
        pedido = crear_pedido(carrito, datos_pedido(metodo_pago=Pago.CONTRA_ENTREGA, **envio))
        self.assertEqual(pedido.metodo_pago, Pago.CONTRA_ENTREGA)

    def test_cupon_se_aplica_y_cuenta_el_uso(self):
        cupon = cupon_de_prueba('DIEZ', usos_maximos=1)
        pedido = pedido_de_prueba(self.producto, 2, cupon='DIEZ')
        self.assertEqual((pedido.descuento, pedido.total, pedido.codigo_cupon),
                         (Decimal('200.00'), Decimal('1800.00'), 'DIEZ'))
        cupon.refresh_from_db()
        self.assertEqual(cupon.usos_actuales, 1)

    def test_cupon_agotado_entre_carrito_y_checkout(self):
        cupon_de_prueba('UNO', usos_maximos=1)
        carrito = carrito_con((self.producto, 1), cupon='UNO')
        pedido_de_prueba(self.producto, 1, cupon='UNO')
        with self.assertRaises(PedidoError):
            crear_pedido(carrito, datos_pedido())
        self.assertEqual(Pedido.objects.count(), 1)

    def test_aviso_de_transferencia_solo_con_ese_pago(self):
        pedido = pedido_de_prueba(self.producto, 1, transferencia_realizada=True, referencia_transferencia='ABC1')
        self.assertTrue(pedido.transferencia_realizada)
        self.assertEqual(pedido.estado, Estado.PENDIENTE)
        efectivo = pedido_de_prueba(
            self.producto, 1, metodo_pago=Pago.EFECTIVO_RECOGER, transferencia_realizada=True,
        )
        self.assertFalse(efectivo.transferencia_realizada)
        with self.assertRaises(PedidoError):
            services.marcar_transferencia(efectivo, 'X')

    def test_marcar_transferencia_no_cambia_el_estado(self):
        pedido = pedido_de_prueba(self.producto, 1)
        services.marcar_transferencia(pedido, ' REF-99 ')
        pedido.refresh_from_db()
        self.assertTrue(pedido.transferencia_realizada)
        self.assertEqual(pedido.referencia_transferencia, 'REF-99')
        self.assertEqual(pedido.estado, Estado.PENDIENTE)
        self.assertIsNone(pedido.fecha_pago)

    @override_settings(PEDIDOS_MAX_POR_IP=2)
    def test_limite_por_ip(self):
        carrito = carrito_con((self.producto, 1))
        self.assertFalse(services.supera_limite_por_ip('10.0.0.1'))
        crear_pedido(carrito, datos_pedido(), ip='10.0.0.1')
        crear_pedido(carrito, datos_pedido(), ip='10.0.0.1')
        self.assertTrue(services.supera_limite_por_ip('10.0.0.1'))
        self.assertFalse(services.supera_limite_por_ip('10.0.0.2'))


class TransicionesTests(BaseServicios):
    def envio(self, **cambios):
        return pedido_de_prueba(
            self.producto, 2, metodo_entrega=Entrega.ENVIO, zona=self.zona, direccion='Calle 1', **cambios,
        )

    def test_transferencia_debe_pasar_por_pagado(self):
        recoger = pedido_de_prueba(self.producto, 2)
        for destino in (Estado.LISTO, Estado.ENVIADO, Estado.ENTREGADO):
            with self.assertRaises(TransicionInvalida):
                cambiar_estado(recoger, destino)
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(self.envio(), Estado.ENVIADO)

    def test_flujo_transferencia_recoger(self):
        pedido = pedido_de_prueba(self.producto, 2)
        pedido = cambiar_estado(pedido, Estado.PAGADO)
        self.assertIsNotNone(pedido.fecha_pago)
        self.assertEqual(self.stock(), (10, 2))
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(pedido, Estado.ENVIADO)
        pedido = cambiar_estado(pedido, Estado.LISTO)
        self.assertEqual(self.stock(), (10, 2))
        pedido = cambiar_estado(pedido, Estado.ENTREGADO)
        self.assertIsNotNone(pedido.fecha_entrega)
        self.assertTrue(pedido.stock_descontado)
        self.assertEqual(self.stock(), (8, 0))

    def test_flujo_transferencia_envio_descuenta_una_sola_vez(self):
        pedido = cambiar_estado(self.envio(), Estado.PAGADO)
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(pedido, Estado.LISTO)
        pedido = cambiar_estado(pedido, Estado.ENVIADO)
        self.assertEqual(self.stock(), (8, 0))
        pedido = cambiar_estado(pedido, Estado.ENTREGADO)
        self.assertEqual(self.stock(), (8, 0))

    def test_efectivo_avanza_sin_pagado_y_queda_pagado_al_entregar(self):
        pedido = pedido_de_prueba(self.producto, 2, metodo_pago=Pago.EFECTIVO_RECOGER)
        pedido = cambiar_estado(pedido, Estado.LISTO)
        self.assertIsNone(pedido.fecha_pago)
        self.assertFalse(pedido.esta_pagado)
        pedido = cambiar_estado(pedido, Estado.ENTREGADO)
        self.assertTrue(pedido.esta_pagado)
        self.assertEqual(self.stock(), (8, 0))

    def test_contra_entrega_puede_enviarse_sin_pagar(self):
        self.tienda.permitir_contra_entrega = True
        self.tienda.save()
        pedido = cambiar_estado(self.envio(metodo_pago=Pago.CONTRA_ENTREGA), Estado.ENVIADO)
        self.assertIsNone(pedido.fecha_pago)
        self.assertEqual(self.stock(), (8, 0))
        pedido = cambiar_estado(pedido, Estado.ENTREGADO)
        self.assertIsNotNone(pedido.fecha_pago)

    def test_cancelar_libera_reserva_y_devuelve_cupon(self):
        cupon = cupon_de_prueba('DIEZ')
        for previos in ([], [Estado.PAGADO], [Estado.PAGADO, Estado.LISTO]):
            pedido = pedido_de_prueba(self.producto, 2, cupon='DIEZ')
            for estado in previos:
                pedido = cambiar_estado(pedido, estado)
            self.assertEqual(self.stock(), (10, 2))
            pedido = cambiar_estado(pedido, Estado.CANCELADO)
            self.assertEqual(self.stock(), (10, 0))
            cupon.refresh_from_db()
            self.assertEqual(cupon.usos_actuales, 0)

    def test_no_se_cancela_lo_enviado_ni_lo_entregado(self):
        enviado = cambiar_estado(cambiar_estado(self.envio(), Estado.PAGADO), Estado.ENVIADO)
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(enviado, Estado.CANCELADO)
        entregado = cambiar_estado(enviado, Estado.ENTREGADO)
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(entregado, Estado.CANCELADO)

    def test_estados_finales_no_cambian(self):
        cancelado = cambiar_estado(pedido_de_prueba(self.producto, 1), Estado.CANCELADO)
        for destino in Estado.values:
            with self.assertRaises(TransicionInvalida):
                cambiar_estado(cancelado, destino)

    def test_usa_el_estado_actual_de_la_base(self):
        pedido = pedido_de_prueba(self.producto, 1)
        cambiar_estado(pedido, Estado.CANCELADO)
        # `pedido` quedo desactualizado en memoria: debe mandar lo que hay en la base.
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(pedido, Estado.PAGADO)
        self.assertEqual(self.stock(), (10, 0))


class EliminarPedidoTests(BaseServicios):
    def test_pedido_activo_libera_reserva_y_devuelve_cupon(self):
        cupon = cupon_de_prueba('DIEZ')
        for previos in ([], [Estado.PAGADO], [Estado.PAGADO, Estado.LISTO]):
            pedido = pedido_de_prueba(self.producto, 2, cupon='DIEZ')
            for estado in previos:
                pedido = cambiar_estado(pedido, estado)
            self.assertEqual(services.eliminar_pedido(pedido), pedido.numero)
            self.assertFalse(Pedido.objects.exists())
            self.assertEqual(self.stock(), (10, 0))
            cupon.refresh_from_db()
            self.assertEqual(cupon.usos_actuales, 0)

    def test_enviado_o_entregado_no_devuelve_stock_ni_cupon(self):
        cupon = cupon_de_prueba('DIEZ')
        enviado = pedido_de_prueba(
            self.producto, 2, cupon='DIEZ', metodo_entrega=Entrega.ENVIO, zona=self.zona, direccion='Calle 1',
        )
        enviado = cambiar_estado(cambiar_estado(enviado, Estado.PAGADO), Estado.ENVIADO)
        entregado = cambiar_estado(pedido_de_prueba(self.producto, 1, cupon='DIEZ'), Estado.PAGADO)
        entregado = cambiar_estado(entregado, Estado.ENTREGADO)
        self.assertEqual(self.stock(), (7, 0))

        services.eliminar_pedido(enviado)
        services.eliminar_pedido(entregado)

        self.assertFalse(Pedido.objects.exists())
        self.assertFalse(DetallePedido.objects.exists())
        self.assertEqual(self.stock(), (7, 0))
        cupon.refresh_from_db()
        self.assertEqual(cupon.usos_actuales, 2)

    def test_cancelado_no_libera_la_reserva_otra_vez(self):
        otro = pedido_de_prueba(self.producto, 3)
        cancelado = cambiar_estado(pedido_de_prueba(self.producto, 2), Estado.CANCELADO)
        services.eliminar_pedido(cancelado)
        self.assertEqual(self.stock(), (10, 3))
        self.assertEqual(list(Pedido.objects.all()), [otro])

    def test_el_numero_eliminado_no_se_reutiliza(self):
        primero = pedido_de_prueba(self.producto, 1)
        services.eliminar_pedido(primero)
        segundo = pedido_de_prueba(self.producto, 1)
        self.assertEqual(int(segundo.numero[-5:]), int(primero.numero[-5:]) + 1)


class PedidosVencidosTests(BaseServicios):
    def test_comando_cancela_solo_pendientes_viejos(self):
        viejo = pedido_de_prueba(self.producto, 2)
        pagado = cambiar_estado(pedido_de_prueba(self.producto, 1), Estado.PAGADO)
        reciente = pedido_de_prueba(self.producto, 1)
        hace_49_horas = timezone.now() - timedelta(hours=49)
        Pedido.objects.filter(pk__in=[viejo.pk, pagado.pk]).update(creado=hace_49_horas)

        salida = StringIO()
        call_command('cancelar_pedidos_vencidos', stdout=salida)

        self.assertIn(viejo.numero, salida.getvalue())
        estados = dict(Pedido.objects.values_list('pk', 'estado'))
        self.assertEqual(estados[viejo.pk], Estado.CANCELADO)
        self.assertEqual(estados[pagado.pk], Estado.PAGADO)
        self.assertEqual(estados[reciente.pk], Estado.PENDIENTE)
        self.assertEqual(self.stock(), (10, 2))

    def test_respeta_las_horas_configuradas(self):
        pedido = pedido_de_prueba(self.producto, 1)
        Pedido.objects.filter(pk=pedido.pk).update(creado=timezone.now() - timedelta(hours=10))
        self.assertEqual(services.cancelar_pedidos_vencidos(), [])
        config = ConfiguracionTienda.obtener()
        config.horas_vencimiento_pedido = 6
        config.save()
        self.assertEqual(services.cancelar_pedidos_vencidos(), [pedido.numero])
