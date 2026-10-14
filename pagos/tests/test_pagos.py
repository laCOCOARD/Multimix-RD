import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto, imagen_de_prueba
from pagos import services
from pagos.models import Pago
from pagos.proveedores import proveedor_de_tarjeta
from pedidos.models import Pedido
from pedidos.services import cambiar_estado, eliminar_pedido
from pedidos.tests.utiles import pedido_de_prueba
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

Estado = Pago.Estado
CARPETA = tempfile.mkdtemp()


def tearDownModule():
    shutil.rmtree(CARPETA, ignore_errors=True)


@override_settings(MEDIA_ROOT=CARPETA)
class PagoTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))
        self.pedido = pedido_de_prueba(self.producto, 2)
        self.url = reverse('pedidos:avisar_transferencia', args=[self.pedido.token])

    def pago(self):
        return Pago.objects.get(pedido=self.pedido, estado__in=Pago.VIGENTES)

    def test_cada_pedido_nace_con_su_pago_pendiente(self):
        pago = self.pago()
        self.assertEqual(
            (pago.estado, pago.monto, pago.metodo, pago.tienda, pago.referencia),
            (Estado.PENDIENTE, Decimal('2000.00'), 'transferencia', self.pedido.tienda, f'{self.pedido.numero}-P1'),
        )
        self.assertEqual(services.pago_vigente(self.pedido), pago)
        self.assertEqual(Pago.objects.count(), 1)

    def test_si_el_cliente_dice_en_el_checkout_que_ya_transfirio_queda_en_revision(self):
        pedido = pedido_de_prueba(self.producto, 1, transferencia_realizada=True, referencia_transferencia='REF-9')
        pago = pedido.pagos.get()
        self.assertEqual((pago.estado, pago.referencia_cliente), (Estado.EN_REVISION, 'REF-9'))

    def test_el_cliente_adjunta_el_comprobante_y_el_pedido_sigue_pendiente(self):
        respuesta = self.client.post(self.url, {'referencia_transferencia': 'REF-123', 'comprobante': imagen_de_prueba()})
        self.assertRedirects(respuesta, self.pedido.get_absolute_url(), fetch_redirect_response=False)
        pago = self.pago()
        self.pedido.refresh_from_db()
        self.assertEqual((pago.estado, pago.referencia_cliente), (Estado.EN_REVISION, 'REF-123'))
        self.assertTrue(pago.comprobante.name.startswith('comprobantes/'))
        self.assertTrue(pago.comprobante.name.endswith('.webp'))
        # El cliente nunca marca el pedido como pagado.
        self.assertEqual(self.pedido.estado, Pedido.Estado.PENDIENTE)
        self.assertTrue(self.pedido.transferencia_realizada)
        pagina = self.client.get(self.pedido.get_absolute_url())
        self.assertContains(pagina, 'Pago en revisión')
        self.assertContains(pagina, 'recibimos tu comprobante')

    def test_un_comprobante_nuevo_reemplaza_al_anterior(self):
        self.client.post(self.url, {'comprobante': imagen_de_prueba()})
        primero = self.pago().comprobante
        self.client.post(self.url, {'comprobante': imagen_de_prueba()})
        pago = self.pago()
        self.assertNotEqual(pago.comprobante.name, primero.name)
        self.assertFalse(primero.storage.exists(primero.name))
        self.assertEqual(Pago.objects.count(), 1)

    def test_no_acepta_archivos_que_no_son_imagenes(self):
        for archivo in (
            SimpleUploadedFile('comprobante.pdf', b'%PDF-1.4 falso', content_type='application/pdf'),
            SimpleUploadedFile('comprobante.png', b'esto no es una imagen', content_type='image/png'),
        ):
            self.client.post(self.url, {'comprobante': archivo})
            self.assertEqual(self.pago().estado, Estado.PENDIENTE)
            self.assertFalse(self.pago().comprobante)

    def test_aprobar_paga_el_pedido_y_repetirlo_no_cobra_dos_veces(self):
        usuario = get_user_model().objects.create_user('vendedor')
        services.registrar_comprobante(self.pedido, imagen_de_prueba(), 'REF-1')
        pago = services.aprobar_pago(self.pago(), usuario)
        self.pedido.refresh_from_db()
        self.assertEqual((pago.estado, pago.revisado_por, self.pedido.estado), (Estado.APROBADO, usuario, Pedido.Estado.PAGADO))
        self.assertIsNotNone(self.pedido.fecha_pago)
        fecha = self.pedido.fecha_pago

        # Una segunda aprobacion (doble clic, notificacion repetida) no cambia nada.
        services.aprobar_pago(pago, usuario)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.fecha_pago, fecha)
        self.assertEqual(Pago.objects.filter(pedido=self.pedido, estado=Estado.APROBADO).count(), 1)
        self.assertContains(self.client.get(self.pedido.get_absolute_url()), 'Pago confirmado')

    def test_rechazar_deja_al_cliente_enviar_otro_comprobante(self):
        services.registrar_comprobante(self.pedido, imagen_de_prueba(), 'REF-1')
        rechazado = services.rechazar_pago(self.pago(), nota='No aparece en el banco')
        self.pedido.refresh_from_db()
        self.assertEqual((rechazado.estado, self.pedido.estado), (Estado.RECHAZADO, Pedido.Estado.PENDIENTE))
        self.assertFalse(self.pedido.transferencia_realizada)
        with self.assertRaises(services.PagoError):
            services.aprobar_pago(rechazado)

        self.client.post(self.url, {'referencia_transferencia': 'REF-2', 'comprobante': imagen_de_prueba()})
        nuevo = self.pago()
        self.assertEqual((nuevo.estado, nuevo.referencia), (Estado.EN_REVISION, f'{self.pedido.numero}-P2'))

    def test_marcar_el_pedido_como_pagado_aprueba_su_pago(self):
        cambiar_estado(self.pedido, Pedido.Estado.PAGADO)
        self.assertEqual(self.pago().estado, Estado.APROBADO)

    def test_cancelar_el_pedido_cancela_el_pago_y_ya_no_admite_comprobantes(self):
        cambiar_estado(self.pedido, Pedido.Estado.CANCELADO)
        self.assertEqual(self.pedido.pagos.get().estado, Estado.CANCELADO)
        self.client.post(self.url, {'comprobante': imagen_de_prueba()})
        self.assertEqual(self.pedido.pagos.get().estado, Estado.CANCELADO)
        self.pedido.refresh_from_db()
        self.assertIsNone(services.pago_vigente(self.pedido))

    def test_el_efectivo_se_cobra_al_entregar(self):
        pedido = pedido_de_prueba(self.producto, 1, metodo_pago=Pedido.Pago.EFECTIVO_RECOGER)
        self.assertEqual(pedido.pagos.get().estado, Estado.PENDIENTE)
        with self.assertRaises(services.PagoError):
            services.registrar_comprobante(pedido, imagen_de_prueba())
        cambiar_estado(pedido, Pedido.Estado.ENTREGADO)
        self.assertEqual(pedido.pagos.get().estado, Estado.APROBADO)

    def test_un_pedido_anterior_a_los_pagos_abre_el_suyo_al_consultarlo(self):
        Pago.objects.all().delete()
        self.client.get(self.pedido.get_absolute_url())
        self.assertEqual(self.pago().estado, Estado.PENDIENTE)

    def test_eliminar_el_pedido_borra_su_pago_y_el_archivo(self):
        services.registrar_comprobante(self.pedido, imagen_de_prueba())
        comprobante = self.pago().comprobante
        eliminar_pedido(self.pedido)
        self.assertFalse(Pago.objects.exists())
        self.assertFalse(comprobante.storage.exists(comprobante.name))

    def test_sin_afiliacion_no_se_ofrece_tarjeta(self):
        self.assertIsNone(proveedor_de_tarjeta())
        # El checkout la anuncia, pero no hay nada que elegir ni campos para datos de tarjeta.
        self.client.post(f'/tienda/{self.pedido.tienda.slug}/carrito/agregar/', {'producto_id': self.producto.pk})
        pagina = self.client.get(f'/tienda/{self.pedido.tienda.slug}/pedido/checkout/')
        self.assertContains(pagina, 'Tarjeta de crédito o débito')
        self.assertContains(pagina, 'Próximamente')
        self.assertNotContains(pagina, 'value="tarjeta"')
        self.assertNotContains(pagina, 'cc-number')
        with override_settings(PAGOS_PROVEEDOR_TARJETA='inventado'):
            self.assertIsNone(proveedor_de_tarjeta())


@override_settings(MEDIA_ROOT=CARPETA)
class PanelDePagosTests(TestCase):
    """Cada vendedor concilia solo los pagos de su tienda."""

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.propia = tienda_de_prueba()
        cls.ajena = tienda_de_prueba('Fitnes RD')
        cls.vendedor = Usuario.objects.create_user('vendedor', password='clave-segura-123')
        cls.propia.usuarios.add(cls.vendedor)
        dar_acceso_al_panel([cls.vendedor])
        cls.pedido_propio = pedido_de_prueba(crear_producto(sku='L1'), 1, transferencia_realizada=True)
        cls.pedido_ajeno = pedido_de_prueba(crear_producto(sku='P1', tienda=cls.ajena), 1, transferencia_realizada=True)
        cls.pago_propio = cls.pedido_propio.pagos.get()
        cls.pago_ajeno = cls.pedido_ajeno.pagos.get()

    def setUp(self):
        self.client.force_login(self.vendedor)
        self.lista = reverse('admin:pagos_pago_changelist')

    def test_solo_ve_los_pagos_de_su_tienda(self):
        respuesta = self.client.get(self.lista)
        self.assertEqual(list(respuesta.context['cl'].queryset), [self.pago_propio])
        self.assertEqual(self.client.get(reverse('admin:pagos_pago_change', args=[self.pago_ajeno.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse('admin:pagos_pago_change', args=[self.pago_propio.pk])).status_code, 200)

    def test_aprueba_el_suyo_pero_no_el_de_otra_tienda(self):
        self.client.post(self.lista, {
            'action': 'aprobar', '_selected_action': [self.pago_propio.pk, self.pago_ajeno.pk],
        })
        self.pago_propio.refresh_from_db()
        self.pago_ajeno.refresh_from_db()
        self.pedido_propio.refresh_from_db()
        self.pedido_ajeno.refresh_from_db()
        self.assertEqual((self.pago_propio.estado, self.pago_propio.revisado_por), (Estado.APROBADO, self.vendedor))
        self.assertEqual(self.pedido_propio.estado, Pedido.Estado.PAGADO)
        self.assertEqual((self.pago_ajeno.estado, self.pedido_ajeno.estado), (Estado.EN_REVISION, Pedido.Estado.PENDIENTE))

    def test_rechaza_desde_la_lista(self):
        self.client.post(self.lista, {'action': 'rechazar', '_selected_action': [self.pago_propio.pk]})
        self.pago_propio.refresh_from_db()
        self.assertEqual(self.pago_propio.estado, Estado.RECHAZADO)

    def test_los_pagos_no_se_crean_ni_se_borran_a_mano(self):
        self.assertEqual(self.client.get(reverse('admin:pagos_pago_add')).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:pagos_pago_delete', args=[self.pago_propio.pk]), {'post': 'yes'}).status_code, 403)
        self.client.post(self.lista, {'action': 'delete_selected', '_selected_action': [self.pago_propio.pk], 'post': 'yes'})
        self.assertTrue(Pago.objects.filter(pk=self.pago_propio.pk).exists())
        self.assertNotContains(self.client.get(reverse('admin:pagos_pago_change', args=[self.pago_propio.pk])), 'deletelink')

    def test_el_pedido_enlaza_a_su_pago(self):
        pagina = self.client.get(reverse('admin:pedidos_pedido_change', args=[self.pedido_propio.pk]))
        self.assertContains(pagina, reverse('admin:pagos_pago_change', args=[self.pago_propio.pk]))
