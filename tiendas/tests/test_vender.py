"""Vender en el sitio (Fase 2 del rediseño): la pagina para emprendedores, la solicitud de tienda y su revision.

La solicitud no crea cuentas ni da acceso al panel: queda pendiente y solo el administrador principal la ve.
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalogo.models import Categoria
from core.models import ConfiguracionTienda
from tiendas.models import SolicitudTienda, Tienda
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

CLAVE = 'clave-segura-123'


def datos(**cambios):
    valores = {
        'nombre_responsable': '  María   Gómez ', 'nombre_comercial': 'Dulces de María', 'correo': 'Maria@Example.com',
        'telefono': '(829) 555-1234', 'categoria': '', 'descripcion': 'Dulces criollos hechos en casa: habichuelas '
        'con dulce, majarete y dulce de leche.', 'redes': '@dulcesdemaria', 'acepta': 'on', 'sitio_web': '',
    }
    valores.update(cambios)
    return valores


class PaginaParaVenderTests(TestCase):
    def test_la_pagina_explica_y_lleva_al_formulario(self):
        pagina = self.client.get(reverse('tiendas:vender'))
        self.assertContains(pagina, 'Tu marca merece su propia <span>tienda online.</span>', html=False)
        self.assertContains(pagina, f'href="{reverse("tiendas:solicitar_tienda")}"')
        self.assertContains(pagina, 'href="#como-funciona"')
        self.assertContains(pagina, 'id="como-funciona"')
        self.assertContains(pagina, '¿Qué información debo preparar?')
        # No promete lo que no existe: precio, aprobacion automatica ni plazos.
        for promesa in ('gratis', 'Gratis', 'sin costo', 'automátic', 'horas', 'comisión'):
            self.assertNotContains(pagina, promesa)

    def test_los_accesos_del_sitio_llevan_a_la_pagina(self):
        tienda_de_prueba()
        portada = self.client.get('/')
        self.assertContains(portada, f'href="{reverse("tiendas:vender")}"')
        self.assertContains(portada, f'href="{reverse("tiendas:solicitar_tienda")}"')
        # Dentro de una tienda la barra es de la tienda: no ofrece vender en el sitio.
        tienda = self.client.get(tienda_de_prueba().get_absolute_url())
        self.assertNotContains(tienda, 'mm-nav-vender')

    def test_aparece_en_el_sitemap(self):
        self.assertContains(self.client.get(reverse('sitemap')), reverse('tiendas:vender'))

    @override_settings(CUENTA_OBLIGATORIA=True)
    def test_se_pide_la_tienda_sin_tener_cuenta(self):
        for nombre in ('tiendas:vender', 'tiendas:solicitar_tienda', 'tiendas:solicitud_enviada'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)


class SolicitudTests(TestCase):
    def setUp(self):
        self.url = reverse('tiendas:solicitar_tienda')
        config = ConfiguracionTienda.obtener()
        config.correo = 'sitio@example.com'
        config.save()
        self.belleza = Categoria.objects.create(nombre='Belleza')

    def enviar(self, **cambios):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, datos(**cambios))

    def test_el_formulario_valida_tambien_en_el_navegador(self):
        formulario = self.client.get(self.url)
        self.assertContains(formulario, 'csrfmiddlewaretoken')
        self.assertContains(formulario, 'name="nombre_comercial"')
        self.assertContains(formulario, 'required', count=None)
        self.assertContains(formulario, 'pattern="[\\d\\s\\(\\)\\+\\.\\-]{10,16}"', html=False)
        self.assertContains(formulario, 'minlength="20"')
        self.assertContains(formulario, 'type="email"')
        # Solo las categorias principales y activas.
        Categoria.objects.create(nombre='Labiales', padre=self.belleza)
        self.assertEqual(list(self.client.get(self.url).context['formulario'].fields['categoria'].queryset), [self.belleza])

    def test_una_solicitud_valida_queda_pendiente_y_avisa(self):
        usuarios, tiendas = get_user_model().objects.count(), Tienda.objects.count()
        respuesta = self.enviar(categoria=self.belleza.pk)
        self.assertRedirects(respuesta, reverse('tiendas:solicitud_enviada'))
        solicitud = SolicitudTienda.objects.get()
        self.assertEqual(
            (solicitud.estado, solicitud.nombre_responsable, solicitud.correo, solicitud.telefono, solicitud.categoria),
            (SolicitudTienda.Estado.PENDIENTE, 'María Gómez', 'maria@example.com', '8295551234', self.belleza),
        )
        # No crea cuentas ni tiendas: eso lo decide el administrador.
        self.assertEqual((get_user_model().objects.count(), Tienda.objects.count()), (usuarios, tiendas))
        destinos = {tuple(correo.to): correo for correo in mail.outbox}
        self.assertIn('Dulces de María', destinos[('sitio@example.com',)].subject)
        self.assertIn(reverse('admin:tiendas_solicitudtienda_change', args=[solicitud.pk]), destinos[('sitio@example.com',)].body)
        self.assertIn('Recibimos tu solicitud', destinos[('maria@example.com',)].subject)
        # La confirmacion no muestra los datos de la persona.
        enviada = self.client.get(reverse('tiendas:solicitud_enviada'))
        self.assertContains(enviada, 'Recibimos tu solicitud')
        self.assertNotContains(enviada, 'maria@example.com')

    def test_datos_que_no_sirven(self):
        casos = {
            'telefono': '555-1234',
            'descripcion': 'Dulces.',
            'acepta': '',
            'correo': 'no-es-un-correo',
            'nombre_comercial': '',
        }
        for campo, valor in casos.items():
            respuesta = self.enviar(**{campo: valor})
            self.assertEqual(respuesta.status_code, 200, campo)
            self.assertTrue(respuesta.context['formulario'].has_error(campo), campo)
            self.assertContains(respuesta, 'id="errores-solicitud"')
            self.assertContains(respuesta, f'id="id_{campo}_error"')
        self.assertFalse(SolicitudTienda.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_los_bots_no_pasan(self):
        respuesta = self.enviar(sitio_web='http://spam.example.com')
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(SolicitudTienda.objects.exists())

    def test_limite_por_correo(self):
        self.enviar()
        self.enviar(nombre_comercial='Otra cosa')
        respuesta = self.enviar(nombre_comercial='Una tercera')
        self.assertContains(respuesta, 'Ya recibimos varias solicitudes')
        self.assertEqual(SolicitudTienda.objects.count(), 2)

    def test_exige_el_token_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        self.assertEqual(cliente.post(self.url, datos()).status_code, 403)
        self.assertFalse(SolicitudTienda.objects.exists())

    def test_con_sesion_llega_con_su_nombre_y_correo(self):
        usuario = get_user_model().objects.create_user('ana@example.com', 'ana@example.com', CLAVE, first_name='Ana',
                                                       last_name='Pérez')
        self.client.force_login(usuario)
        formulario = self.client.get(self.url).context['formulario']
        self.assertEqual(formulario.initial, {'nombre_responsable': 'Ana Pérez', 'correo': 'ana@example.com'})


class RevisionEnElPanelTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_superuser('admin', 'dueno@example.com', CLAVE)
        self.vendedor = Usuario.objects.create_user('vendedor', 'vendedor@example.com', CLAVE)
        tienda_de_prueba().usuarios.add(self.vendedor)
        dar_acceso_al_panel([self.vendedor])
        self.solicitud = SolicitudTienda.objects.create(
            nombre_responsable='María Gómez', nombre_comercial='Dulces de María', correo='maria@example.com',
            telefono='8295551234', descripcion='Dulces criollos hechos en casa.',
        )
        self.lista = reverse('admin:tiendas_solicitudtienda_changelist')
        self.detalle = reverse('admin:tiendas_solicitudtienda_change', args=[self.solicitud.pk])

    def test_solo_el_administrador_principal_las_ve(self):
        self.client.force_login(self.vendedor)
        self.assertEqual(self.client.get(self.lista).status_code, 403)
        self.assertEqual(self.client.get(self.detalle).status_code, 403)
        self.assertNotContains(self.client.get(reverse('admin:index')), 'Solicitudes de tiendas')
        # Tampoco en el sitio: los datos no se publican.
        self.assertNotContains(self.client.get('/'), 'maria@example.com')
        self.assertNotContains(self.client.get(reverse('tiendas:vender')), 'Dulces de María')

    def test_el_administrador_la_revisa_y_crea_la_tienda_con_sus_datos(self):
        self.client.force_login(self.admin)
        inicio = self.client.get(reverse('admin:index'))
        self.assertContains(inicio, '1 solicitud de tienda pendiente')
        self.assertContains(self.client.get(self.lista), 'Dulces de María')
        detalle = self.client.get(self.detalle)
        self.assertContains(detalle, 'https://wa.me/18295551234')
        self.assertContains(detalle, f'{reverse("admin:tiendas_tienda_add")}?nombre=Dulces+de+Mar%C3%ADa')
        # El formulario de la tienda nueva llega con esos datos.
        nueva = self.client.get(f'{reverse("admin:tiendas_tienda_add")}?nombre=Dulces+de+Mar%C3%ADa&correo=maria%40example.com')
        self.assertContains(nueva, 'value="Dulces de María"')

        respuesta = self.client.post(self.detalle, {'estado': 'en_revision', 'notas': 'Llamar el lunes.', 'tienda': ''})
        self.assertEqual(respuesta.status_code, 302)
        self.solicitud.refresh_from_db()
        self.assertEqual((self.solicitud.estado, self.solicitud.revisada_por), ('en_revision', self.admin))
        self.assertIsNotNone(self.solicitud.revisada_el)

    def test_rechazar_desde_la_lista_y_no_se_agregan_a_mano(self):
        self.client.force_login(self.admin)
        self.client.post(self.lista, {'action': 'rechazar', '_selected_action': [self.solicitud.pk]})
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'rechazada')
        self.assertEqual(self.client.get(reverse('admin:tiendas_solicitudtienda_add')).status_code, 403)
