"""Programa de referidos entre tiendas (pedido del dueño el 2026-11-02) y QR de la tienda en el panel."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from planes import services as planes
from planes.models import Cargo, Plan
from tiendas.models import SolicitudTienda, Tienda
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

from . import services
from .models import PremioReferido, TiendaReferida

D = Decimal
CLAVE = 'clave-segura-123'
Usuario = get_user_model()


class ConTiendas(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser('admin', 'dueno@example.com', CLAVE)
        self.plan = Plan.objects.get(nombre='Estándar')
        self.plan.mensualidad = D('1000')
        self.plan.save()
        self.referente = self.tienda('Multimix RD', 'vendedor')
        self.codigo = services.codigo_de(self.vendedor).codigo

    def tienda(self, nombre, usuario):
        tienda = tienda_de_prueba(nombre, correo=f'{usuario}@example.com')
        Tienda.objects.filter(pk=tienda.pk).update(plan=self.plan, plan_desde=date(2026, 9, 1))
        tienda.refresh_from_db()
        vendedor = Usuario.objects.create_user(usuario, f'{usuario}@example.com', CLAVE)
        tienda.usuarios.add(vendedor)
        dar_acceso_al_panel([vendedor])
        setattr(self, usuario, vendedor)
        return tienda

    def invitar(self, nombre):
        """Una solicitud con el codigo del referente y la tienda que el administrador crea con ella."""
        tienda = self.tienda(nombre, nombre.lower().replace(' ', ''))
        solicitud = SolicitudTienda.objects.create(
            nombre_responsable='Ana', nombre_comercial=nombre, correo='a@example.com', telefono='8095551234',
            descripcion='Vendemos cosas muy buenas para todos.', codigo_referido=self.codigo, tienda=tienda,
        )
        services.vincular_tienda(solicitud)
        return tienda

    def pagar_primera(self, tienda, hoy=date(2026, 10, 25)):
        [cargo] = [c for c in planes.generar_mensualidades(hoy) if c.tienda_id == tienda.pk]
        with self.captureOnCommitCallbacks(execute=True):
            planes.aprobar_cargo(cargo, self.admin)
        return cargo


class SolicitudConCodigoTests(ConTiendas):
    def test_el_enlace_deja_el_codigo_puesto_en_la_solicitud(self):
        self.client.get(reverse('referidos:clic', args=[self.codigo]))
        pagina = self.client.get(reverse('tiendas:solicitar_tienda'))
        self.assertEqual(pagina.context['formulario'].initial['codigo_referido'], self.codigo)
        datos = {
            'nombre_responsable': 'Ana Pérez', 'nombre_comercial': 'Dulces Ana', 'correo': 'ana@example.com',
            'telefono': '809-555-1234', 'rubro': 'otro', 'descripcion': 'Dulces caseros de coco y leche.',
            'codigo_referido': self.codigo.lower(), 'acepta': 'on', 'sitio_web': '',
        }
        self.client.post(reverse('tiendas:solicitar_tienda'), datos)
        self.assertEqual(SolicitudTienda.objects.get().codigo_referido, self.codigo)

    def test_un_codigo_que_no_existe_se_rechaza(self):
        datos = {
            'nombre_responsable': 'Ana Pérez', 'nombre_comercial': 'Dulces Ana', 'correo': 'ana@example.com',
            'telefono': '809-555-1234', 'rubro': 'otro', 'descripcion': 'Dulces caseros de coco y leche.',
            'codigo_referido': 'NOEXISTE', 'acepta': 'on', 'sitio_web': '',
        }
        respuesta = self.client.post(reverse('tiendas:solicitar_tienda'), datos)
        self.assertContains(respuesta, 'No encontramos ese código')
        self.assertFalse(SolicitudTienda.objects.exists())

    def test_al_elegir_la_tienda_en_la_solicitud_queda_vinculada(self):
        invitada = self.invitar('Dulces Ana')
        relacion = TiendaReferida.objects.get(tienda=invitada)
        self.assertEqual((relacion.referente, relacion.codigo, relacion.activa_desde), (self.referente, self.codigo, None))
        # No se vincula dos veces ni una tienda consigo misma.
        solicitud = SolicitudTienda.objects.get(tienda=invitada)
        self.assertIsNone(services.vincular_tienda(solicitud))
        solicitud.tienda = self.referente
        self.assertIsNone(services.vincular_tienda(solicitud))


class PremiosTests(ConTiendas):
    def test_la_invitada_tiene_10_por_ciento_en_su_primera_mensualidad(self):
        invitada = self.invitar('Dulces Ana')
        cargo = self.pagar_primera(invitada)
        self.assertEqual(cargo.monto, D('900.00'))
        self.assertIn('Bienvenida', cargo.detalle)
        # La siguiente ya va completa.
        [siguiente] = [c for c in planes.generar_mensualidades(date(2026, 11, 25)) if c.tienda_id == invitada.pk]
        self.assertEqual(siguiente.monto, D('1000.00'))

    def test_cada_dos_activas_dan_un_premio_que_se_usa_en_la_mensualidad(self):
        primera = self.invitar('Dulces Ana')
        segunda = self.invitar('Flores Luz')
        # El referente ya tiene su mensualidad de noviembre creada y sin pagar.
        [del_referente] = [c for c in planes.generar_mensualidades(date(2026, 10, 25)) if c.tienda_id == self.referente.pk]
        for invitada in (primera, segunda):
            cargo = Cargo.objects.get(tienda=invitada, tipo=Cargo.Tipo.MENSUALIDAD)
            with self.captureOnCommitCallbacks(execute=True):
                planes.aprobar_cargo(cargo, self.admin)
        self.assertEqual(TiendaReferida.objects.filter(referente=self.referente, activa_desde__isnull=False).count(), 2)
        premio = PremioReferido.objects.get(tienda=self.referente)
        self.assertEqual((premio.numero, premio.descuento, premio.anuncios_extra), (1, D('25'), 1))
        # Se aplico a la mensualidad que estaba por pagar.
        del_referente.refresh_from_db()
        self.assertEqual(del_referente.monto, D('750.00'))
        self.assertEqual(premio.cargo_id, del_referente.pk)
        self.assertTrue(any('premio' in correo.subject.lower() for correo in mail.outbox))

    def test_una_sola_activa_no_da_premio_y_pagar_dos_veces_no_cuenta_doble(self):
        invitada = self.invitar('Dulces Ana')
        cargo = self.pagar_primera(invitada)
        planes.aprobar_cargo(cargo, self.admin)
        self.assertFalse(PremioReferido.objects.exists())
        self.assertEqual(services.programa_de(self.referente)['avance'], 1)

    def test_el_premio_da_un_anuncio_extra_en_la_portada(self):
        self.assertEqual(planes.limite_de_anuncios(self.referente), self.plan.anuncios_portada)
        PremioReferido.objects.create(
            tienda=self.referente, numero=1, descuento=D('25'), anuncios_extra=1,
            anuncios_hasta=timezone.localdate() + timedelta(days=30), vence=timezone.localdate() + timedelta(days=90),
        )
        self.assertEqual(planes.limite_de_anuncios(self.referente), self.plan.anuncios_portada + 1)
        # Uno vencido ya no suma.
        PremioReferido.objects.filter(tienda=self.referente).update(anuncios_hasta=timezone.localdate() - timedelta(days=1))
        self.assertEqual(planes.limite_de_anuncios(self.referente), self.plan.anuncios_portada)

    def test_un_premio_vencido_no_se_aplica(self):
        PremioReferido.objects.create(
            tienda=self.referente, numero=1, descuento=D('25'), anuncios_extra=1,
            anuncios_hasta=date(2026, 1, 1), vence=date(2026, 1, 31),
        )
        [cargo] = [c for c in planes.generar_mensualidades(date(2026, 10, 25)) if c.tienda_id == self.referente.pk]
        self.assertEqual(cargo.monto, D('1000.00'))


class EscaleraDePremiosTests(ConTiendas):
    """Pedido del dueño el 2026-11-05: 2 activas = 25% + anuncio; 4 = 50% + destacada 15 dias; 6 = mes gratis +
    insignia "Tienda embajadora" (una sola vez); despues, cada 2 vuelve el primer premio."""

    def activar(self, cuantas):
        invitadas = [self.invitar(f'Invitada {n}') for n in range(cuantas)]
        planes.generar_mensualidades(date(2026, 10, 25))
        for invitada in invitadas:
            cargo = Cargo.objects.get(tienda=invitada, tipo=Cargo.Tipo.MENSUALIDAD, periodo=date(2026, 11, 1))
            with self.captureOnCommitCallbacks(execute=True):
                planes.aprobar_cargo(cargo, self.admin)

    def mensualidad(self, hoy):
        return [c for c in planes.generar_mensualidades(hoy) if c.tienda_id == self.referente.pk][0]

    def test_los_niveles_y_el_mes_gratis(self):
        from tiendas.services import tiendas_destacadas

        self.activar(8)
        premios = list(PremioReferido.objects.filter(tienda=self.referente).order_by('numero'))
        self.assertEqual([(p.numero, p.descuento, p.anuncios_extra) for p in premios],
                         [(1, D('25'), 1), (2, D('50'), 0), (3, D('100'), 0), (4, D('25'), 1)])
        self.assertIsNone(premios[0].destacada_hasta)
        self.assertEqual(premios[1].destacada_hasta, timezone.localdate() + timedelta(days=15))
        self.referente.refresh_from_db()
        self.assertEqual(self.referente.embajadora_desde, timezone.localdate())
        # Sale entre las destacadas por el premio, aunque nadie la marco.
        self.assertFalse(self.referente.destacada)
        self.assertIn(self.referente, tiendas_destacadas())
        PremioReferido.objects.filter(pk=premios[1].pk).update(destacada_hasta=timezone.localdate() - timedelta(days=1))
        self.assertNotIn(self.referente, tiendas_destacadas())

        # Un premio por mensualidad, en orden: noviembre 25%, diciembre 50%, enero gratis y febrero 25%.
        noviembre = Cargo.objects.get(tienda=self.referente, periodo=date(2026, 11, 1))
        self.assertEqual(noviembre.monto, D('750.00'))
        self.assertEqual(self.mensualidad(date(2026, 11, 25)).monto, D('500.00'))
        enero = self.mensualidad(date(2026, 12, 25))
        self.assertEqual(enero.estado, Cargo.Estado.ANULADO)
        self.assertTrue(enero.nota.startswith(services.NOTA_MES_GRATIS))
        self.assertIn('-100%', enero.detalle)
        febrero = self.mensualidad(date(2027, 1, 25))
        self.assertEqual(febrero.monto, D('750.00'))
        self.assertEqual(PremioReferido.objects.get(tienda=self.referente, numero=4).cargo_id, febrero.pk)
        # El mes gratis queda usado: no vuelve a aplicarse aunque su mensualidad este anulada.
        programa = services.programa_de(self.referente)
        tercero = next(p for p in programa['premios'] if p.numero == 3)
        self.assertTrue(tercero.mes_gratis)
        self.assertFalse(tercero.disponible)
        self.assertTrue(programa['embajadora'])

    def test_la_insignia_se_ve_en_la_tienda_y_en_el_directorio_y_no_se_quita(self):
        self.activar(6)
        self.referente.refresh_from_db()
        self.assertContains(self.client.get(self.referente.get_absolute_url()), 'Tienda embajadora')
        self.assertContains(self.client.get(reverse('tiendas:directorio')), 'Tienda embajadora')
        # Si una invitada se va, el premio y la insignia se quedan.
        Tienda.objects.filter(invitada_por__referente=self.referente).update(activa=False)
        self.referente.refresh_from_db()
        self.assertIsNotNone(self.referente.embajadora_desde)

    def test_el_panel_muestra_la_escalera_y_el_proximo_premio(self):
        self.activar(2)
        self.client.force_login(self.vendedor)
        inicio = self.client.get(reverse('admin:index'))
        self.assertContains(inicio, 'tu tienda destacada en la portada por 15 días')
        self.assertContains(inicio, 'un mes gratis')
        self.assertContains(inicio, 'Tienda embajadora')
        self.assertContains(inicio, 'para tu próximo premio (50%)')
        self.assertEqual(inicio.context['programa']['proximo']['numero'], 2)

    def test_el_correo_del_mes_gratis(self):
        self.activar(6)
        correo = [m for m in mail.outbox if 'premio' in m.subject.lower()][-1]
        self.assertIn('Un mes gratis', correo.body)
        self.assertIn('Tienda embajadora', correo.body)


class PanelDelVendedorTests(ConTiendas):
    def test_el_inicio_muestra_el_avance_y_solo_sus_premios(self):
        ajena = self.tienda('Otra Tienda', 'ajeno')
        PremioReferido.objects.create(
            tienda=ajena, numero=1, descuento=D('25'), anuncios_extra=1,
            anuncios_hasta=date(2099, 1, 1), vence=date(2099, 1, 1),
        )
        self.client.force_login(self.vendedor)
        inicio = self.client.get(reverse('admin:index'))
        self.assertContains(inicio, 'Invita tiendas y gana premios')
        self.assertContains(inicio, 'Llevas <strong>0 de 2</strong>', html=False)
        self.assertEqual(inicio.context['programa']['premios'], [])
        # El vendedor no ve las tablas del programa: solo el administrador principal.
        self.assertEqual(self.client.get(reverse('admin:referidos_premioreferido_changelist')).status_code, 403)


class QrDeLaTiendaTests(ConTiendas):
    def test_el_vendedor_baja_el_qr_de_su_tienda_y_no_el_de_otra(self):
        ajena = self.tienda('Otra Tienda', 'ajeno')
        self.client.force_login(self.vendedor)
        respuesta = self.client.get(reverse('admin:qr_tienda', args=[self.referente.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'image/png')
        self.assertTrue(respuesta.content.startswith(b'\x89PNG'))
        self.assertEqual(self.client.get(reverse('admin:qr_tienda', args=[ajena.pk])).status_code, 404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('admin:qr_tienda', args=[ajena.pk])).status_code, 200)
