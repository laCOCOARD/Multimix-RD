"""Pedidos en el panel del dueño de la tienda, fase 2 (2026-10-29): pestañas con lo que falta, columna "Qué sigue" y
la página del pedido con el paso siguiente, el comprobante y sus botones. Cada vendedor solo ve y toca lo suyo."""
from django.contrib.messages import get_messages
from django.urls import reverse

from pagos import services as pagos
from pagos.models import Pago
from pedidos.models import Pedido
from pedidos.services import cambiar_estado, siguiente_paso
from pedidos.tests.utiles import comprobante_de_prueba, pedido_de_prueba

from .test_panel import PanelDeVendedores

Estado = Pedido.Estado


class PedidosDelVendedorTests(PanelDeVendedores):
    def bandejas(self, **filtros):
        respuesta = self.client.get(reverse('admin:pedidos_pedido_changelist'), filtros)
        cuentas = {p['clave']: p['cantidad'] for p in respuesta.context['pestanas']}
        return cuentas, [tarjeta['pedido'] for tarjeta in respuesta.context['tarjetas']]

    def detalle(self, pedido):
        return self.client.get(reverse('admin:pedidos_pedido_change', args=[pedido.pk]))

    def avisar_transferencia(self, pedido):
        with self.captureOnCommitCallbacks(execute=True):
            return pagos.registrar_comprobante(pedido, comprobante_de_prueba(), 'REF-9')

    def test_pestanas_cuentan_solo_lo_de_su_tienda_y_filtran(self):
        cuentas, pedidos = self.bandejas(bandeja='todos')
        self.assertEqual(cuentas['esperando_pago'], 1)
        self.assertEqual(sum(cuentas.values()), 1)  # el de la otra tienda no cuenta
        self.assertEqual(pedidos, [self.pedido_propio])
        # "Para atender" (lo primero que se ve) no trae lo que espera al cliente.
        self.assertEqual(self.bandejas()[1], [])
        self.avisar_transferencia(self.pedido_propio)
        cuentas, pedidos = self.bandejas(bandeja='por_confirmar')
        self.assertEqual((cuentas['por_confirmar'], cuentas['esperando_pago']), (1, 0))
        self.assertEqual(pedidos, [self.pedido_propio])
        self.assertEqual(self.bandejas(bandeja='por_preparar')[1], [])
        cambiar_estado(self.pedido_propio, Estado.PAGADO)
        self.assertEqual(self.bandejas(bandeja='por_preparar')[1], [self.pedido_propio])

    def test_columna_que_sigue(self):
        lista = self.client.get(reverse('admin:pedidos_pedido_changelist'), {'lista': 1})
        self.assertContains(lista, 'Esperando el pago')
        self.avisar_transferencia(self.pedido_propio)
        lista = self.client.get(reverse('admin:pedidos_pedido_changelist'), {'lista': 1})
        self.assertContains(lista, 'pv-que-sigue pv-urgente')
        self.assertContains(lista, 'Revisar el pago')

    def test_confirmar_el_pago_desde_el_pedido(self):
        pago = self.avisar_transferencia(self.pedido_propio)
        pagina = self.detalle(self.pedido_propio)
        self.assertContains(pagina, 'Revisa el comprobante')
        self.assertContains(pagina, reverse('admin:pagos_pago_comprobante', args=[pago.pk]))
        self.assertContains(pagina, 'El dinero llegó: confirmar pago')
        url = reverse('admin:pedidos_pedido_pago', args=[self.pedido_propio.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(url, {'accion': 'aprobar'})
        self.assertRedirects(respuesta, reverse('admin:pedidos_pedido_change', args=[self.pedido_propio.pk]),
                             fetch_redirect_response=False)
        self.pedido_propio.refresh_from_db()
        pago.refresh_from_db()
        self.assertEqual((self.pedido_propio.estado, pago.estado), (Estado.PAGADO, Pago.Estado.APROBADO))
        self.assertEqual(pago.revisado_por, self.vendedor)
        # Ahora toca prepararlo: ese es el boton grande.
        self.assertEqual(self.detalle(self.pedido_propio).context['paso']['principal']['valor'], Estado.PREPARANDO)

    def test_rechazar_el_comprobante_con_motivo(self):
        pago = self.avisar_transferencia(self.pedido_propio)
        url = reverse('admin:pedidos_pedido_pago', args=[self.pedido_propio.pk])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {'accion': 'rechazar', 'motivo': 'No aparece en el banco'})
        pago.refresh_from_db()
        self.pedido_propio.refresh_from_db()
        self.assertEqual((pago.estado, pago.nota), (Pago.Estado.RECHAZADO, 'No aparece en el banco'))
        self.assertEqual((self.pedido_propio.estado, self.pedido_propio.transferencia_realizada),
                         (Estado.PENDIENTE, False))

    def test_no_toca_el_pago_de_otra_tienda(self):
        self.avisar_transferencia(self.pedido_ajeno)
        url = reverse('admin:pedidos_pedido_pago', args=[self.pedido_ajeno.pk])
        self.assertEqual(self.client.post(url, {'accion': 'aprobar'}).status_code, 404)
        self.pedido_ajeno.refresh_from_db()
        self.assertEqual(self.pedido_ajeno.estado, Estado.PENDIENTE)

    def test_sin_pago_por_revisar_avisa_y_no_cambia_nada(self):
        url = reverse('admin:pedidos_pedido_pago', args=[self.pedido_propio.pk])
        respuesta = self.client.post(url, {'accion': 'aprobar'})
        self.assertIn('no tiene un pago esperando', ' '.join(m.message for m in get_messages(respuesta.wsgi_request)))
        self.pedido_propio.refresh_from_db()
        self.assertEqual(self.pedido_propio.estado, Estado.PENDIENTE)

    def test_si_lo_cobra_el_sitio_el_vendedor_no_lo_confirma(self):
        Pedido.objects.filter(pk=self.pedido_propio.pk).update(cobra_el_sitio=True)
        self.pedido_propio.refresh_from_db()
        self.avisar_transferencia(self.pedido_propio)
        pagina = self.detalle(self.pedido_propio)
        self.assertContains(pagina, 'El sitio está revisando el pago')
        self.assertNotContains(pagina, 'El dinero llegó: confirmar pago')
        self.client.post(reverse('admin:pedidos_pedido_pago', args=[self.pedido_propio.pk]), {'accion': 'aprobar'})
        self.pedido_propio.refresh_from_db()
        self.assertEqual(self.pedido_propio.estado, Estado.PENDIENTE)

    def test_enviar_con_transportista_y_mensaje_para_el_cliente(self):
        pedido = pedido_de_prueba(self.lampara, 1, metodo_entrega=Pedido.Entrega.ENVIO, zona=self.zona_propia,
                                  direccion='Calle 1')
        cambiar_estado(pedido, Estado.PAGADO)
        cambiar_estado(pedido, Estado.PREPARANDO)
        paso = self.detalle(pedido).context['paso']
        self.assertEqual(paso['principal']['valor'], Estado.ENVIADO)
        self.assertTrue(paso['pide_envio'])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin:pedidos_pedido_estado', args=[pedido.pk]), {
                'estado': 'enviado', 'transportista': ' Mensajería Rápida ', 'numero_seguimiento': 'MR-123',
                'nota': 'Llega en la tarde',
            })
        pedido.refresh_from_db()
        self.assertEqual((pedido.estado, pedido.transportista, pedido.numero_seguimiento),
                         (Estado.ENVIADO, 'Mensajería Rápida', 'MR-123'))
        self.assertEqual(pedido.eventos.order_by('-id').first().nota, 'Llega en la tarde')

    def test_un_cambio_invalido_no_guarda_el_transportista(self):
        self.client.post(reverse('admin:pedidos_pedido_estado', args=[self.pedido_propio.pk]), {
            'estado': 'enviado', 'transportista': 'Alguien',
        })
        self.pedido_propio.refresh_from_db()
        self.assertEqual((self.pedido_propio.estado, self.pedido_propio.transportista), (Estado.PENDIENTE, ''))

    def test_cada_paso_solo_ofrece_cambios_permitidos(self):
        # Recorre los estados de un pedido para recoger y comprueba que los botones son transiciones validas.
        from pedidos.services import transiciones_permitidas

        pedido = self.pedido_propio
        for estado in (None, Estado.PAGADO, Estado.PREPARANDO, Estado.LISTO, Estado.ENTREGADO):
            if estado:
                pedido = cambiar_estado(pedido, estado)
            paso = siguiente_paso(pedido, self.vendedor)
            botones = [paso.principal, *paso.otros] if paso.principal else paso.otros
            self.assertTrue(set(botones) <= set(transiciones_permitidas(pedido, self.vendedor)), estado)
        self.assertEqual(paso.titulo, 'Pedido completado')
