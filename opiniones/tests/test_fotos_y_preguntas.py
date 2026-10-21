"""Reseñas con fotos y preguntas y respuestas."""
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto, imagen_de_prueba
from clientes.services import registrar_cliente
from opiniones.models import FotoResena, Pregunta, Resena
from tiendas.tests.utiles import ruta

CLAVE = 'clave-segura-123'
COMENTARIO = 'Muy buena calidad y llegó a tiempo.'
MEDIOS = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIOS)
class FotosDeResenaTests(TestCase):
    def setUp(self):
        self.ana = registrar_cliente('Ana Pérez', 'ana@example.com', CLAVE)
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))
        self.url = ruta('catalogo:opinar', self.producto.slug)
        self.client.force_login(self.ana)

    def opinar(self, *fotos):
        return self.client.post(self.url, {'estrellas': '5', 'comentario': COMENTARIO, 'fotos': list(fotos)})

    def test_sube_fotos_que_se_ven_al_publicarla(self):
        self.opinar(imagen_de_prueba('uno.png', tamano=(300, 300)), imagen_de_prueba('dos.png', tamano=(300, 300)))
        resena = Resena.objects.get()
        fotos = list(resena.fotos.all())
        self.assertEqual(len(fotos), 2)
        self.assertTrue(all(foto.imagen.name.endswith('.webp') for foto in fotos))
        self.assertNotContains(self.client.get(self.producto.get_absolute_url()), 'mm-resena-fotos')
        Resena.objects.update(estado=Resena.Estado.APROBADA)
        self.assertContains(self.client.get(self.producto.get_absolute_url()), fotos[0].imagen.url)

    def test_fotos_nuevas_reemplazan_y_sin_fotos_se_conservan(self):
        self.opinar(imagen_de_prueba('uno.png', tamano=(300, 300)))
        self.client.post(self.url, {'estrellas': '4', 'comentario': COMENTARIO})
        self.assertEqual(FotoResena.objects.count(), 1)
        self.opinar(imagen_de_prueba('a.png', tamano=(300, 300)), imagen_de_prueba('b.png', tamano=(300, 300)))
        self.assertEqual(FotoResena.objects.count(), 2)

    def test_rechaza_mas_de_tres_o_archivos_que_no_son_imagen(self):
        self.opinar(*[imagen_de_prueba(f'{n}.png', tamano=(50, 50)) for n in range(4)])
        self.opinar(SimpleUploadedFile('virus.png', b'no es una imagen', content_type='image/png'))
        self.assertFalse(Resena.objects.exists())
        self.assertFalse(FotoResena.objects.exists())


class PreguntasTests(TestCase):
    def setUp(self):
        self.ana = registrar_cliente('Ana Pérez', 'ana@example.com', CLAVE)
        self.producto = crear_producto(nombre='Crema', precio=Decimal('900'))
        self.tienda = self.producto.tienda
        self.tienda.correo = 'ventas@tienda.example'
        self.tienda.save()
        self.url = ruta('catalogo:preguntar', self.producto.slug)

    def test_sin_cuenta_no_pregunta(self):
        self.assertContains(self.client.get(self.producto.get_absolute_url()), 'Inicia sesión para preguntar')
        self.client.post(self.url, {'pregunta': '¿Sirve para piel sensible?'})
        self.assertFalse(Pregunta.objects.exists())

    def test_la_tienda_responde_y_se_publica(self):
        self.client.force_login(self.ana)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {'pregunta': '¿Sirve para piel sensible?'})
        pregunta = Pregunta.objects.get()
        self.assertEqual((pregunta.tienda, pregunta.estado), (self.tienda, Pregunta.Estado.PENDIENTE))
        self.assertEqual(mail.outbox[-1].to, ['ventas@tienda.example'])
        ficha = self.client.get(self.producto.get_absolute_url())
        self.assertContains(ficha, 'espera la respuesta de la tienda')
        self.client.logout()
        self.assertNotContains(self.client.get(self.producto.get_absolute_url()), 'piel sensible')

        admin = get_user_model().objects.create_superuser('admin', 'admin@example.com', CLAVE)
        self.client.force_login(admin)
        url = reverse('admin:opiniones_pregunta_change', args=[pregunta.pk])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {'respuesta': 'Sí, es hipoalergénica.'})
        pregunta.refresh_from_db()
        self.assertEqual((pregunta.estado, pregunta.respondida_por), (Pregunta.Estado.PUBLICADA, admin))
        self.assertEqual(mail.outbox[-1].to, ['ana@example.com'])
        self.assertIn('hipoalergénica', mail.outbox[-1].body)
        self.client.logout()
        ficha = self.client.get(self.producto.get_absolute_url())
        self.assertContains(ficha, 'piel sensible')
        self.assertContains(ficha, 'hipoalergénica')

    def test_preguntas_muy_cortas_y_limite_por_hora(self):
        self.client.force_login(self.ana)
        self.client.post(self.url, {'pregunta': '¿?'})
        self.assertFalse(Pregunta.objects.exists())
        for numero in range(7):
            self.client.post(self.url, {'pregunta': f'¿Pregunta número {numero}?'})
        self.assertEqual(Pregunta.objects.count(), 5)
