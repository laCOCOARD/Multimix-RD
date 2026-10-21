"""Avisame cuando este disponible."""
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from catalogo.avisos import avisar_disponibles
from catalogo.models import AvisoDisponible, Disponibilidad
from tiendas.tests.utiles import entrar_como_cliente

from .test_modelos import crear_producto


class AvisameTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(
            nombre='Proteína', precio=Decimal('1500'), controla_stock=False, disponibilidad=Disponibilidad.AGOTADO,
        )
        self.url = reverse('catalogo:avisame', args=[self.producto.tienda.slug, self.producto.slug])

    def test_la_ficha_ofrece_el_aviso_solo_si_no_se_puede_comprar(self):
        self.assertContains(self.client.get(self.producto.get_absolute_url()), 'Avísame cuando esté disponible')
        self.producto.disponibilidad = Disponibilidad.DISPONIBLE
        self.producto.save()
        self.assertNotContains(self.client.get(self.producto.get_absolute_url()), 'Avísame cuando esté disponible')

    def test_sin_cuenta_deja_su_correo_y_se_le_avisa_una_vez_al_volver(self):
        respuesta = self.client.post(self.url, {'correo': 'Ana@Example.com'})
        self.assertRedirects(respuesta, self.producto.get_absolute_url(), fetch_redirect_response=False)
        aviso = AvisoDisponible.objects.get()
        self.assertEqual((aviso.correo, aviso.tienda, aviso.avisado), ('ana@example.com', self.producto.tienda, None))
        self.assertContains(self.client.get(self.producto.get_absolute_url()), 'Te avisaremos por correo')

        with self.captureOnCommitCallbacks(execute=True):
            self.producto.disponibilidad = Disponibilidad.DISPONIBLE
            self.producto.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@example.com'])
        self.assertIn('Proteína', mail.outbox[0].subject)
        self.assertIn(self.producto.get_absolute_url(), mail.outbox[0].body)
        aviso.refresh_from_db()
        self.assertIsNotNone(aviso.avisado)

        # Guardarlo otra vez no repite el correo.
        with self.captureOnCommitCallbacks(execute=True):
            self.producto.save()
        self.assertEqual(len(mail.outbox), 1)

    def test_con_cuenta_va_al_correo_de_la_cuenta(self):
        usuario = entrar_como_cliente(self.client)
        self.client.post(self.url, {'correo': 'otro@example.com'})
        self.assertEqual(AvisoDisponible.objects.get().correo, usuario.email)
        self.assertEqual(AvisoDisponible.objects.get().usuario, usuario)

    def test_un_producto_a_la_venta_no_admite_aviso(self):
        self.producto.disponibilidad = Disponibilidad.DISPONIBLE
        self.producto.save()
        self.client.post(self.url, {'correo': 'ana@example.com'})
        self.assertFalse(AvisoDisponible.objects.exists())

    def test_correo_invalido_y_bots(self):
        self.client.post(self.url, {'correo': 'no-es-correo'})
        self.client.post(self.url, {'correo': 'bot@example.com', 'sitio_web': 'spam'})
        self.assertFalse(AvisoDisponible.objects.exists())

    def test_limite_de_avisos_por_persona(self):
        for numero in range(12):
            self.client.post(self.url, {'correo': f'persona{numero}@example.com'})
        self.assertEqual(AvisoDisponible.objects.count(), 10)

    def test_los_cambios_en_masa_avisan_con_la_tarea_periodica(self):
        self.client.post(self.url, {'correo': 'ana@example.com'})
        type(self.producto).objects.filter(pk=self.producto.pk).update(disponibilidad=Disponibilidad.DISPONIBLE)
        self.assertEqual(avisar_disponibles(), 1)
        self.assertEqual(avisar_disponibles(), 0)
