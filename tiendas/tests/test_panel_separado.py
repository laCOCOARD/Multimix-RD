"""El panel del dueño de tienda sin lo del administrador (2026-10-28): sin el reparto viejo (cobra el sitio,
liquidaciones), ruta de arriba simple, numeritos de pendientes en el menu que se actualizan solos."""
from decimal import Decimal

from django.urls import reverse

from opiniones.models import Pregunta
from pagos.models import Liquidacion
from pedidos.models import Pedido
from pedidos.services import cambiar_estado

from .test_panel import PanelDeVendedores


class SinLoDelAdministradorTests(PanelDeVendedores):
    def test_pedidos_sin_reparto_viejo(self):
        lista = self.client.get(reverse('admin:pedidos_pedido_changelist'))
        filtros = [f.title for f in lista.context['cl'].filter_specs]
        self.assertNotIn('lo cobra el sitio', filtros)
        self.assertNotIn('liquidación', filtros)
        self.assertNotIn('metodo_pago', lista.context['cl'].list_display)
        pedido = self.client.get(reverse('admin:pedidos_pedido_change', args=[self.pedido_propio.pk]))
        self.assertNotContains(pedido, 'Reparto a la tienda')
        self.assertContains(pedido, '<div class="breadcrumbs"><a href="/panel/">Inicio</a>', html=False)
        self.assertNotContains(pedido, '>Pedidos</a>\n› <a', html=False)

    def test_el_administrador_si_ve_el_reparto(self):
        self.client.force_login(self.admin)
        lista = self.client.get(reverse('admin:pedidos_pedido_changelist'))
        self.assertIn('lo cobra el sitio', [f.title for f in lista.context['cl'].filter_specs])

    def test_pagos_sin_quien_confirma(self):
        lista = self.client.get(reverse('admin:pagos_pago_changelist'))
        self.assertNotIn('quien_confirma', lista.context['cl'].list_display)

    def test_liquidaciones_solo_si_tiene(self):
        menu = [m['name'] for g in self.client.get(reverse('admin:index')).context['app_list'] for m in g['models']]
        self.assertNotIn('Liquidaciones', menu)
        cero = Decimal('0')
        Liquidacion.objects.create(tienda=self.propia, ventas=cero, cobrado_por_el_sitio=cero, cobrado_por_la_tienda=cero,
                                   comision_de_lo_cobrado_por_la_tienda=cero, comision_porcentaje=cero, comision=cero,
                                   monto=cero)
        menu = [m['name'] for g in self.client.get(reverse('admin:index')).context['app_list'] for m in g['models']]
        self.assertIn('Liquidaciones', menu)

    def test_ruta_de_arriba_simple(self):
        lista = self.client.get(reverse('admin:catalogo_producto_changelist'))
        self.assertContains(lista, '<div class="breadcrumbs"><a href="/panel/">Inicio</a> › Productos</div>', html=True)
        self.assertNotContains(lista, 'Catalogo</a>')


class PendientesEnVivoTests(PanelDeVendedores):
    def test_numeritos_del_menu_y_del_endpoint(self):
        Pedido.objects.filter(pk=self.pedido_propio.pk).update(transferencia_realizada=True)
        cambiar_estado(self.pedido_ajeno, Pedido.Estado.PAGADO)  # de otra tienda: no cuenta
        Pregunta.objects.create(tienda=self.propia, producto=self.lampara, usuario=self.vendedor, texto='¿Hay azul?')
        inicio = self.client.get(reverse('admin:index'))
        self.assertContains(inicio, 'data-pendientes="pedidos.pedido"')
        self.assertContains(inicio, '<meta name="pv-pendientes" content="/panel/pendientes/">', html=True)
        datos = self.client.get(reverse('admin:pendientes')).json()
        self.assertEqual(datos['pendientes'], {'pedidos.pedido': 1, 'opiniones.pregunta': 1})
        self.assertEqual(datos['total'], 1)  # solo lo urgente: la transferencia por confirmar
        self.assertIn('Transferencia por confirmar', datos['tareas'])
        self.assertNotIn('Pesas', datos['tareas'])

    def test_el_menu_tiene_el_lugar_del_numerito_aunque_este_en_cero(self):
        lista = self.client.get(reverse('admin:catalogo_producto_changelist'))
        self.assertContains(lista, 'data-pendientes="opiniones.pregunta" hidden', html=False)

    def test_el_administrador_no_lo_usa(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('admin:pendientes')).json()['pendientes'], {})
        self.assertNotContains(self.client.get(reverse('admin:index')), 'pv-pendientes')

    def test_sin_entrar_no_responde(self):
        self.client.logout()
        respuesta = self.client.get(reverse('admin:pendientes'))
        self.assertEqual(respuesta.status_code, 302)
