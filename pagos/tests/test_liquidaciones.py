from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto
from pagos import liquidaciones
from pagos.models import Liquidacion
from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import cupon_de_prueba, pedido_de_prueba, zona_de_prueba
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

D = Decimal
CLAVE = 'clave-segura-123'
Estado = Pedido.Estado


def entregado(producto, cantidad=1, **cambios):
    pedido = pedido_de_prueba(producto, cantidad, **cambios)
    if pedido.estado == Estado.PENDIENTE and pedido.paga_por_transferencia:
        cambiar_estado(pedido, Estado.PAGADO)
    return cambiar_estado(pedido, Estado.ENTREGADO)


class SaldoTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba(comision_porcentaje=D('10'))
        self.producto = crear_producto(nombre='Lámpara', precio=D('1000'))

    def test_el_sitio_cobro_la_transferencia_y_le_deposita_menos_su_comision(self):
        entregado(self.producto, 2)
        saldo = liquidaciones.saldo_de(self.tienda)
        self.assertEqual((saldo.ventas, saldo.cobrado_por_el_sitio, saldo.comision, saldo.monto),
                         (D('2000.00'), D('2000.00'), D('200.00'), D('1800.00')))

    def test_la_comision_es_sobre_los_productos_no_sobre_el_envio_ni_el_descuento(self):
        cupon_de_prueba('DIEZ')
        entregado(self.producto, 2, cupon='DIEZ', metodo_entrega=Pedido.Entrega.ENVIO, zona=zona_de_prueba(),
                  sector='Naco', direccion='Calle 1')
        saldo = liquidaciones.saldo_de(self.tienda)
        # 2,000 - 200 de cupon = 1,800 en productos; comision 180. El envio (250) va completo a la tienda.
        self.assertEqual((saldo.ventas, saldo.comision, saldo.monto), (D('2050.00'), D('180.00'), D('1870.00')))
        self.assertEqual((saldo.productos, saldo.envios), (D('1800.00'), D('250.00')))
        # El cliente deposito 2,050 (productos + envio). La tienda recibe sus productos menos la comision (1,620)
        # y el envio completo (250).
        self.assertEqual(saldo.monto, (saldo.productos - saldo.comision) + saldo.envios)

    def test_el_efectivo_lo_cobra_la_tienda_y_debe_la_comision(self):
        entregado(self.producto, 1, metodo_pago=Pedido.Pago.EFECTIVO_RECOGER)
        saldo = liquidaciones.saldo_de(self.tienda)
        self.assertEqual((saldo.cobrado_por_el_sitio, saldo.comision, saldo.monto), (D('0.00'), D('100.00'), D('-100.00')))

    def test_un_pedido_de_antes_transferido_a_la_tienda_solo_debe_la_comision(self):
        pedido = entregado(self.producto, 3)
        Pedido.objects.filter(pk=pedido.pk).update(cobra_el_sitio=False)
        saldo = liquidaciones.saldo_de(self.tienda)
        self.assertEqual((saldo.cobrado_por_el_sitio, saldo.monto), (D('0.00'), D('-300.00')))

    def test_toda_transferencia_la_cobra_el_sitio(self):
        self.assertTrue(entregado(self.producto, 1).cobra_el_sitio)
        self.assertFalse(entregado(self.producto, 1, metodo_pago=Pedido.Pago.EFECTIVO_RECOGER).cobra_el_sitio)

    def test_el_efectivo_va_aparte_no_se_deposita_pero_paga_comision(self):
        transferido = entregado(self.producto, 2)
        efectivo = entregado(self.producto, 1, metodo_pago=Pedido.Pago.EFECTIVO_RECOGER)
        saldo = liquidaciones.saldo_de(self.tienda)
        self.assertEqual(saldo.del_sitio.pedidos, [transferido])
        self.assertEqual((saldo.del_sitio.ventas, saldo.del_sitio.comision, saldo.del_sitio.neto),
                         (D('2000.00'), D('200.00'), D('1800.00')))
        self.assertEqual(saldo.de_la_tienda.pedidos, [efectivo])
        self.assertEqual((saldo.de_la_tienda.ventas, saldo.de_la_tienda.comision), (D('1000.00'), D('100.00')))
        # Se le deposita lo transferido menos toda la comision: 1,800 - 100 del efectivo.
        self.assertEqual(saldo.monto, D('1700.00'))
        liquidacion = liquidaciones.liquidar(self.tienda)
        self.assertEqual(
            (liquidacion.cobrado_por_el_sitio, liquidacion.cobrado_por_la_tienda,
             liquidacion.comision_de_lo_cobrado_por_la_tienda, liquidacion.monto),
            (D('2000.00'), D('1000.00'), D('100.00'), D('1700.00')),
        )

    def test_cada_tienda_con_su_porcentaje(self):
        otra = tienda_de_prueba('Fitnes RD', comision_porcentaje=D('25'))
        entregado(self.producto, 1)
        entregado(crear_producto(sku='P1', precio=D('1000'), tienda=otra), 1)
        self.assertEqual(liquidaciones.saldo_de(self.tienda).monto, D('900.00'))
        self.assertEqual(liquidaciones.saldo_de(otra).monto, D('750.00'))

    def test_solo_cuenta_lo_cobrado_y_entregado(self):
        pedido_de_prueba(self.producto, 1)                                   # pendiente
        cambiar_estado(pedido_de_prueba(self.producto, 1), Estado.PAGADO)    # cobrado, sin entregar
        cancelado = cambiar_estado(pedido_de_prueba(self.producto, 1), Estado.PAGADO)
        cambiar_estado(cancelado, Estado.CANCELADO)
        saldo = liquidaciones.saldo_de(self.tienda)
        self.assertEqual((saldo.pedidos, saldo.monto), ([], D('0.00')))
        self.assertEqual((saldo.pedidos_en_curso, saldo.en_curso), (1, D('1000.00')))
        with self.assertRaises(liquidaciones.LiquidacionError):
            liquidaciones.liquidar(self.tienda)

    def test_liquidar_marca_los_pedidos_y_no_los_paga_dos_veces(self):
        admin = get_user_model().objects.create_superuser('admin', 'a@example.com', CLAVE)
        pedido = entregado(self.producto, 2)
        liquidacion = liquidaciones.liquidar(self.tienda, admin, 'Transferencia 4471')
        self.assertEqual(
            (liquidacion.monto, liquidacion.comision, liquidacion.comision_porcentaje, liquidacion.pedidos_incluidos,
             liquidacion.creada_por, liquidacion.nota),
            (D('1800.00'), D('200.00'), D('10.00'), 1, admin, 'Transferencia 4471'),
        )
        pedido.refresh_from_db()
        self.assertEqual((pedido.liquidacion, pedido.monto_liquidado), (liquidacion, D('1800.00')))
        self.assertFalse(liquidaciones.saldo_de(self.tienda).hay_movimientos)
        with self.assertRaises(liquidaciones.LiquidacionError):
            liquidaciones.liquidar(self.tienda, admin)

        # Cambiar el porcentaje despues no altera lo ya liquidado; aplica a lo siguiente.
        self.tienda.comision_porcentaje = D('20')
        self.tienda.save()
        entregado(self.producto, 1)
        self.assertEqual(liquidaciones.saldo_de(self.tienda).monto, D('800.00'))
        liquidacion.refresh_from_db()
        self.assertEqual(liquidacion.monto, D('1800.00'))

    def test_la_comision_del_banco_la_paga_el_sitio_y_no_la_tienda(self):
        entregado(self.producto, 2)  # saldo a depositar: 1800
        liquidacion = liquidaciones.liquidar(self.tienda, costo_transferencia='150')
        # Queda anotada como gasto del sitio, pero la tienda recibe su saldo completo.
        self.assertEqual((liquidacion.costo_transferencia, liquidacion.monto), (D('150.00'), D('1800.00')))

    def test_la_comision_de_la_transferencia_tiene_que_ser_un_monto_valido(self):
        entregado(self.producto, 1)  # saldo a depositar: 900
        for malo in ('-5', 'abc'):
            with self.assertRaises(liquidaciones.LiquidacionError):
                liquidaciones.liquidar(self.tienda, costo_transferencia=malo)
        self.assertFalse(Liquidacion.objects.exists())
        self.assertEqual(liquidaciones.liquidar(self.tienda, costo_transferencia='').costo_transferencia, D('0.00'))

    def test_un_reembolso_de_algo_ya_depositado_se_descuenta_en_la_siguiente(self):
        devuelto = entregado(self.producto, 1)
        liquidaciones.liquidar(self.tienda)
        cambiar_estado(devuelto, Estado.REEMBOLSADO)
        entregado(self.producto, 2)
        saldo = liquidaciones.saldo_de(self.tienda)
        self.assertEqual((saldo.ajustes, saldo.monto), (D('900.00'), D('900.00')))  # 1,800 nuevos - 900 ya depositados
        liquidaciones.liquidar(self.tienda)
        self.assertFalse(liquidaciones.saldo_de(self.tienda).hay_movimientos)


class PanelDeLiquidacionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_superuser('admin', 'a@example.com', CLAVE)
        cls.propia = tienda_de_prueba(comision_porcentaje=D('10'))
        cls.ajena = tienda_de_prueba('Fitnes RD', comision_porcentaje=D('20'))
        cls.vendedor = Usuario.objects.create_user('vendedor', password=CLAVE)
        cls.propia.usuarios.add(cls.vendedor)
        dar_acceso_al_panel([cls.vendedor])
        entregado(crear_producto(sku='L1', precio=D('1000')), 1)
        entregado(crear_producto(sku='P1', precio=D('1000'), tienda=cls.ajena), 1)
        cls.saldos = reverse('admin:pagos_liquidacion_saldos')

    def test_el_administrador_ve_el_saldo_de_cada_tienda_y_liquida(self):
        self.client.force_login(self.admin)
        pagina = self.client.get(self.saldos)
        self.assertEqual({s.tienda.nombre: s.monto for s in pagina.context['saldos']},
                         {'Multimix RD': D('900.00'), 'Fitnes RD': D('800.00')})
        self.assertContains(pagina, 'RD$ 900.00')
        respuesta = self.client.post(
            reverse('admin:pagos_liquidacion_liquidar', args=[self.propia.pk]),
            {'nota': 'Dep. 123', 'costo_transferencia': '100'}, follow=True,
        )
        self.assertContains(respuesta, 'RD$ 900.00 depositados')
        self.assertContains(respuesta, 'Comisión del banco anotada como gasto tuyo: RD$ 100.00')
        liquidacion = Liquidacion.objects.get()
        self.assertEqual((liquidacion.tienda, liquidacion.monto, liquidacion.creada_por), (self.propia, D('900.00'), self.admin))
        self.assertEqual(self.client.get(reverse('admin:pagos_liquidacion_liquidar', args=[self.propia.pk])).status_code, 405)

    def test_el_vendedor_no_ve_saldos_ni_liquida_pero_si_sus_liquidaciones(self):
        liquidaciones.liquidar(self.propia)
        liquidaciones.liquidar(self.ajena)
        self.client.force_login(self.vendedor)
        self.assertEqual(self.client.get(self.saldos).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:pagos_liquidacion_liquidar', args=[self.propia.pk])).status_code, 403)
        lista = self.client.get(reverse('admin:pagos_liquidacion_changelist'))
        self.assertEqual([l.tienda for l in lista.context['cl'].queryset], [self.propia])
        self.assertNotContains(lista, 'Saldos por tienda')
        # Lo que cobra el banco por el deposito es gasto del sitio: el vendedor no lo ve en su liquidacion.
        detalle = self.client.get(reverse('admin:pagos_liquidacion_change', args=[lista.context['cl'].queryset[0].pk]))
        self.assertEqual(detalle.status_code, 200)
        self.assertNotContains(detalle, 'comisión de la transferencia', status_code=200)

    def test_el_vendedor_no_puede_ver_ni_cambiar_su_comision(self):
        self.client.force_login(self.vendedor)
        editar = reverse('admin:tiendas_tienda_change', args=[self.propia.pk])
        self.assertNotContains(self.client.get(editar), 'comision_porcentaje')
        self.client.post(editar, {
            'nombre': 'Multimix RD', 'banner_titulo': '', 'banner_subtitulo': '', 'banner_texto_boton': 'Ver catálogo',
            'whatsapp': '', 'telefono': '', 'correo': '', 'horario': '', 'direccion_tienda': '', 'facebook': '',
            'instagram': '', 'tiktok': '', 'itbis_porcentaje': '0', 'comision_porcentaje': '0',
        })
        self.propia.refresh_from_db()
        self.assertEqual(self.propia.comision_porcentaje, D('10.00'))

    def test_el_administrador_cambia_el_porcentaje_de_cada_tienda_por_separado(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('admin:tiendas_tienda_changelist')), 'Tu comisión')
        editar = reverse('admin:tiendas_tienda_change', args=[self.ajena.pk])
        self.assertContains(self.client.get(editar), 'comision_porcentaje')
        self.client.post(editar, {
            'nombre': 'Fitnes RD', 'slug': self.ajena.slug, 'activa': 'on', 'orden': '0', 'banner_titulo': '',
            'banner_subtitulo': '', 'banner_texto_boton': 'Ver catálogo', 'whatsapp': '', 'telefono': '', 'correo': '',
            'horario': '', 'direccion_tienda': '', 'facebook': '', 'instagram': '', 'tiktok': '',
            'itbis_porcentaje': '0', 'comision_porcentaje': '15',
        })
        self.ajena.refresh_from_db()
        self.propia.refresh_from_db()
        self.assertEqual((self.ajena.comision_porcentaje, self.propia.comision_porcentaje), (D('15.00'), D('10.00')))

    def test_reporte_de_ventas_de_una_sola_tienda(self):
        self.client.force_login(self.admin)
        url = reverse('admin:pedidos_pedido_reporte')
        self.assertEqual(self.client.get(url).context['reporte']['cobrado'], D('2000.00'))
        self.assertEqual(self.client.get(url, {'tienda': self.ajena.pk}).context['reporte']['cobrado'], D('1000.00'))
        # El vendedor no puede pedir el reporte de una tienda que no es suya.
        self.client.force_login(self.vendedor)
        self.assertEqual(self.client.get(url, {'tienda': self.ajena.pk}).context['reporte']['cobrado'], D('1000.00'))
        self.assertIsNone(self.client.get(url, {'tienda': self.ajena.pk}).context['tienda_elegida'])
