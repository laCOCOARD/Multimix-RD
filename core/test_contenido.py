from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.tests.test_modelos import crear_producto
from core.models import PaginaInformativa, PreguntaFrecuente
from tiendas.models import Banner
from tiendas.services import banners_de, dar_acceso_al_panel
from tiendas.tests.utiles import ruta, tienda_de_prueba

CLAVE = 'clave-segura-123'


class PaginasInformativasTests(TestCase):
    def test_las_politicas_nacen_escritas_y_publicadas(self):
        slugs = set(PaginaInformativa.objects.values_list('slug', flat=True))
        self.assertTrue({'privacidad', 'entregas', 'cambios-y-devoluciones', 'reembolsos', 'garantias'} <= slugs)
        self.assertFalse(PaginaInformativa.objects.filter(publicada=False).exists())
        self.assertFalse(PaginaInformativa.objects.filter(contenido='').exists())
        # Los plazos salen de la configuracion por defecto.
        self.assertIn('dentro de los 7 días', PaginaInformativa.objects.get(slug='cambios-y-devoluciones').contenido)
        self.assertIn('48 horas', PaginaInformativa.objects.get(slug='metodos-de-pago').contenido)

    def test_sin_publicar_solo_la_ve_el_administrador(self):
        PaginaInformativa.objects.filter(slug='privacidad').update(publicada=False)
        url = reverse('core:pagina', args=['privacidad'])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse('tiendas:portada')), 'Política de privacidad')
        Usuario = get_user_model()
        self.client.force_login(Usuario.objects.create_user('vendedor', is_staff=True))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(Usuario.objects.create_superuser('admin', 'a@example.com', CLAVE))
        self.assertContains(self.client.get(url), 'Vista previa')

    def test_publicada_sale_en_el_pie_y_el_texto_no_es_html(self):
        pagina = PaginaInformativa.objects.get(slug='privacidad')
        pagina.contenido = 'Cuidamos tus datos.\n\n<script>alert(1)</script>'
        pagina.publicada = True
        pagina.save()
        self.assertContains(self.client.get(reverse('tiendas:portada')), '/pagina/privacidad/')
        respuesta = self.client.get(pagina.get_absolute_url())
        self.assertContains(respuesta, '<p>Cuidamos tus datos.</p>')
        self.assertNotContains(respuesta, '<script>alert(1)</script>')
        self.assertContains(self.client.get(reverse('sitemap')), '/pagina/privacidad/')

    def test_solo_el_administrador_las_edita(self):
        Usuario = get_user_model()
        vendedor = Usuario.objects.create_user('vendedor', password=CLAVE)
        tienda_de_prueba().usuarios.add(vendedor)
        dar_acceso_al_panel([vendedor])
        self.client.force_login(vendedor)
        for nombre in ('admin:core_paginainformativa_changelist', 'admin:core_preguntafrecuente_changelist'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)


class PreguntasFrecuentesTests(TestCase):
    def test_sin_preguntas_no_hay_pagina_ni_enlace(self):
        self.assertEqual(self.client.get(reverse('core:preguntas')).status_code, 404)
        self.assertNotContains(self.client.get(reverse('tiendas:portada')), 'Preguntas frecuentes')

    def test_solo_se_ven_las_activas(self):
        PreguntaFrecuente.objects.create(pregunta='¿Hacen envíos?', respuesta='Sí, a las zonas de cada tienda.')
        PreguntaFrecuente.objects.create(pregunta='¿Pregunta oculta?', respuesta='No se ve.', activa=False)
        for url in (reverse('core:preguntas'), reverse('tiendas:portada')):
            pagina = self.client.get(url)
            self.assertContains(pagina, '¿Hacen envíos?')
            self.assertNotContains(pagina, '¿Pregunta oculta?')


class BannerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.propia = tienda_de_prueba()
        cls.ajena = tienda_de_prueba('Fitnes RD')
        crear_producto()
        cls.vendedor = get_user_model().objects.create_user('vendedor', password=CLAVE)
        cls.propia.usuarios.add(cls.vendedor)
        dar_acceso_al_panel([cls.vendedor])

    def test_sin_banners_se_ve_el_banner_fijo_de_la_tienda(self):
        pagina = self.client.get(ruta('catalogo:inicio'))
        self.assertNotContains(pagina, 'id="banners"')
        self.assertContains(pagina, 'Tu tienda de bienestar')

    def test_solo_rotan_los_activos_vigentes_y_de_la_tienda(self):
        ahora = timezone.now()
        Banner.objects.create(tienda=self.propia, titulo='Semana de ofertas', texto_boton='Ver ofertas',
                              enlace='/tienda/multimix-rd/catalogo/?oferta=on')
        Banner.objects.create(tienda=self.propia, titulo='Apagado', activo=False)
        Banner.objects.create(tienda=self.propia, titulo='Ya terminó', vigente_hasta=ahora - timedelta(days=1))
        Banner.objects.create(tienda=self.propia, titulo='Aún no empieza', vigente_desde=ahora + timedelta(days=1))
        Banner.objects.create(tienda=self.ajena, titulo='De otra tienda')
        self.assertEqual([b.titulo for b in banners_de(self.propia)], ['Semana de ofertas'])
        pagina = self.client.get(ruta('catalogo:inicio'))
        self.assertContains(pagina, 'Semana de ofertas')
        self.assertContains(pagina, 'href="/tienda/multimix-rd/catalogo/?oferta=on"')
        for oculto in ('Apagado', 'Ya terminó', 'Aún no empieza', 'De otra tienda'):
            self.assertNotContains(pagina, oculto)

    def test_el_enlace_no_acepta_direcciones_peligrosas(self):
        for enlace in ('javascript:alert(1)', 'http://sin-candado.example', '//otro-sitio.example'):
            with self.assertRaises(ValidationError):
                Banner(tienda=self.propia, titulo='X', enlace=enlace).full_clean()
        Banner(tienda=self.propia, titulo='X', enlace='https://seguro.example/promo').full_clean()

    def test_cada_vendedor_administra_solo_sus_banners(self):
        propio = Banner.objects.create(tienda=self.propia, titulo='Mío')
        ajeno = Banner.objects.create(tienda=self.ajena, titulo='Ajeno')
        self.client.force_login(self.vendedor)
        lista = self.client.get(reverse('admin:tiendas_banner_changelist'))
        self.assertEqual(list(lista.context['cl'].queryset), [propio])
        self.assertEqual(self.client.get(reverse('admin:tiendas_banner_change', args=[ajeno.pk])).status_code, 302)
        self.client.post(reverse('admin:tiendas_banner_add'), {
            'tienda': self.ajena.pk, 'titulo': 'Colado', 'subtitulo': '', 'texto_boton': '', 'enlace': '', 'activo': 'on', 'orden': 0,
        })
        self.assertFalse(Banner.objects.filter(tienda=self.ajena, titulo='Colado').exists())
        self.client.post(reverse('admin:tiendas_banner_add'), {
            'tienda': self.propia.pk, 'titulo': 'Nuevo', 'subtitulo': '', 'texto_boton': '', 'enlace': '', 'activo': 'on', 'orden': 0,
        })
        self.assertTrue(Banner.objects.filter(tienda=self.propia, titulo='Nuevo').exists())
