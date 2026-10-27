"""Cada tienda cobra lo suyo (pedido del dueño el 2026-10-26): el cliente ve las cuentas de la tienda, el comprobante
le llega a ella y ella aprueba el pago. Los pedidos de antes que cobro el sitio (`cobra_el_sitio`) los sigue
confirmando el administrador principal."""
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
from pedidos.services import (
    PedidoError, TransicionInvalida, cambiar_estado, metodos_pago_disponibles, transiciones_permitidas,
)
from pedidos.tests.utiles import comprobante_de_prueba, pedido_de_prueba
from tiendas.models import CuentaBancaria
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

CLAVE = 'clave-segura-123'
Estado = Pedido.Estado


class CobroDeCadaTiendaTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_superuser('admin', 'dueno@example.com', CLAVE)
        self.tienda = tienda_de_prueba(correo='tienda@example.com')
        self.tienda.cuentas.update(banco='Banco de la tienda')
        self.vendedor = Usuario.objects.create_user('vendedor', 'vendedor@example.com', CLAVE)
        self.tienda.usuarios.add(self.vendedor)
        dar_acceso_al_panel([self.vendedor])
        self.del_sitio = CuentaDelSitio.objects.create(banco='Banco del dueño', numero='111', titular='Dueño')
        self.producto = crear_producto(precio=Decimal('1000'), tienda=self.tienda)

    def pedido(self, **cambios):
        return pedido_de_prueba(self.producto, 1, **cambios)

    def pedido_de_antes(self, **cambios):
        """Un pedido de antes del 2026-10-26: el cliente transfirio a las cuentas del sitio."""
        pedido = self.pedido(**cambios)
        Pedido.objects.filter(pk=pedido.pk).update(cobra_el_sitio=True)
        pedido.refresh_from_db()
        return pedido

    def test_el_cliente_ve_las_cuentas_de_la_tienda(self):
        CuentaBancaria.objects.create(tienda=self.tienda, banco='Banco viejo', numero='999', titular='X', activa=False)
        self.assertEqual([c.banco for c in cuentas_para_transferir(self.tienda)], ['Banco de la tienda'])
        pedido = self.pedido()
        self.assertFalse(pedido.cobra_el_sitio)
        pagina = self.client.get(pedido.get_absolute_url())
        self.assertContains(pagina, 'Banco de la tienda')
        self.assertNotContains(pagina, 'Banco viejo')
        self.assertNotContains(pagina, 'Banco del dueño')

    def test_sin_cuentas_la_tienda_no_ofrece_transferencia(self):
        self.tienda.cuentas.all().delete()
        self.assertEqual(metodos_pago_disponibles(Pedido.Entrega.RECOGER, self.tienda), [Pedido.Pago.EFECTIVO_RECOGER])
        self.assertEqual(metodos_pago_disponibles(Pedido.Entrega.ENVIO, self.tienda), [])
        with self.assertRaises(PedidoError):
            self.pedido()
        # En efectivo al recoger sigue vendiendo.
        self.assertEqual(self.pedido(metodo_pago=Pedido.Pago.EFECTIVO_RECOGER).estado, Estado.PENDIENTE)

    def test_el_comprobante_le_llega_a_la_tienda(self):
        pedido = self.pedido()
        with self.captureOnCommitCallbacks(execute=True):
            services.registrar_comprobante(pedido, comprobante_de_prueba(), referencia='REF-1')
        aviso = [correo for correo in mail.outbox if 'Transferencia por revisar' in correo.subject][0]
        self.assertEqual(aviso.to, ['tienda@example.com'])

    def test_el_vendedor_aprueba_el_pago_de_su_pedido_y_sigue_con_el(self):
        pedido = self.pedido(transferencia_realizada=True)
        self.assertIn(Estado.PAGADO, transiciones_permitidas(pedido, self.vendedor))
        services.aprobar_pago(pedido.pagos.get(), self.vendedor)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.PAGADO)
        cambiar_estado(pedido, Estado.PREPARANDO, usuario=self.vendedor)
        # El dinero lo tiene la tienda: ella decide si cancela y devuelve.
        otro = cambiar_estado(self.pedido(transferencia_realizada=True), Estado.PAGADO, usuario=self.vendedor)
        self.assertIn(Estado.CANCELADO, transiciones_permitidas(otro, self.vendedor))

    def test_en_el_panel_el_vendedor_aprueba_y_rechaza(self):
        pedido = self.pedido(transferencia_realizada=True)
        self.client.force_login(self.vendedor)
        respuesta = self.client.post(reverse('admin:pagos_pago_changelist'), {
            'action': 'aprobar', '_selected_action': [pedido.pagos.get().pk],
        }, follow=True)
        self.assertContains(respuesta, '1 pago(s) aprobados')
        self.assertEqual(pedido.pagos.get().estado, Pago.Estado.APROBADO)

    def test_los_pedidos_de_antes_los_sigue_confirmando_el_sitio(self):
        pedido = self.pedido_de_antes(transferencia_realizada=True)
        pago = pedido.pagos.get()
        for accion in (services.aprobar_pago, services.rechazar_pago):
            with self.assertRaises(services.PagoError):
                accion(pago, self.vendedor)
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(pedido, Estado.PAGADO, usuario=self.vendedor)
        self.assertEqual(transiciones_permitidas(pedido, self.vendedor), [])
        self.client.force_login(self.vendedor)
        self.assertContains(self.client.get(reverse('admin:pedidos_pedido_changelist')), 'El sitio verifica el pago')
        # El dueño lo aprueba y la tienda recibe "Pago confirmado" para prepararlo.
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.aprobar_pago(pago, self.admin)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.PAGADO)
        aviso = [correo for correo in mail.outbox if correo.subject == f'Pago confirmado: pedido {pedido.numero}'][0]
        self.assertEqual(aviso.to, ['tienda@example.com'])
        self.assertNotIn(Estado.CANCELADO, transiciones_permitidas(pedido, self.vendedor))

    def test_el_vendedor_maneja_las_cuentas_de_su_tienda_y_no_las_del_sitio(self):
        ajena = tienda_de_prueba('Fitnes RD')
        self.client.force_login(self.vendedor)
        lista = self.client.get(reverse('admin:tiendas_cuentabancaria_changelist'))
        self.assertEqual([c.tienda for c in lista.context['cl'].result_list], [self.tienda])
        respuesta = self.client.post(reverse('admin:tiendas_cuentabancaria_add'), {
            'tienda': self.tienda.pk, 'banco': 'Banreservas', 'tipo_cuenta': 'ahorros', 'numero': '123',
            'titular': 'Mi tienda', 'cedula_rnc': '', 'activa': 'on', 'orden': '0',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.tienda.cuentas.filter(banco='Banreservas').exists())
        cuenta_ajena = ajena.cuentas.get()
        self.assertNotEqual(
            self.client.get(reverse('admin:tiendas_cuentabancaria_change', args=[cuenta_ajena.pk])).status_code, 200,
        )
        # Las del sitio (a donde le pagan las tiendas su plan) son solo del administrador.
        self.assertEqual(self.client.get(reverse('admin:core_cuentadelsitio_changelist')).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('admin:core_cuentadelsitio_changelist')), 'Banco del dueño')


class PedidosConDineroTests(TestCase):
    """El vendedor no borra pedidos con dinero de por medio: son el registro de lo cobrado."""

    setUp = CobroDeCadaTiendaTests.setUp
    pedido = CobroDeCadaTiendaTests.pedido
    pedido_de_antes = CobroDeCadaTiendaTests.pedido_de_antes

    def borrar(self, usuario, pedido):
        self.client.force_login(usuario)
        return self.client.post(reverse('admin:pedidos_pedido_delete', args=[pedido.pk]), {'post': 'yes'})

    def test_el_vendedor_no_borra_lo_cobrado_avisado_ni_liquidado(self):
        from pagos.liquidaciones import liquidar

        pagado = cambiar_estado(self.pedido(), Estado.PAGADO, usuario=self.vendedor)
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

    def test_el_vendedor_no_cancela_un_pedido_de_antes_ya_cobrado_por_el_sitio(self):
        pagado = cambiar_estado(self.pedido_de_antes(), Estado.PAGADO, usuario=self.admin)
        self.assertNotIn(Estado.CANCELADO, transiciones_permitidas(pagado, self.vendedor))
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(pagado, Estado.CANCELADO, usuario=self.vendedor)
        # Lo sigue preparando y entregando como siempre.
        self.assertIn(Estado.PREPARANDO, transiciones_permitidas(pagado, self.vendedor))
        self.assertIn(Estado.CANCELADO, transiciones_permitidas(pagado, self.admin))
