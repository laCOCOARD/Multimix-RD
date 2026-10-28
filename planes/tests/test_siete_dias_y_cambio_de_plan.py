"""Pedido del dueño el 2026-10-28: cada anuncio dura 7 dias desde que se aprueba y, vencido, la tienda pone otro
(Estandar: 1 con foto; Premium: 2 con foto y 1 video); y la tienda pide cambiar de plan, que aprueba el administrador
principal (la mensualidad nueva se cobra desde el proximo dia 1)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from catalogo.tests.test_modelos import imagen_de_prueba
from planes import services
from planes.models import DIAS_DEL_ANUNCIO, Anuncio, Cargo, Plan
from tiendas.models import Tienda

from .test_anuncios import ConAnuncios


class SieteDiasTests(ConAnuncios):
    def test_los_planes_de_fabrica(self):
        estandar, premium = Plan.objects.get(nombre='Estándar'), Plan.objects.get(nombre='Premium')
        self.assertEqual((estandar.anuncios_portada, estandar.videos_portada), (1, 0))
        self.assertEqual((premium.anuncios_portada, premium.videos_portada), (2, 1))

    def test_al_aprobarlo_sale_siete_dias_y_vencido_deja_poner_otro(self):
        self.con_plan(self.tienda)
        anuncio = self.anuncio(aprobado=False)
        with self.captureOnCommitCallbacks(execute=True):
            services.aprobar_anuncio(anuncio, self.admin)
        anuncio.refresh_from_db()
        self.assertAlmostEqual(anuncio.vigente_hasta - anuncio.vigente_desde, timedelta(days=DIAS_DEL_ANUNCIO),
                               delta=timedelta(seconds=1))
        self.assertIn('hasta el', mail.outbox[-1].body)
        self.assertEqual(services.anuncios_para_la_portada(), [anuncio])
        # Mientras dura ocupa el cupo del Estandar.
        otro = Anuncio(tienda=self.tienda, titulo='Otro', imagen=imagen_de_prueba())
        with self.assertRaisesMessage(ValidationError, 'Tu plan permite 1 anuncio a la vez'):
            otro.full_clean()
        # A los 7 dias ya no sale y el cupo queda libre.
        despues = timezone.now() + timedelta(days=DIAS_DEL_ANUNCIO, minutes=1)
        with mock.patch('django.utils.timezone.now', return_value=despues):
            self.assertEqual(services.anuncios_para_la_portada(), [])
            self.assertTrue(Anuncio.objects.get(pk=anuncio.pk).vencido)
            otro.full_clean()

    def test_volver_a_aprobarlo_tras_un_cambio_no_alarga_la_semana(self):
        self.con_plan(self.tienda)
        anuncio = self.anuncio(aprobado=False)
        services.aprobar_anuncio(anuncio, self.admin)
        anuncio.refresh_from_db()
        fin = anuncio.vigente_hasta
        Anuncio.objects.filter(pk=anuncio.pk).update(aprobado=False)
        services.aprobar_anuncio(Anuncio.objects.get(pk=anuncio.pk), self.admin)
        self.assertEqual(Anuncio.objects.get(pk=anuncio.pk).vigente_hasta, fin)

    def test_el_premium_tiene_dos_con_foto(self):
        self.con_plan(self.tienda, Plan.objects.get(nombre='Premium'))
        self.anuncio(titulo='Uno')
        self.anuncio(titulo='Dos')
        tercero = Anuncio(tienda=self.tienda, titulo='Tres', imagen=imagen_de_prueba())
        with self.assertRaisesMessage(ValidationError, 'Tu plan permite 2 anuncios a la vez'):
            tercero.full_clean()

    def test_la_tienda_no_cambia_las_fechas_y_ve_hasta_cuando_sale(self):
        self.con_plan(self.tienda)
        anuncio = self.anuncio(aprobado=False)
        services.aprobar_anuncio(anuncio, self.admin)
        self.client.force_login(self.vendedor)
        lista = self.client.get(reverse('admin:planes_anuncio_changelist'))
        self.assertContains(lista, 'Hasta el')
        formulario = self.client.get(reverse('admin:planes_anuncio_change', args=[anuncio.pk]))
        self.assertContains(formulario, f'{DIAS_DEL_ANUNCIO} días en la portada')
        self.assertNotContains(formulario, 'name="vigente_hasta')


class CambioDePlanTests(ConAnuncios):
    def setUp(self):
        super().setUp()
        self.premium = Plan.objects.get(nombre='Premium')
        self.con_plan(self.tienda)
        self.client.force_login(self.vendedor)
        self.url = reverse('admin:tiendas_tienda_plan', args=[self.tienda.pk])

    def deposito(self):
        return Cargo.objects.get(tienda=self.tienda, tipo=Cargo.Tipo.CAMBIO_DE_PLAN)

    def test_subir_de_plan_pide_el_deposito_y_al_aprobarlo_cambia_solo(self):
        pagina = self.client.get(self.url)
        self.assertContains(pagina, 'Tu plan ahora: <strong>Estándar</strong>', html=False)
        self.assertContains(pagina, 'Para cambiar hoy depositas <strong>RD$ 1,300.00</strong>', html=False)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {'plan': self.premium.pk})
        self.tienda.refresh_from_db()
        self.assertEqual((self.tienda.plan, self.tienda.plan_pedido), (self.estandar, self.premium))
        deposito = self.deposito()
        self.assertEqual((deposito.monto, deposito.estado, deposito.plan), (Decimal('1300.00'), 'pendiente', self.premium))
        self.assertIn('debe depositar la diferencia de este mes: RD$ 1,300.00', mail.outbox[-1].body)
        self.assertContains(self.client.get(self.url), 'Falta tu depósito de RD$ 1,300.00')
        # No cuenta como deuda que cierra la tienda ni en el aviso rojo del inicio.
        self.assertEqual(services.estado_de_cuenta(self.tienda).pendientes, [])
        self.assertNotIn(deposito, services._vencidos_sin_gracia(timezone.localdate() + timedelta(days=60)))
        # Sin el deposito el administrador no puede aprobar el cambio, ni el vendedor aprobarse solo.
        with self.assertRaisesMessage(services.CambioDePlanError, 'todavía no ha pagado la diferencia'):
            services.aprobar_cambio_de_plan(self.tienda, self.admin)
        with self.assertRaises(services.CambioDePlanError):
            services.aprobar_cambio_de_plan(self.tienda, self.vendedor)
        self.client.force_login(self.admin)
        self.client.post(reverse('admin:tiendas_tienda_changelist'), {
            'action': 'aprobar_cambio_de_plan', '_selected_action': [self.tienda.pk],
        })
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.plan, self.estandar)
        # La tienda sube su comprobante y el administrador aprueba el pago: el plan cambia solo.
        services.subir_comprobante(deposito, imagen_de_prueba(), 'REF-1')
        with self.captureOnCommitCallbacks(execute=True):
            services.aprobar_cargo(deposito, self.admin)
        self.tienda.refresh_from_db()
        self.assertEqual((self.tienda.plan, self.tienda.plan_pedido), (self.premium, None))
        self.assertEqual(self.tienda.plan_desde, timezone.localdate())
        self.assertIn('desde hoy tu tienda tiene el plan Premium', mail.outbox[-1].body)

    def test_bajar_de_plan_no_lleva_deposito_y_lo_aprueba_el_administrador(self):
        basico = Plan.objects.get(nombre='Básico')
        self.client.post(self.url, {'plan': basico.pk})
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.plan_pedido, basico)
        self.assertFalse(Cargo.objects.filter(tipo=Cargo.Tipo.CAMBIO_DE_PLAN).exists())
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('admin:index')), 'Cambios de plan pedidos')
        self.client.post(reverse('admin:tiendas_tienda_changelist'), {
            'action': 'aprobar_cambio_de_plan', '_selected_action': [self.tienda.pk],
        })
        self.tienda.refresh_from_db()
        self.assertEqual((self.tienda.plan, self.tienda.plan_pedido), (basico, None))

    def test_con_pagos_vencidos_no_puede_pedir(self):
        Cargo.objects.create(tienda=self.tienda, tipo=Cargo.Tipo.MENSUALIDAD, periodo=date(2026, 10, 1),
                             concepto='Mensualidad', monto=Decimal('1200'), vence=timezone.localdate())
        self.assertContains(self.client.get(self.url), 'Primero paga lo pendiente')
        self.client.post(self.url, {'plan': self.premium.pk})
        self.tienda.refresh_from_db()
        self.assertIsNone(self.tienda.plan_pedido)
        # La mensualidad del mes que viene (creada antes de vencer) no lo impide.
        Cargo.objects.update(vence=timezone.localdate() + timedelta(days=3))
        self.client.post(self.url, {'plan': self.premium.pk})
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.plan_pedido, self.premium)

    def test_la_mensualidad_del_mes_que_viene_ya_creada_pasa_al_plan_nuevo(self):
        hoy = date(2026, 10, 28)
        with mock.patch('planes.services._hoy', return_value=hoy):
            Tienda.objects.filter(pk=self.tienda.pk).update(plan_desde=date(2026, 9, 1))
            services.generar_mensualidades(hoy)
            Cargo.objects.filter(tienda=self.tienda, periodo=date(2026, 10, 1)).update(estado='pagado')
            cargo = Cargo.objects.get(tienda=self.tienda, periodo=date(2026, 11, 1))
            self.assertEqual(cargo.monto, self.estandar.mensualidad)
            services.pedir_cambio_de_plan(self.tienda, self.premium)
            services.aprobar_cargo(self.deposito(), self.admin)
        cargo.refresh_from_db()
        self.assertEqual(cargo.monto, self.premium.mensualidad)
        self.assertIn('Plan Premium', cargo.concepto)
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.plan, self.premium)

    def test_retirar_y_rechazar_anulan_el_deposito(self):
        self.client.post(self.url, {'plan': self.estandar.pk})  # ya lo tiene
        self.tienda.refresh_from_db()
        self.assertIsNone(self.tienda.plan_pedido)
        self.client.post(self.url, {'plan': self.premium.pk})
        self.client.post(self.url, {'cancelar': '1'})
        self.tienda.refresh_from_db()
        self.assertIsNone(self.tienda.plan_pedido)
        self.assertEqual(self.deposito().estado, 'anulado')
        # Pide otra vez y el administrador lo rechaza.
        self.client.post(self.url, {'plan': self.premium.pk})
        self.tienda.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            services.rechazar_cambio_de_plan(self.tienda, self.admin)
        self.tienda.refresh_from_db()
        self.assertEqual((self.tienda.plan, self.tienda.plan_pedido), (self.estandar, None))
        self.assertFalse(Cargo.objects.filter(tipo=Cargo.Tipo.CAMBIO_DE_PLAN).exclude(estado='anulado').exists())
        self.assertIn('no aprobamos', mail.outbox[-1].body)

    def test_con_el_comprobante_enviado_ya_no_lo_retira_la_tienda(self):
        self.client.post(self.url, {'plan': self.premium.pk})
        services.subir_comprobante(self.deposito(), imagen_de_prueba(), 'REF-2')
        self.client.post(self.url, {'cancelar': '1'})
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.plan_pedido, self.premium)
        # Si ya se confirmo el pago, rechazarlo pide devolver el dinero primero.
        Cargo.objects.filter(pk=self.deposito().pk).update(estado='pagado')
        with self.assertRaisesMessage(services.CambioDePlanError, 'devuélvele el dinero'):
            services.rechazar_cambio_de_plan(self.tienda, self.admin)

    def test_solo_su_tienda(self):
        ajena = reverse('admin:tiendas_tienda_plan', args=[self.ajena.pk])
        self.assertEqual(self.client.get(ajena).status_code, 404)
        self.assertEqual(self.client.post(ajena, {'plan': self.premium.pk}).status_code, 404)
        self.ajena.refresh_from_db()
        self.assertIsNone(self.ajena.plan_pedido)

    def test_sin_plan_deposita_la_mensualidad_completa(self):
        Tienda.objects.filter(pk=self.tienda.pk).update(plan=None)
        self.assertContains(self.client.get(reverse('admin:tiendas_tienda_change', args=[self.tienda.pk])),
                            'Elegir un plan')
        self.client.post(self.url, {'plan': self.premium.pk})
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.plan_pedido, self.premium)
        self.assertEqual(self.deposito().monto, self.premium.mensualidad)
