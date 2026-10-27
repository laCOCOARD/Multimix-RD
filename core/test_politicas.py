"""Politicas al dia (2026-10-27): cada tienda cobra lo suyo, el comprobante es obligatorio, las solicitudes de tiendas
y la medicion sin datos personales; condiciones para vendedores. Lo que el dueño haya reescrito no se toca."""
import importlib

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.models import ConfiguracionTienda, PaginaInformativa
from tiendas.models import SolicitudTienda
from tiendas.tests.utiles import tienda_de_prueba

migracion = importlib.import_module('core.migrations.0023_politicas_al_dia')


class PoliticasAlDiaTests(TestCase):
    def texto(self, slug):
        return PaginaInformativa.objects.get(slug=slug).contenido

    def test_las_politicas_dicen_como_funciona_hoy_el_sitio(self):
        self.assertIn('Sin comprobante la tienda no puede confirmar tu pago.', self.texto('metodos-de-pago'))
        self.assertNotIn('Ya hice la transferencia', self.texto('metodos-de-pago'))
        privacidad = self.texto('privacidad')
        self.assertIn('Si pides abrir una tienda', privacidad)
        self.assertIn('no guardamos quién lo hizo, su dirección IP ni lo que escribió en el buscador', privacidad)
        self.assertIn('días hábiles (de lunes a sábado)', self.texto('entregas'))
        contacto = self.texto('contacto')
        self.assertIn('Nombre comercial: Multimix RD', contacto)
        self.assertIn('cobra y atiende sus pedidos', contacto)
        # Sin registro todavia: no se inventa razon social ni RNC.
        self.assertNotIn('RNC', contacto)

    def test_condiciones_para_vendedores_publicadas_y_enlazadas(self):
        condiciones = PaginaInformativa.objects.get(slug='condiciones-para-vendedores')
        self.assertTrue(condiciones.publicada)
        self.assertIn('4 días después de vencido', condiciones.contenido)
        self.assertIn('Productos ilegales, falsificados', condiciones.contenido)
        url = reverse('core:pagina', args=['condiciones-para-vendedores'])
        self.assertContains(self.client.get(url), 'El plan y los pagos al sitio')
        self.assertContains(self.client.get(reverse('tiendas:vender')), f'href="{url}"')
        self.assertContains(self.client.get(reverse('tiendas:solicitar_tienda')), f'href="{url}"')
        # En el pie, con lo legal.
        self.assertContains(self.client.get('/'), f'href="{url}"')

    def test_no_pisa_lo_que_el_dueno_escribio(self):
        PaginaInformativa.objects.filter(slug='metodos-de-pago').update(contenido='Mi texto propio.')
        PaginaInformativa.objects.filter(slug='contacto').update(contenido='Escríbenos a hola@example.com.')
        PaginaInformativa.objects.filter(slug='condiciones-para-vendedores').update(contenido='Las mías.')
        migracion.actualizar(apps, None)
        self.assertEqual(self.texto('metodos-de-pago'), 'Mi texto propio.')
        self.assertEqual(self.texto('contacto'), 'Escríbenos a hola@example.com.')
        self.assertEqual(self.texto('condiciones-para-vendedores'), 'Las mías.')
        # Y correrla dos veces no repite los agregados.
        migracion.actualizar(apps, None)
        self.assertEqual(self.texto('privacidad').count('Si pides abrir una tienda'), 1)

    def test_los_terminos_dicen_que_cada_tienda_cobra(self):
        terminos = self.client.get(reverse('core:terminos'))
        self.assertContains(terminos, 'las transferencias van a las cuentas de la tienda')
        self.assertNotContains(terminos, 'cobra por cuenta de la tienda')
        self.assertContains(terminos, 'condiciones para vendedores')


class AvisoDelResultadoTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('admin', 'dueno@example.com', 'clave-segura-123')
        config = ConfiguracionTienda.obtener()
        config.correo = 'sitio@example.com'
        config.save()
        self.solicitud = SolicitudTienda.objects.create(
            nombre_responsable='María Gómez', nombre_comercial='Dulces de María', correo='maria@example.com',
            telefono='8295551234', descripcion='Dulces criollos hechos en casa.',
        )
        self.url = reverse('admin:tiendas_solicitudtienda_change', args=[self.solicitud.pk])
        self.client.force_login(self.admin)

    def guardar(self, **datos):
        valores = {'estado': 'pendiente', 'notas': '', 'tienda': ''}
        valores.update(datos)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, valores)

    def test_aprobar_le_avisa_sin_las_notas_internas(self):
        tienda = tienda_de_prueba()
        self.guardar(estado='en_revision', notas='Llamar el lunes.')
        self.assertEqual(mail.outbox, [])
        self.guardar(estado='aprobada', notas='Confidencial: buen negocio.', tienda=tienda.pk)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['maria@example.com'])
        self.assertIn('solicitud aprobada', correo.subject)
        self.assertIn(tienda.get_absolute_url(), correo.body)
        self.assertNotIn('Confidencial', correo.body)
        # Guardar otra vez sin cambiar el estado no lo repite.
        self.guardar(estado='aprobada', notas='Otra nota.', tienda=tienda.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_rechazar_desde_la_lista_le_avisa(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin:tiendas_solicitudtienda_changelist'),
                             {'action': 'rechazar', '_selected_action': [self.solicitud.pk]})
        self.assertEqual([c.to for c in mail.outbox], [['maria@example.com']])
        self.assertIn('por ahora no podemos abrir tu tienda', mail.outbox[0].body)
        self.assertIn('sitio@example.com', mail.outbox[0].body)
