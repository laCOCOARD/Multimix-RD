from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.tests.test_modelos import crear_producto
from core.models import ConfiguracionTienda
from core.panel import resumen_panel
from pagos.models import Pago
from pedidos import services
from pedidos.models import Pedido, SolicitudDevolucion
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

from .utiles import pedido_de_prueba, zona_de_prueba

Estado = Pedido.Estado


class SeguimientoTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), stock_almacen=5)

    def envio(self, **cambios):
        return pedido_de_prueba(
            self.producto, 2, metodo_entrega=Pedido.Entrega.ENVIO, zona=zona_de_prueba(), sector='Naco',
            direccion='Calle 1', **cambios,
        )

    def test_recorrido_de_un_envio_y_su_historial(self):
        # Quien marca Pagado una transferencia es el administrador principal.
        vendedor = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'clave-segura-123')
        pedido = self.envio()
        for estado in (Estado.PAGADO, Estado.PREPARANDO, Estado.ENVIADO, Estado.EN_REPARTO, Estado.ENTREGADO):
            self.assertIn(estado, services.transiciones_permitidas(pedido))
            pedido = services.cambiar_estado(pedido, estado, usuario=vendedor)
        self.assertEqual(
            [(e.estado, e.usuario) for e in pedido.eventos.all()],
            [('pendiente', None), ('pagado', vendedor), ('preparando', vendedor), ('enviado', vendedor),
             ('en_reparto', vendedor), ('entregado', vendedor)],
        )
        self.producto.refresh_from_db()
        self.assertEqual((self.producto.stock_almacen, self.producto.stock_reservado), (3, 0))

    def test_no_se_salta_a_estados_que_no_tocan(self):
        pedido = pedido_de_prueba(self.producto, 1)  # recoge en tienda y paga por transferencia
        for estado in (Estado.PREPARANDO, Estado.EN_REPARTO, Estado.REEMBOLSADO, Estado.ENVIADO):
            with self.assertRaises(services.TransicionInvalida):
                services.cambiar_estado(pedido, estado)
        pedido = services.cambiar_estado(pedido, Estado.PAGADO)
        # En reparto es solo de los envios; quien recoge pasa por "listo".
        self.assertEqual(
            services.transiciones_permitidas(pedido), [Estado.PREPARANDO, Estado.LISTO, Estado.ENTREGADO, Estado.CANCELADO],
        )

    def test_el_cliente_ve_el_seguimiento_y_el_numero_de_guia(self):
        pedido = self.envio()
        services.cambiar_estado(pedido, Estado.PAGADO)
        services.cambiar_estado(pedido, Estado.ENVIADO, nota='Sale hoy en la tarde')
        Pedido.objects.filter(pk=pedido.pk).update(transportista='Mensajería Rápida', numero_seguimiento='MR-123')
        pagina = self.client.get(pedido.get_absolute_url())
        self.assertContains(pagina, 'Seguimiento')
        self.assertContains(pagina, 'Sale hoy en la tarde')
        self.assertContains(pagina, 'MR-123')
        self.assertContains(pagina, 'Mensajería Rápida')

    def test_reembolso_saca_el_pedido_de_las_ventas_y_marca_el_pago(self):
        pedido = pedido_de_prueba(self.producto, 1)
        services.cambiar_estado(pedido, Estado.PAGADO)
        pedido = services.cambiar_estado(pedido, Estado.ENTREGADO)
        self.assertEqual(resumen_panel()['ventas_mes'], Decimal('1000.00'))

        pedido = services.cambiar_estado(pedido, Estado.REEMBOLSADO, nota='Devolución aceptada')
        self.assertFalse(pedido.esta_pagado)
        self.assertEqual(pedido.pagos.get().estado, Pago.Estado.REEMBOLSADO)
        self.assertEqual(resumen_panel()['ventas_mes'], 0)
        self.assertEqual(services.transiciones_permitidas(pedido), [])
        # Lo entregado no vuelve solo al almacen.
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_almacen, 4)

    def test_un_pedido_cancelado_sin_cobrar_no_se_reembolsa(self):
        pedido = services.cambiar_estado(pedido_de_prueba(self.producto, 1), Estado.CANCELADO)
        self.assertEqual(services.transiciones_permitidas(pedido), [])
        pagado = services.cambiar_estado(pedido_de_prueba(self.producto, 1), Estado.PAGADO)
        cancelado = services.cambiar_estado(pagado, Estado.CANCELADO)
        self.assertEqual(services.transiciones_permitidas(cancelado), [Estado.REEMBOLSADO])


class CancelarPorElClienteTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), stock_almacen=5)

    def cancelar(self, pedido):
        return self.client.post(reverse('pedidos:cancelar', args=[pedido.token]), follow=True)

    def test_cancela_antes_de_pagar_y_libera_el_stock(self):
        pedido = pedido_de_prueba(self.producto, 2)
        self.assertContains(self.client.get(pedido.get_absolute_url()), 'Cancelar este pedido')
        self.assertContains(self.cancelar(pedido), 'Cancelamos tu pedido.')
        pedido.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual((pedido.estado, self.producto.stock_reservado), (Estado.CANCELADO, 0))
        self.assertEqual(pedido.eventos.last().nota, 'Cancelado por el cliente')
        self.assertEqual(pedido.pagos.get().estado, Pago.Estado.CANCELADO)

    def test_no_cancela_despues_de_pagar_ni_si_ya_aviso_que_transfirio(self):
        pagado = services.cambiar_estado(pedido_de_prueba(self.producto, 1), Estado.PAGADO)
        avisado = pedido_de_prueba(self.producto, 1, transferencia_realizada=True)
        for pedido in (pagado, avisado):
            self.assertNotContains(self.client.get(pedido.get_absolute_url()), 'Cancelar este pedido')
            self.assertContains(self.cancelar(pedido), 'ya no se puede cancelar')
            estado = pedido.estado
            pedido.refresh_from_db()
            self.assertEqual(pedido.estado, estado)

    def test_la_pagina_del_pedido_no_anula_el_origen_de_sus_formularios(self):
        """Con `no-referrer` el navegador manda "Origin: null" y la proteccion CSRF rechaza cancelar o avisar el pago."""
        pedido = pedido_de_prueba(self.producto, 1)
        pagina = self.client.get(pedido.get_absolute_url())
        self.assertNotContains(pagina, 'content="no-referrer"')
        self.assertContains(pagina, '<meta name="referrer" content="same-origin">')

    def test_solo_por_post(self):
        pedido = pedido_de_prueba(self.producto, 1)
        self.assertEqual(self.client.get(reverse('pedidos:cancelar', args=[pedido.token])).status_code, 405)


class DevolucionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.propia = tienda_de_prueba(correo='ventas@tienda.example')
        cls.ajena = tienda_de_prueba('Fitnes RD')
        cls.vendedor = Usuario.objects.create_user('vendedor', password='clave-segura-123')
        cls.propia.usuarios.add(cls.vendedor)
        dar_acceso_al_panel([cls.vendedor])
        cls.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))
        cls.producto_ajeno = crear_producto(sku='P1', tienda=cls.ajena)

    def entregado(self, producto=None):
        pedido = pedido_de_prueba(producto or self.producto, 1)
        services.cambiar_estado(pedido, Estado.PAGADO)
        return services.cambiar_estado(pedido, Estado.ENTREGADO)

    def pedir(self, pedido, motivo='Llegó con la pantalla rota y no enciende.'):
        return self.client.post(reverse('pedidos:pedir_devolucion', args=[pedido.token]), {'motivo': motivo}, follow=True)

    def test_el_cliente_la_pide_y_la_tienda_recibe_el_aviso(self):
        pedido = self.entregado()
        self.assertContains(self.client.get(pedido.get_absolute_url()), 'Solicita una devolución')
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.pedir(pedido)
        self.assertContains(respuesta, 'Enviamos tu solicitud a la tienda')
        solicitud = SolicitudDevolucion.objects.get()
        self.assertEqual((solicitud.tienda, solicitud.estado), (self.propia, SolicitudDevolucion.Estado.PENDIENTE))
        self.assertEqual(mail.outbox[-1].to, ['ventas@tienda.example'])
        self.assertIn('pantalla rota', mail.outbox[-1].body)
        # Con una solicitud abierta no se puede pedir otra.
        self.pedir(pedido)
        self.assertEqual(SolicitudDevolucion.objects.count(), 1)
        self.assertContains(self.client.get(pedido.get_absolute_url()), 'Por revisar')

    def test_solo_pedidos_entregados_dentro_del_plazo_y_con_motivo(self):
        pendiente = pedido_de_prueba(self.producto, 1)
        self.pedir(pendiente)
        entregado = self.entregado()
        self.pedir(entregado, motivo='corto')
        Pedido.objects.filter(pk=entregado.pk).update(fecha_entrega=timezone.now() - timedelta(days=8))
        self.assertNotContains(self.client.get(entregado.get_absolute_url()), 'Solicita una devolución')
        self.pedir(entregado)
        self.assertFalse(SolicitudDevolucion.objects.exists())

    def test_con_cero_dias_no_se_ofrecen_devoluciones(self):
        configuracion = ConfiguracionTienda.obtener()
        configuracion.dias_devolucion = 0
        configuracion.save()
        pedido = self.entregado()
        self.assertFalse(services.puede_pedir_devolucion(pedido))

    def test_la_tienda_responde_solo_las_suyas(self):
        propia = services.solicitar_devolucion(self.entregado(), 'El producto llegó dañado.')
        ajena = services.solicitar_devolucion(self.entregado(self.producto_ajeno), 'El producto llegó dañado.')
        self.client.force_login(self.vendedor)
        lista = reverse('admin:pedidos_solicituddevolucion_changelist')
        self.assertEqual(list(self.client.get(lista).context['cl'].queryset), [propia])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(lista, {'action': 'aceptar', '_selected_action': [propia.pk, ajena.pk]})
        propia.refresh_from_db()
        ajena.refresh_from_db()
        self.assertEqual((propia.estado, propia.resuelto_por), (SolicitudDevolucion.Estado.ACEPTADA, self.vendedor))
        self.assertEqual(ajena.estado, SolicitudDevolucion.Estado.PENDIENTE)
        self.assertIn('aceptó tu solicitud', mail.outbox[-1].body)
        # Aceptar no mueve dinero: el reembolso se registra aparte en el pedido.
        self.assertEqual(propia.pedido.estado, Estado.ENTREGADO)
        with self.assertRaises(services.PedidoError):
            services.responder_devolucion(propia, False)

    def test_tras_un_rechazo_puede_volver_a_pedirla(self):
        pedido = self.entregado()
        solicitud = services.solicitar_devolucion(pedido, 'El producto llegó dañado.')
        services.responder_devolucion(solicitud, False, respuesta='Fuera de garantía')
        self.assertTrue(services.puede_pedir_devolucion(pedido))
