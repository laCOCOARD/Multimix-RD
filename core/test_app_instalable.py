"""App instalable (PWA): manifiesto, service worker y pagina sin conexion."""
from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse


class AppInstalableTests(TestCase):
    def test_el_manifiesto_describe_la_app(self):
        respuesta = self.client.get('/manifest.webmanifest')
        self.assertEqual(respuesta['Content-Type'], 'application/manifest+json')
        datos = respuesta.json()
        self.assertEqual((datos['display'], datos['scope'], datos['lang']), ('standalone', '/', 'es-DO'))
        self.assertEqual(datos['name'], 'Multimix RD')
        tamanos = {(icono['sizes'], icono['purpose']) for icono in datos['icons']}
        self.assertTrue({('192x192', 'any'), ('512x512', 'any'), ('512x512', 'maskable')} <= tamanos)
        for icono in datos['icons']:
            self.assertTrue(finders.find(icono['src'].split('/static/', 1)[-1]), icono['src'])

    def test_el_service_worker_se_sirve_desde_la_raiz_y_no_guarda_paginas(self):
        respuesta = self.client.get('/sw.js')
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta['Content-Type'].startswith('application/javascript'))
        self.assertEqual(respuesta['Cache-Control'], 'no-cache')
        codigo = respuesta.content.decode()
        self.assertIn(reverse('core:sin_conexion'), codigo)
        self.assertIn("if (peticion.method !== 'GET') return;", codigo)
        self.assertNotIn('{%', codigo)

    def test_pagina_sin_conexion_sin_cdn(self):
        respuesta = self.client.get(reverse('core:sin_conexion'))
        self.assertContains(respuesta, 'Estás sin conexión')
        self.assertNotContains(respuesta, 'cdn.jsdelivr.net')

    def test_todas_las_paginas_enlazan_el_manifiesto(self):
        self.assertContains(self.client.get(reverse('tiendas:portada')), 'rel="manifest" href="/manifest.webmanifest"')

    @override_settings(CUENTA_OBLIGATORIA=True)
    def test_abre_sin_sesion_aunque_el_sitio_pida_cuenta(self):
        for url in ('/manifest.webmanifest', '/sw.js', reverse('core:sin_conexion')):
            self.assertEqual(self.client.get(url).status_code, 200, url)
