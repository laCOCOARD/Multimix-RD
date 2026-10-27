"""Planes y cobro del sitio a las tiendas (pedido del dueño el 2026-10-26): la mensualidad vence el dia 1, el dia 1
se cobran los pedidos de mas del mes anterior, avisos por correo y cierre de la tienda que no paga."""
from datetime import date, datetime, time
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.tests.test_modelos import crear_producto, imagen_de_prueba
from core.models import ConfiguracionTienda, CuentaDelSitio
from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import pedido_de_prueba
from planes import services
from planes.models import Cargo, Plan
from tiendas.models import Tienda
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

D = Decimal
CLAVE = 'clave-segura-123'
Estado = Cargo.Estado


def en_fecha(fecha, hora=time(12)):
    return timezone.make_aware(datetime.combine(fecha, hora))


class ConPlan(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_superuser('admin', 'dueno@example.com', CLAVE)
        self.plan = Plan.objects.get(nombre='Estándar')
        self.plan.mensualidad, self.plan.pedidos_incluidos, self.plan.porcentaje_excedente = D('1000'), 2, D('10')
        self.plan.save()
        self.tienda = tienda_de_prueba(correo='tienda@example.com')
        self.vendedor = Usuario.objects.create_user('vendedor', 'vendedor@example.com', CLAVE)
        self.tienda.usuarios.add(self.vendedor)
        dar_acceso_al_panel([self.vendedor])
        CuentaDelSitio.objects.create(banco='Banco del dueño', numero='111', titular='Dueño')
        config = ConfiguracionTienda.obtener()
        config.correo = 'sitio@example.com'
        config.save()

    def dar_plan(self, tienda=None, desde=date(2026, 9, 15)):
        tienda = tienda or self.tienda
        Tienda.objects.filter(pk=tienda.pk).update(plan=self.plan, plan_desde=desde)
        tienda.refresh_from_db()
        return tienda


class PlanesTests(ConPlan):
    def test_hay_tres_planes_y_ninguna_tienda_queda_con_uno(self):
        self.assertEqual(list(Plan.objects.values_list('nombre', flat=True)), ['Básico', 'Estándar', 'Premium'])
        self.assertFalse(Tienda.objects.filter(plan__isnull=False).exists())

    def test_al_asignar_el_plan_se_anota_desde_cuando(self):
        self.tienda.plan = self.plan
        self.tienda.save()
        self.assertEqual(self.tienda.plan_desde, timezone.localdate())
        self.tienda.nombre = 'Otro nombre'
        self.tienda.save()
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.plan_desde, timezone.localdate())


class MensualidadesTests(ConPlan):
    def test_la_mensualidad_aparece_una_semana_antes_y_vence_el_1(self):
        self.dar_plan()
        self.assertEqual(services.generar_mensualidades(date(2026, 10, 24)), [])
        [cargo] = services.generar_mensualidades(date(2026, 10, 25))
        self.assertEqual(
            (cargo.tipo, cargo.periodo, cargo.vence, cargo.monto, cargo.concepto),
            (Cargo.Tipo.MENSUALIDAD, date(2026, 11, 1), date(2026, 11, 1), D('1000.00'),
             'Mensualidad de noviembre de 2026 · Plan Estándar'),
        )
        # No se repite.
        self.assertEqual(services.generar_mensualidades(date(2026, 10, 30)), [])

    def test_sin_plan_o_sin_mensualidad_no_se_cobra(self):
        tienda_de_prueba('Sin plan')
        self.assertEqual(services.generar_mensualidades(date(2026, 10, 28)), [])
        self.plan.mensualidad = 0
        self.plan.save()
        self.dar_plan()
        self.assertEqual(services.generar_mensualidades(date(2026, 10, 28)), [])

    def test_quien_recibe_el_plan_a_mitad_de_mes_empieza_a_pagar_el_siguiente(self):
        self.dar_plan(desde=date(2026, 11, 10))
        self.assertEqual(services.generar_mensualidades(date(2026, 11, 10)), [])
        [cargo] = services.generar_mensualidades(date(2026, 11, 25))
        self.assertEqual(cargo.periodo, date(2026, 12, 1))

    def test_si_no_corrio_antes_la_del_mes_se_crea_mientras_dure_la_gracia(self):
        self.dar_plan()
        [cargo] = services.generar_mensualidades(date(2026, 11, 2))
        self.assertEqual((cargo.periodo, cargo.vence), (date(2026, 11, 1), date(2026, 11, 1)))
        # Pasada la gracia ya no: cerraria la tienda en el acto.
        Cargo.objects.all().delete()
        self.assertEqual(services.generar_mensualidades(date(2026, 11, 8)), [])


class ExcedenteTests(ConPlan):
    def setUp(self):
        super().setUp()
        self.dar_plan()
        self.producto = crear_producto(precio=D('1000'), controla_stock=False)

    def cobrado(self, fecha, cantidad=1, **cambios):
        pedido = pedido_de_prueba(self.producto, cantidad, **cambios)
        with mock.patch('django.utils.timezone.now', return_value=en_fecha(fecha)):
            return cambiar_estado(pedido, Pedido.Estado.PAGADO)

    def test_cobra_el_porcentaje_de_lo_vendido_en_los_pedidos_de_mas(self):
        for dia in (3, 5, 9, 20):
            self.cobrado(date(2026, 10, dia), cantidad=dia % 3 + 1)
        cancelado = self.cobrado(date(2026, 10, 25), cantidad=5)
        cambiar_estado(cancelado, Pedido.Estado.CANCELADO)
        self.cobrado(date(2026, 11, 1), cantidad=9)  # de otro mes
        ajeno = crear_producto(sku='A1', precio=D('1000'), tienda=tienda_de_prueba('Fitnes RD'))
        cambiar_estado(pedido_de_prueba(ajeno, 7), Pedido.Estado.PAGADO)

        calculo = services.calcular_excedente(self.tienda, date(2026, 10, 1))
        # Cuatro cobrados en octubre (el cancelado no cuenta); el plan incluye 2: los de mas son los dos ultimos
        # (dia 9, 1 unidad, y dia 20, 3 unidades): RD$ 4,000 en productos, el 10 % es RD$ 400.
        self.assertEqual((calculo.pedidos, calculo.incluidos, len(calculo.de_mas)), (4, 2, 2))
        self.assertEqual((calculo.base, calculo.monto), (D('4000.00'), D('400.00')))

        [cargo] = services.generar_excedentes(date(2026, 11, 1))
        self.assertEqual((cargo.tipo, cargo.periodo, cargo.vence, cargo.monto),
                         (Cargo.Tipo.EXCEDENTE, date(2026, 10, 1), date(2026, 11, 1), D('400.00')))
        self.assertIn('Pedidos de más: ', cargo.detalle)
        self.assertEqual(services.generar_excedentes(date(2026, 11, 2)), [])

    def test_el_envio_y_el_descuento_no_cuentan(self):
        from pedidos.tests.utiles import cupon_de_prueba, zona_de_prueba

        cupon_de_prueba('DIEZ')
        for dia in (1, 2):
            self.cobrado(date(2026, 10, dia))
        self.cobrado(date(2026, 10, 3), cupon='DIEZ', metodo_entrega=Pedido.Entrega.ENVIO, zona=zona_de_prueba(),
                     sector='Naco', direccion='Calle 1')
        # 1,000 - 100 de cupon; el envio no: 10 % de 900.
        self.assertEqual(services.calcular_excedente(self.tienda, date(2026, 10, 1)).monto, D('90.00'))

    def test_sin_pasar_del_limite_o_sin_limite_no_hay_cargo(self):
        self.cobrado(date(2026, 10, 4))
        self.assertEqual(services.generar_excedentes(date(2026, 11, 1)), [])
        self.plan.pedidos_incluidos = None
        self.plan.save()
        for dia in (5, 6, 7):
            self.cobrado(date(2026, 10, dia))
        self.assertEqual(services.generar_excedentes(date(2026, 11, 1)), [])

    def test_solo_cuenta_desde_que_tiene_el_plan(self):
        Tienda.objects.filter(pk=self.tienda.pk).update(plan_desde=date(2026, 10, 20))
        self.tienda.refresh_from_db()
        for dia in (2, 3, 4, 21):
            self.cobrado(date(2026, 10, dia))
        self.assertEqual(services.calcular_excedente(self.tienda, date(2026, 10, 1)).pedidos, 1)


class RecordatoriosYCierreTests(ConPlan):
    def setUp(self):
        super().setUp()
        self.dar_plan()
        [self.cargo] = services.generar_mensualidades(date(2026, 10, 26))

    def correos(self, hoy):
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.revisar_cobros(hoy)
        return list(mail.outbox)

    def test_avisa_antes_el_dia_que_vence_y_el_ultimo_dia_una_sola_vez(self):
        self.assertEqual(self.correos(date(2026, 10, 27)), [])
        [aviso] = self.correos(date(2026, 10, 29))
        self.assertEqual(aviso.subject, 'Tu mensualidad de Multimix RD vence el 1 de noviembre')
        self.assertCountEqual(aviso.to, ['vendedor@example.com', 'tienda@example.com'])
        self.assertIn('RD$ 1,000.00', aviso.body)
        self.assertIn('Banco del dueño', aviso.body)
        self.assertEqual(self.correos(date(2026, 10, 30)), [])
        [aviso] = self.correos(date(2026, 11, 1))
        self.assertEqual(aviso.subject, 'Pago pendiente: tu tienda en Multimix RD')
        self.assertIn('5 de noviembre', aviso.body)
        self.assertEqual(self.correos(date(2026, 11, 2)), [])
        [aviso] = self.correos(date(2026, 11, 4))
        self.assertTrue(aviso.subject.startswith('Último día'))
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.avisos, ['por_vencer', 'ultimo_dia', 'vence_hoy'])

    def test_el_dia_5_se_cierra_la_tienda_que_no_pago(self):
        self.correos(date(2026, 11, 4))
        self.tienda.refresh_from_db()
        self.assertTrue(self.tienda.activa)
        correos = self.correos(date(2026, 11, 5))
        self.tienda.refresh_from_db()
        self.assertEqual((self.tienda.activa, self.tienda.cerrada_por_falta_de_pago), (False, True))
        self.assertEqual({tuple(sorted(correo.to)) for correo in correos},
                         {('tienda@example.com', 'vendedor@example.com'), ('sitio@example.com',)})
        # Cerrada, nadie la ve.
        self.assertEqual(self.client.get(self.tienda.get_absolute_url()).status_code, 404)

    def test_con_el_comprobante_en_revision_no_se_cierra(self):
        with self.captureOnCommitCallbacks(execute=True):
            services.subir_comprobante(self.cargo, imagen_de_prueba(), 'REF-9')
        self.correos(date(2026, 11, 7))
        self.tienda.refresh_from_db()
        self.assertTrue(self.tienda.activa)

    def test_pagada_no_avisa_ni_se_cierra(self):
        services.aprobar_cargo(self.cargo, self.admin)
        self.assertEqual(self.correos(date(2026, 11, 1)), [])
        self.correos(date(2026, 11, 9))
        self.tienda.refresh_from_db()
        self.assertTrue(self.tienda.activa)

    def test_queda_cerrada_hasta_que_el_administrador_la_habilita(self):
        self.correos(date(2026, 11, 5))
        services.aprobar_cargo(self.cargo, self.admin)
        self.tienda.refresh_from_db()
        self.assertFalse(self.tienda.activa)
        self.client.force_login(self.admin)
        self.client.post(reverse('admin:tiendas_tienda_changelist'), {
            'action': 'habilitar', '_selected_action': [self.tienda.pk],
        })
        self.tienda.refresh_from_db()
        self.assertEqual((self.tienda.activa, self.tienda.cerrada_por_falta_de_pago), (True, False))

    def test_lo_que_ya_estaba_vencido_al_habilitarla_no_la_vuelve_a_cerrar(self):
        with mock.patch('django.utils.timezone.now', return_value=en_fecha(date(2026, 11, 5))):
            self.correos(date(2026, 11, 5))
            services.habilitar_tienda(self.tienda, self.admin)
        self.correos(date(2026, 11, 8))
        self.tienda.refresh_from_db()
        self.assertTrue(self.tienda.activa)

    def test_el_vendedor_no_se_habilita_a_si_mismo(self):
        self.correos(date(2026, 11, 5))
        self.client.force_login(self.vendedor)
        self.client.post(reverse('admin:tiendas_tienda_changelist'), {
            'action': 'habilitar', '_selected_action': [self.tienda.pk],
        })
        with self.assertRaises(services.CargoError):
            services.habilitar_tienda(self.tienda, self.vendedor)
        self.tienda.refresh_from_db()
        self.assertFalse(self.tienda.activa)


class ComprobantesTests(ConPlan):
    # En las pruebas el almacenamiento privado ya es una carpeta temporal (settings.PRIVADO_ROOT).
    def setUp(self):
        super().setUp()
        self.dar_plan()
        [self.cargo] = services.generar_mensualidades(date(2026, 10, 26))
        self.ajena = self.dar_plan(tienda_de_prueba('Fitnes RD'))
        [self.cargo_ajeno] = services.generar_mensualidades(date(2026, 10, 26))

    def test_la_tienda_sube_el_comprobante_y_el_dueno_lo_aprueba(self):
        self.client.force_login(self.vendedor)
        url = reverse('admin:planes_cargo_change', args=[self.cargo.pk])
        pagina = self.client.get(url)
        self.assertContains(pagina, 'Banco del dueño')
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(url, {'referencia': 'REF-1', 'archivo': imagen_de_prueba()})
        self.assertEqual(respuesta.status_code, 302)
        self.cargo.refresh_from_db()
        self.assertEqual((self.cargo.estado, self.cargo.referencia), (Estado.EN_REVISION, 'REF-1'))
        self.assertTrue(self.cargo.comprobante.name.endswith('.webp'))
        aviso = [correo for correo in mail.outbox if correo.to == ['sitio@example.com']][0]
        self.assertIn('Comprobante de Multimix RD', aviso.subject)
        # El vendedor no lo aprueba.
        self.client.post(reverse('admin:planes_cargo_changelist'), {
            'action': 'aprobar', '_selected_action': [self.cargo.pk],
        })
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.estado, Estado.EN_REVISION)
        with self.assertRaises(services.CargoError):
            services.aprobar_cargo(self.cargo, self.vendedor)
        # El dueño ve el comprobante y lo aprueba; la tienda recibe el aviso.
        self.client.force_login(self.admin)
        comprobante = self.client.get(reverse('admin:planes_cargo_comprobante', args=[self.cargo.pk]))
        self.assertEqual((comprobante.status_code, comprobante['Content-Type']), (200, 'image/webp'))
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin:planes_cargo_changelist'), {
                'action': 'aprobar', '_selected_action': [self.cargo.pk],
            })
        self.cargo.refresh_from_db()
        self.assertEqual((self.cargo.estado, self.cargo.revisado_por), (Estado.PAGADO, self.admin))
        self.assertTrue(mail.outbox[0].subject.startswith('Recibimos tu pago'))

    def test_sin_foto_no_hay_aviso_y_el_rechazo_devuelve_a_pendiente(self):
        self.client.force_login(self.vendedor)
        url = reverse('admin:planes_cargo_change', args=[self.cargo.pk])
        self.assertEqual(self.client.post(url, {'referencia': 'REF-1'}).status_code, 200)
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.estado, Estado.PENDIENTE)
        services.subir_comprobante(self.cargo, imagen_de_prueba(), 'REF-2')
        with self.captureOnCommitCallbacks(execute=True):
            services.rechazar_comprobante(self.cargo, self.admin, 'No llegó el depósito')
        self.cargo.refresh_from_db()
        self.assertEqual((self.cargo.estado, self.cargo.nota), (Estado.PENDIENTE, 'No llegó el depósito'))
        self.assertIn('No llegó el depósito', mail.outbox[-1].body)

    def test_cada_tienda_ve_solo_sus_cargos(self):
        self.client.force_login(self.vendedor)
        lista = self.client.get(reverse('admin:planes_cargo_changelist'))
        self.assertEqual(list(lista.context['cl'].result_list), [self.cargo])
        for nombre in ('admin:planes_cargo_change', 'admin:planes_cargo_comprobante'):
            self.assertNotEqual(self.client.get(reverse(nombre, args=[self.cargo_ajeno.pk])).status_code, 200, nombre)
        respuesta = self.client.post(reverse('admin:planes_cargo_change', args=[self.cargo_ajeno.pk]), {
            'referencia': 'X', 'archivo': imagen_de_prueba(),
        })
        self.assertNotEqual(respuesta.status_code, 200)
        self.cargo_ajeno.refresh_from_db()
        self.assertEqual(self.cargo_ajeno.estado, Estado.PENDIENTE)
        # Tampoco crea ni borra cargos.
        self.assertEqual(self.client.get(reverse('admin:planes_cargo_add')).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:planes_cargo_delete', args=[self.cargo.pk]),
                                          {'post': 'yes'}).status_code, 403)

    def test_el_panel_le_muestra_su_plan_y_lo_que_debe(self):
        self.client.force_login(self.vendedor)
        portada = self.client.get(reverse('admin:index'))
        self.assertContains(portada, 'Tu plan: Estándar')
        self.assertContains(portada, 'Debes RD$ 1,000.00')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('admin:index')), 'Pagos de las tiendas')

    def test_el_vendedor_ve_su_plan_pero_no_lo_cambia(self):
        self.client.force_login(self.vendedor)
        editar = reverse('admin:tiendas_tienda_change', args=[self.tienda.pk])
        pagina = self.client.get(editar)
        self.assertContains(pagina, 'Plan Estándar')
        self.assertNotContains(pagina, 'name="plan"')
        premium = Plan.objects.get(nombre='Premium')
        self.client.post(editar, {'nombre': 'Multimix RD', 'plan': premium.pk, 'activa': ''})
        self.tienda.refresh_from_db()
        self.assertEqual((self.tienda.plan, self.tienda.activa), (self.plan, True))


class ElAdministradorEditaTodoTests(ConPlan):
    """Pedido del dueño el 2026-10-26: todo lo de los planes y los cobros se cambia desde el panel."""

    def setUp(self):
        super().setUp()
        self.dar_plan()
        [self.cargo] = services.generar_mensualidades(date(2026, 10, 26))
        self.client.force_login(self.admin)

    def test_cambia_los_planes(self):
        url = reverse('admin:planes_plan_change', args=[self.plan.pk])
        respuesta = self.client.post(url, {
            'nombre': 'Estándar', 'descripcion': 'Nuevo texto', 'mensualidad': '1500', 'activo': 'on', 'orden': '2',
            'pedidos_incluidos': '', 'porcentaje_excedente': '2.5', 'anuncios_portada': '2',
            'productos_patrocinados': '6', 'videos_portada': '1',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(
            (self.plan.mensualidad, self.plan.pedidos_incluidos, self.plan.porcentaje_excedente,
             self.plan.anuncios_portada, self.plan.productos_patrocinados, self.plan.videos_portada),
            (D('1500.00'), None, D('2.50'), 2, 6, 1),
        )
        # Y crea otros.
        self.assertEqual(self.client.get(reverse('admin:planes_plan_add')).status_code, 200)

    def test_los_dias_de_gracia_y_de_aviso_estan_en_la_configuracion(self):
        pagina = self.client.get(reverse('admin:core_configuraciontienda_change', args=[1]))
        self.assertContains(pagina, 'name="dias_de_gracia"')
        self.assertContains(pagina, 'name="dias_aviso_mensualidad"')

    def datos_del_cargo(self, **cambios):
        datos = {'tipo': 'mensualidad', 'periodo': '2026-11-01', 'concepto': self.cargo.concepto, 'detalle': '',
                 'monto': '1000.00', 'vence': '2026-11-01', 'estado': self.cargo.estado, 'nota': ''}
        datos.update(cambios)
        return datos

    def test_cambia_monto_fechas_y_estado_del_cargo(self):
        url = reverse('admin:planes_cargo_change', args=[self.cargo.pk])
        self.client.post(url, self.datos_del_cargo(monto='800.00', vence='2026-11-03'))
        self.cargo.refresh_from_db()
        self.assertEqual((self.cargo.monto, self.cargo.vence), (D('800.00'), date(2026, 11, 3)))
        # Pagado por el formulario: igual que la accion, con el correo a la tienda.
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, self.datos_del_cargo(monto='800.00', vence='2026-11-03', estado='pagado'))
        self.cargo.refresh_from_db()
        self.assertEqual((self.cargo.estado, self.cargo.revisado_por), (Estado.PAGADO, self.admin))
        self.assertTrue(mail.outbox[0].subject.startswith('Recibimos tu pago'))
        # Lo reabre y lo anula.
        self.client.post(url, self.datos_del_cargo(monto='800.00', vence='2026-11-03', estado='pendiente'))
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.estado, Estado.PENDIENTE)
        self.client.post(url, self.datos_del_cargo(estado='anulado', nota='Mes de regalo'))
        self.cargo.refresh_from_db()
        self.assertEqual((self.cargo.estado, self.cargo.nota), (Estado.ANULADO, 'Mes de regalo'))

    def test_pendiente_desde_revision_es_rechazar_el_comprobante(self):
        services.subir_comprobante(self.cargo, imagen_de_prueba(), 'REF-1')
        url = reverse('admin:planes_cargo_change', args=[self.cargo.pk])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, self.datos_del_cargo(estado='pendiente', nota='No llegó'))
        self.cargo.refresh_from_db()
        self.assertEqual((self.cargo.estado, self.cargo.nota), (Estado.PENDIENTE, 'No llegó'))
        self.assertTrue(mail.outbox[-1].subject.startswith('No pudimos confirmar tu pago'))
