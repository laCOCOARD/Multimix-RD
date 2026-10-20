"""El sitio recibe todas las transferencias: el cliente ve las cuentas del dueño, el dueño comprueba el pago en su
banco y lo aprueba, y la tienda se entera por correo y en el panel."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto
from core.models import CuentaDelSitio, cuentas_para_transferir
from pagos import services
from pagos.models import Pago
from pedidos.models import Pedido
from pedidos.services import TransicionInvalida, cambiar_estado, transiciones_permitidas
from pedidos.tests.utiles import comprobante_de_prueba, pedido_de_prueba
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

CLAVE = 'clave-segura-123'
Estado = Pedido.Estado


class CobroDelSitioTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_superuser('admin', 'dueno@example.com', CLAVE)
        self.tienda = tienda_de_prueba(correo='tienda@example.com')
        self.vendedor = Usuario.objects.create_user('vendedor', 'vendedor@example.com', CLAVE)
        self.tienda.usuarios.add(self.vendedor)
        dar_acceso_al_panel([self.vendedor])
        self.del_sitio = CuentaDelSitio.objects.create(banco='Banco del dueño', numero='111', titular='Dueño')
        self.producto = crear_producto(precio=Decimal('1000'), tienda=self.tienda)

    def pedido(self, **cambios):
        return pedido_de_prueba(self.producto, 1, **cambios)

    def test_el_cliente_ve_las_cuentas_del_sitio(self):
        CuentaDelSitio.objects.create(banco='Banco viejo', numero='999', titular='Dueño', activa=False)
        self.assertEqual(list(cuentas_para_transferir()), [self.del_sitio])
        pedido = self.pedido()
        self.assertTrue(pedido.cobra_el_sitio)
        pagina = self.client.get(pedido.get_absolute_url())
        self.assertContains(pagina, 'Banco del dueño')
        self.assertNotContains(pagina, 'Banco viejo')

    def test_el_efectivo_lo_cobra_la_tienda(self):
        self.assertFalse(self.pedido(metodo_pago=Pedido.Pago.EFECTIVO_RECOGER).cobra_el_sitio)

    def test_el_comprobante_le_llega_al_dueno_no_a_la_tienda(self):
        pedido = self.pedido()
        with self.captureOnCommitCallbacks(execute=True):
            services.registrar_comprobante(pedido, comprobante_de_prueba(), referencia='REF-1')
        aviso = [correo for correo in mail.outbox if 'Transferencia por revisar' in correo.subject][0]
        self.assertEqual(aviso.to, ['dueno@example.com'])
        self.assertIn('app del banco', aviso.body)

    def test_el_vendedor_no_aprueba_ni_rechaza_ni_marca_pagado(self):
        pedido = self.pedido(transferencia_realizada=True)
        pago = pedido.pagos.get()
        for accion in (services.aprobar_pago, services.rechazar_pago):
            with self.assertRaises(services.PagoError):
                accion(pago, self.vendedor)
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(pedido, Estado.PAGADO, usuario=self.vendedor)
        # Tampoco lo cancela: el cliente dice que ya transfirio a las cuentas del dueño.
        self.assertEqual(transiciones_permitidas(pedido, self.vendedor), [])
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.PENDIENTE)

    def test_el_dueno_aprueba_y_la_tienda_recibe_el_aviso_para_preparar(self):
        pedido = self.pedido(transferencia_realizada=True)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.aprobar_pago(pedido.pagos.get(), self.admin)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.PAGADO)
        aviso = [correo for correo in mail.outbox if correo.subject == f'Pago confirmado: pedido {pedido.numero}'][0]
        self.assertEqual(aviso.to, ['tienda@example.com'])
        self.assertIn('Ya puedes prepararlo', aviso.body)
        # Despues el vendedor sigue con el pedido como siempre.
        self.assertIn(Estado.PREPARANDO, transiciones_permitidas(pedido, self.vendedor))
        cambiar_estado(pedido, Estado.PREPARANDO, usuario=self.vendedor)

    def test_en_el_panel_el_vendedor_ve_que_lo_confirma_el_sitio(self):
        pedido = self.pedido(transferencia_realizada=True)
        self.client.force_login(self.vendedor)
        lista = self.client.get(reverse('admin:pedidos_pedido_changelist'))
        self.assertContains(lista, 'El sitio verifica el pago')
        detalle = self.client.get(reverse('admin:pedidos_pedido_change', args=[pedido.pk]))
        self.assertContains(detalle, 'lo marca como')
        self.assertEqual(detalle.context['transiciones'], [])
        respuesta = self.client.post(reverse('admin:pagos_pago_changelist'), {
            'action': 'aprobar', '_selected_action': [pedido.pagos.get().pk],
        }, follow=True)
        self.assertContains(respuesta, 'lo confirma el administrador principal')
        self.assertEqual(pedido.pagos.get().estado, Pago.Estado.EN_REVISION)

    def test_solo_el_dueno_administra_las_cuentas_del_sitio(self):
        lista = reverse('admin:core_cuentadelsitio_changelist')
        self.client.force_login(self.vendedor)
        self.assertEqual(self.client.get(lista).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(lista), 'Banco del dueño')


class PedidosConDineroTests(TestCase):
    """El vendedor no borra ni cancela pedidos con dinero de por medio: son el registro de lo que cobro el dueño y de
    la comision del sitio."""

    setUp = CobroDelSitioTests.setUp
    pedido = CobroDelSitioTests.pedido

    def borrar(self, usuario, pedido):
        self.client.force_login(usuario)
        return self.client.post(reverse('admin:pedidos_pedido_delete', args=[pedido.pk]), {'post': 'yes'})

    def test_el_vendedor_no_borra_lo_cobrado_avisado_ni_liquidado(self):
        from pagos.liquidaciones import liquidar

        pagado = cambiar_estado(self.pedido(), Estado.PAGADO, usuario=self.admin)
        avisado = self.pedido(transferencia_realizada=True)
        efectivo = self.pedido(metodo_pago=Pedido.Pago.EFECTIVO_RECOGER)
        for estado in (Estado.PAGADO, Estado.ENTREGADO):
            efectivo = cambiar_estado(efectivo, estado, usuario=self.vendedor)
        liquidar(self.tienda, self.admin)
        for pedido in (pagado, avisado, efectivo):
            self.assertEqual(self.borrar(self.vendedor, pedido).status_code, 403, pedido.numero)
            self.assertTrue(Pedido.objects.filter(pk=pedido.pk).exists())
        # Tampoco con la accion de la lista.
        self.client.post(reverse('admin:pedidos_pedido_changelist'), {
            'action': 'delete_selected', '_selected_action': [pagado.pk, avisado.pk], 'post': 'yes',
        })
        self.assertEqual(Pedido.objects.filter(pk__in=[pagado.pk, avisado.pk]).count(), 2)

    def test_el_vendedor_si_borra_uno_sin_pagar_y_el_administrador_cualquiera(self):
        sin_pagar = self.pedido()
        self.assertEqual(self.borrar(self.vendedor, sin_pagar).status_code, 302)
        self.assertFalse(Pedido.objects.filter(pk=sin_pagar.pk).exists())

        pagado = cambiar_estado(self.pedido(), Estado.PAGADO, usuario=self.admin)
        self.assertEqual(self.borrar(self.admin, pagado).status_code, 302)
        self.assertFalse(Pedido.objects.filter(pk=pagado.pk).exists())

    def test_el_vendedor_no_cancela_un_pedido_ya_cobrado_por_el_sitio(self):
        pagado = cambiar_estado(self.pedido(), Estado.PAGADO, usuario=self.admin)
        self.assertNotIn(Estado.CANCELADO, transiciones_permitidas(pagado, self.vendedor))
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(pagado, Estado.CANCELADO, usuario=self.vendedor)
        # Lo sigue preparando y entregando como siempre.
        self.assertIn(Estado.PREPARANDO, transiciones_permitidas(pagado, self.vendedor))
        self.assertIn(Estado.CANCELADO, transiciones_permitidas(pagado, self.admin))
