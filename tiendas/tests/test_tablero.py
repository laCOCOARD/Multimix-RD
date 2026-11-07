"""Tablero de pedidos (2026-11-06): tarjetas con un boton grande; cada tienda ve solo sus pedidos."""
from django.urls import reverse

from pagos import services as pagos
from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import comprobante_de_prueba

from .test_panel import PanelDeVendedores

Estado = Pedido.Estado
TABLERO = 'admin:pedidos_pedido_changelist'


class TableroTests(PanelDeVendedores):
    def tablero(self, **filtros):
        return self.client.get(reverse(TABLERO), filtros)

    def pedidos(self, **filtros):
        return [tarjeta['pedido'] for tarjeta in self.tablero(**filtros).context['tarjetas']]

    def avisar_transferencia(self, pedido):
        with self.captureOnCommitCallbacks(execute=True):
            return pagos.registrar_comprobante(pedido, comprobante_de_prueba(), 'REF-9')

    def test_es_la_pantalla_de_pedidos_y_la_lista_sigue_aparte(self):
        respuesta = self.tablero()
        self.assertTemplateUsed(respuesta, 'admin/pedidos/pedido/tablero.html')
        self.assertContains(respuesta, '?lista=1')
        lista = self.client.get(reverse(TABLERO), {'lista': 1})
        self.assertEqual(list(lista.context['cl'].result_list), [self.pedido_propio])
        # Con un filtro de la lista de Django (por ejemplo desde el resumen) sigue la lista.
        self.assertIn('cl', self.client.get(reverse(TABLERO), {'estado__exact': 'pendiente'}).context)

    def test_solo_trae_lo_de_su_tienda(self):
        self.avisar_transferencia(self.pedido_ajeno)
        self.assertEqual(self.pedidos(bandeja='todos'), [self.pedido_propio])
        self.assertEqual(self.pedidos(bandeja='por_confirmar'), [])
        self.assertEqual(self.pedidos(bandeja='todos', q=self.pedido_ajeno.numero), [])
        respuesta = self.tablero(bandeja='todos')
        self.assertNotContains(respuesta, 'Carlos Ajeno')
        self.assertEqual(sum(p['cantidad'] for p in respuesta.context['pestanas']), 1)
        # Elegir la tienda ajena por su numero no la abre: solo cuentan las tiendas de quien mira.
        self.assertEqual(self.pedidos(bandeja='todos', tienda=self.ajena.pk), [self.pedido_propio])

    def test_el_administrador_ve_todas_y_puede_elegir_una(self):
        self.client.force_login(self.admin)
        self.assertCountEqual(self.pedidos(bandeja='todos'), [self.pedido_propio, self.pedido_ajeno])
        self.assertEqual(self.pedidos(bandeja='todos', tienda=self.ajena.pk), [self.pedido_ajeno])

    def test_confirmar_el_pago_desde_la_tarjeta_vuelve_al_tablero(self):
        pago = self.avisar_transferencia(self.pedido_propio)
        respuesta = self.tablero()
        (tarjeta,) = respuesta.context['tarjetas']
        self.assertEqual(tarjeta['accion']['tipo'], 'pago')
        self.assertContains(respuesta, 'El dinero llegó: confirmar pago')
        self.assertContains(respuesta, reverse('admin:pagos_pago_comprobante', args=[pago.pk]))
        self.assertContains(respuesta, 'data-confirmar=')
        volver = reverse(TABLERO) + '?bandeja=por_confirmar'
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('admin:pedidos_pedido_pago', args=[self.pedido_propio.pk]),
                                         {'accion': 'aprobar', 'volver': volver})
        self.assertRedirects(respuesta, volver, fetch_redirect_response=False)
        self.pedido_propio.refresh_from_db()
        self.assertEqual(self.pedido_propio.estado, Estado.PAGADO)

    def test_el_boton_grande_avanza_el_pedido(self):
        cambiar_estado(self.pedido_propio, Estado.PAGADO)
        (tarjeta,) = self.tablero().context['tarjetas']
        self.assertEqual(tarjeta['accion']['valor'], Estado.PREPARANDO)
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('admin:pedidos_pedido_estado', args=[self.pedido_propio.pk]),
                                         {'estado': Estado.PREPARANDO, 'volver': reverse(TABLERO)})
        self.assertRedirects(respuesta, reverse(TABLERO), fetch_redirect_response=False)
        self.pedido_propio.refresh_from_db()
        self.assertEqual(self.pedido_propio.estado, Estado.PREPARANDO)
        self.assertEqual(self.pedidos(bandeja='preparando'), [self.pedido_propio])

    def test_volver_no_lleva_fuera_del_panel(self):
        cambiar_estado(self.pedido_propio, Estado.PAGADO)
        for volver in ('https://otro.example/', '//otro.example/', '/'):
            respuesta = self.client.post(reverse('admin:pedidos_pedido_estado', args=[self.pedido_propio.pk]),
                                         {'estado': Estado.PREPARANDO, 'volver': volver})
            self.assertRedirects(respuesta, reverse('admin:pedidos_pedido_change', args=[self.pedido_propio.pk]),
                                 fetch_redirect_response=False)

    def test_no_avanza_un_pedido_de_otra_tienda(self):
        cambiar_estado(self.pedido_ajeno, Estado.PAGADO)
        respuesta = self.client.post(reverse('admin:pedidos_pedido_estado', args=[self.pedido_ajeno.pk]),
                                     {'estado': Estado.PREPARANDO, 'volver': reverse(TABLERO)})
        self.assertEqual(respuesta.status_code, 404)
        self.pedido_ajeno.refresh_from_db()
        self.assertEqual(self.pedido_ajeno.estado, Estado.PAGADO)

    def test_lo_terminado_no_tiene_boton(self):
        cambiar_estado(self.pedido_propio, Estado.CANCELADO)
        (tarjeta,) = self.tablero(bandeja='cancelados').context['tarjetas']
        self.assertIsNone(tarjeta['accion'])
        self.assertEqual(self.pedidos(), [])  # "Para atender" queda vacio
        self.assertContains(self.tablero(), 'Todo al día')
