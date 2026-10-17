"""Pruebas de los arreglos de seguridad: limites de intentos que no dependen de la IP, imagenes enormes, comprobantes
privados, confirmacion del correo y scripts fuera de las plantillas (CSP)."""
import re
import shutil
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from PIL import Image

from catalogo.imagenes import convertir_a_webp
from catalogo.tests.test_modelos import crear_producto, imagen_de_prueba
from clientes import services as clientes
from core import limites
from core.validators import validar_imagen
from pagos import services as pagos
from pagos.models import Pago
from pedidos.tests.utiles import cupon_de_prueba, pedido_de_prueba
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba

Usuario = get_user_model()
CLAVE = 'clave-segura-123'
CARPETA = tempfile.mkdtemp()
DETRAS_DEL_PROXY = {'CONFIAR_IP_PROXY': True, 'CABECERA_IP': 'HTTP_X_REAL_IP'}


def tearDownModule():
    shutil.rmtree(CARPETA, ignore_errors=True)


def con_ip(numero):
    return {'HTTP_X_REAL_IP': f'203.0.113.{numero}'}


@override_settings(**DETRAS_DEL_PROXY)
class EntrarConOtraIpTests(TestCase):
    def setUp(self):
        clientes.registrar_cliente('Ana Pérez', 'ana@example.com', CLAVE)
        self.url = reverse('clientes:entrar')

    def test_cambiar_de_ip_en_cada_intento_no_salta_el_limite_de_la_cuenta(self):
        for numero in range(clientes.INTENTOS_POR_CUENTA):
            self.client.post(self.url, {'username': 'ana@example.com', 'password': 'mala'}, **con_ip(numero))
        respuesta = self.client.post(self.url, {'username': 'ana@example.com', 'password': CLAVE}, **con_ip(99))
        self.assertContains(respuesta, 'Demasiados intentos')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_x_forwarded_for_inventado_no_cambia_la_ip(self):
        for _ in range(clientes.INTENTOS_MAXIMOS):
            self.client.post(
                self.url, {'username': 'ana@example.com', 'password': 'mala'},
                HTTP_X_FORWARDED_FOR='198.51.100.1', **con_ip(1),
            )
        respuesta = self.client.post(
            self.url, {'username': 'ana@example.com', 'password': CLAVE}, HTTP_X_FORWARDED_FOR='198.51.100.2', **con_ip(1),
        )
        self.assertContains(respuesta, 'Demasiados intentos')

    def test_entrar_bien_borra_los_intentos(self):
        for numero in range(clientes.INTENTOS_POR_CUENTA - 1):
            self.client.post(self.url, {'username': 'ana@example.com', 'password': 'mala'}, **con_ip(numero))
        self.client.post(self.url, {'username': 'ana@example.com', 'password': CLAVE}, **con_ip(50))
        self.assertIn('_auth_user_id', self.client.session)
        self.assertFalse(clientes.entrada_bloqueada('203.0.113.51', 'ana@example.com'))

    def test_los_intentos_se_guardan_resumidos_y_los_viejos_se_borran(self):
        self.client.post(self.url, {'username': 'ana@example.com', 'password': 'mala'}, **con_ip(1))
        from core.models import Intento

        claves = list(Intento.objects.values_list('clave', flat=True))
        self.assertEqual(len(claves), 2)
        self.assertTrue(all(re.fullmatch(r'[0-9a-f]{64}', clave) for clave in claves))
        Intento.objects.update(creado='2020-01-01T00:00:00Z')
        self.assertEqual(limites.borrar_viejos(), 2)


@override_settings(**DETRAS_DEL_PROXY)
class EntrarAlPanelTests(TestCase):
    def setUp(self):
        Usuario.objects.create_superuser('MULTIMIX_ADMIN', 'dueno@example.com', CLAVE)
        self.url = reverse('admin:login')

    def test_el_panel_tambien_tiene_limite_de_intentos(self):
        for numero in range(clientes.INTENTOS_POR_CUENTA):
            self.client.post(self.url, {'username': 'MULTIMIX_ADMIN', 'password': 'mala'}, **con_ip(numero))
        respuesta = self.client.post(self.url, {'username': 'MULTIMIX_ADMIN', 'password': CLAVE}, **con_ip(99))
        self.assertContains(respuesta, 'Demasiados intentos')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_cuenta_junto_con_el_formulario_del_sitio(self):
        for numero in range(clientes.INTENTOS_POR_CUENTA):
            self.client.post(
                reverse('clientes:entrar'), {'username': 'multimix_admin', 'password': 'mala'}, **con_ip(numero),
            )
        respuesta = self.client.post(self.url, {'username': 'MULTIMIX_ADMIN', 'password': CLAVE}, **con_ip(99))
        self.assertContains(respuesta, 'Demasiados intentos')

    def test_entra_con_la_clave_buena(self):
        respuesta = self.client.post(self.url, {'username': 'MULTIMIX_ADMIN', 'password': CLAVE, 'next': '/panel/'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)


@override_settings(**DETRAS_DEL_PROXY)
class RecuperarYRegistrarTests(TestCase):
    def test_un_correo_no_recibe_mas_enlaces_aunque_cambie_la_ip(self):
        clientes.registrar_cliente('Ana Pérez', 'ana@example.com', CLAVE)
        for numero in range(10):
            respuesta = self.client.post(reverse('clientes:recuperar'), {'email': 'ana@example.com'}, **con_ip(numero))
            self.assertRedirects(respuesta, reverse('clientes:recuperar_enviado'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), clientes.ENLACES_POR_CORREO)

    def test_sin_ip_hay_un_tope_de_cuentas_para_todo_el_sitio(self):
        for numero in range(clientes.REGISTROS_DEL_SITIO):
            clientes.anotar_registro(None)
        self.assertTrue(clientes.registro_bloqueado(None))
        self.assertTrue(clientes.registro_bloqueado('203.0.113.7'))


class CuponesTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))
        cupon_de_prueba('BIENVENIDO10')
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        self.url = ruta('carrito:cupon_aplicar')

    def probar(self, codigo):
        return self.client.post(self.url, {'codigo': codigo}, HTTP_X_REQUESTED_WITH='fetch').json()

    def test_no_se_pueden_probar_codigos_sin_limite(self):
        for numero in range(10):
            self.assertFalse(self.probar(f'ADIVINA{numero}')['ok'])
        respuesta = self.probar('BIENVENIDO10')
        self.assertFalse(respuesta['ok'])
        self.assertIn('Probaste muchos cupones', respuesta['mensaje'])

    def test_repetir_el_mismo_codigo_equivocado_no_cuenta(self):
        for _ in range(15):
            self.assertFalse(self.probar('ERRADO')['ok'])
        self.assertTrue(self.probar('BIENVENIDO10')['ok'])

    def test_otra_sesion_de_la_misma_cuenta_sigue_bloqueada(self):
        entrar_como_cliente(self.client)
        for numero in range(10):
            self.probar(f'ADIVINA{numero}')
        self.client.cookies.clear()
        entrar_como_cliente(self.client)
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        self.assertIn('Probaste muchos cupones', self.probar('BIENVENIDO10')['mensaje'])


def png(ancho, alto, nombre='grande.png'):
    salida = BytesIO()
    Image.new('L', (ancho, alto)).save(salida, 'PNG')
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type='image/png')


class ImagenesEnormesTests(TestCase):
    @override_settings(IMAGEN_MAX_PIXELES=10_000)
    def test_rechaza_una_imagen_de_demasiados_pixeles_aunque_pese_poco(self):
        with self.assertRaisesMessage(ValidationError, 'demasiado grande'):
            validar_imagen(png(200, 100))
        validar_imagen(png(100, 100))

    @override_settings(IMAGEN_MAX_PIXELES=10_000)
    def test_convertir_tampoco_la_abre(self):
        with self.assertRaises(ValueError):
            convertir_a_webp(png(200, 100))

    @override_settings(IMAGEN_MAX_PIXELES=10_000, IMAGEN_MAX_PIXELES_JPEG=100_000)
    def test_un_jpg_admite_mas_pixeles(self):
        validar_imagen(imagen_de_prueba('foto.jpg', 'JPEG', (300, 200)))

    def test_respeta_la_orientacion_de_la_foto(self):
        salida = BytesIO()
        exif = Image.Exif()
        exif[0x0112] = 6  # tomada de lado: hay que girarla 90 grados
        Image.new('RGB', (400, 200), (10, 120, 30)).save(salida, 'JPEG', exif=exif)
        convertida = convertir_a_webp(SimpleUploadedFile('lado.jpg', salida.getvalue()))
        self.assertEqual(Image.open(BytesIO(convertida.read())).size, (200, 400))

    def test_achica_una_foto_grande(self):
        convertida = convertir_a_webp(imagen_de_prueba('foto.jpg', 'JPEG', (4000, 3000)))
        self.assertEqual(Image.open(BytesIO(convertida.read())).size, (1200, 900))


@override_settings(MEDIA_ROOT=CARPETA)
class ComprobantesPrivadosTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))
        self.pedido = pedido_de_prueba(self.producto, 1)
        self.admin = Usuario.objects.create_superuser('MULTIMIX_ADMIN', 'dueno@example.com', CLAVE)

    def subir(self):
        self.client.post(
            reverse('pedidos:avisar_transferencia', args=[self.pedido.token]), {'comprobante': imagen_de_prueba()},
        )
        return Pago.objects.get(pedido=self.pedido, estado=Pago.Estado.EN_REVISION)

    def test_el_comprobante_va_al_almacenamiento_privado(self):
        pago = self.subir()
        self.assertTrue(pago.comprobante_privado)
        self.assertTrue(storages['privado'].exists(pago.comprobante.name))
        self.assertFalse(storages['default'].exists(pago.comprobante.name))
        self.assertFalse(str(settings.PRIVADO_ROOT).startswith(str(settings.MEDIA_ROOT)))

    def test_el_panel_lo_muestra_solo_a_quien_ve_el_pago(self):
        pago = self.subir()
        url = reverse('admin:pagos_pago_comprobante', args=[pago.pk])
        self.assertEqual(self.client.get(url).status_code, 302)  # sin sesion: a la entrada del panel

        self.client.force_login(self.admin)
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'image/webp')
        self.assertIn('no-store', respuesta['Cache-Control'])
        self.assertContains(self.client.get(reverse('admin:pagos_pago_change', args=[pago.pk])), url)

        ajena = tienda_de_prueba('Fitnes Total', prefijo='FIT')
        vendedor = Usuario.objects.create_user('vendedor-ajeno', password=CLAVE)
        ajena.usuarios.add(vendedor)
        dar_acceso_al_panel([vendedor])
        self.client.force_login(vendedor)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_los_comprobantes_de_antes_pasan_al_privado(self):
        nombre = storages['default'].save('comprobantes/viejo.webp', ContentFile(b'imagen'))
        pago = pagos.pago_vigente(self.pedido)
        Pago.objects.filter(pk=pago.pk).update(comprobante=nombre, comprobante_privado=False)
        pago.refresh_from_db()
        self.assertEqual(pago.almacenamiento_del_comprobante, storages['default'])

        self.assertEqual(pagos.mover_comprobantes_al_privado(), 1)
        pago.refresh_from_db()
        self.assertTrue(pago.comprobante_privado)
        self.assertTrue(storages['privado'].exists(pago.comprobante.name))
        self.assertFalse(storages['default'].exists(nombre))
        self.assertEqual(pagos.mover_comprobantes_al_privado(), 0)

        pago.delete()
        self.assertFalse(storages['privado'].exists(pago.comprobante.name))


@override_settings(VERIFICAR_CORREO=True)
class ConfirmarCorreoTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))
        self.checkout = ruta('pedidos:checkout')

    def registrarse(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('clientes:registro'), {
                'nombre': 'Ana Pérez', 'correo': 'ana@example.com', 'telefono': '8095551234',
                'clave': CLAVE, 'clave_repetida': CLAVE, 'sitio_web': '',
            })
        return Usuario.objects.get(username='ana@example.com')

    def enlace(self):
        return re.search(r'https?://\S+/cuenta/confirmar/\S+/', mail.outbox[-1].body).group(0).split('8000', 1)[-1]

    def test_una_cuenta_nueva_confirma_su_correo_antes_de_comprar(self):
        usuario = self.registrarse()
        self.assertEqual(mail.outbox[-1].subject, 'Confirma tu correo')
        self.assertEqual(mail.outbox[-1].to, ['ana@example.com'])
        self.assertFalse(clientes.correo_confirmado(usuario))

        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        respuesta = self.client.get(self.checkout)
        self.assertRedirects(
            respuesta, f"{reverse('clientes:confirma_tu_correo')}?next={self.checkout.replace('/', '%2F')}",
            fetch_redirect_response=False,
        )
        self.assertContains(self.client.get(reverse('clientes:cuenta')), 'Confirma tu correo')

        self.assertRedirects(self.client.get(self.enlace()), reverse('clientes:cuenta'), fetch_redirect_response=False)
        self.assertTrue(clientes.correo_confirmado(usuario))
        self.assertEqual(self.client.get(self.checkout).status_code, 200)

    def test_un_enlace_alterado_no_sirve(self):
        usuario = self.registrarse()
        respuesta = self.client.get(self.enlace()[:-3] + 'xx/')
        self.assertContains(respuesta, 'Enlace vencido')
        self.assertFalse(clientes.correo_confirmado(usuario))

    def test_el_enlace_no_sirve_si_la_cuenta_cambio_de_correo(self):
        usuario = self.registrarse()
        enlace = self.enlace()
        usuario.email = 'otro@example.com'
        usuario.save()
        self.assertContains(self.client.get(enlace), 'Enlace vencido')

    def test_reenviar_tiene_limite(self):
        self.registrarse()
        url = reverse('clientes:confirma_tu_correo')
        for _ in range(clientes.ENLACES_POR_CORREO):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(url)
        self.assertEqual(len(mail.outbox), clientes.ENLACES_POR_CORREO)
        respuesta = self.client.post(url, follow=True)
        self.assertContains(respuesta, 'Ya te enviamos varios enlaces')

    def test_recuperar_la_contrasena_tambien_confirma_el_correo(self):
        usuario = self.registrarse()
        self.client.post(reverse('clientes:salir'))
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        respuesta = self.client.get(reverse('clientes:nueva_clave', args=[uid, token]))
        self.client.post(respuesta.url, {'new_password1': 'otra-clave-456', 'new_password2': 'otra-clave-456'})
        self.assertTrue(clientes.correo_confirmado(usuario))

    def test_las_cuentas_del_panel_no_lo_necesitan(self):
        vendedor = Usuario.objects.create_user('vendedor', 'v@example.com', CLAVE, is_staff=True)
        self.assertTrue(clientes.correo_confirmado(vendedor))

    @override_settings(VERIFICAR_CORREO=False)
    def test_sin_correo_configurado_no_se_pide(self):
        self.assertTrue(clientes.correo_confirmado(self.registrarse()))


class PoliticaDeContenidoTests(TestCase):
    def test_los_scripts_en_linea_no_corren(self):
        politica = self.client.get(reverse('tiendas:portada'))['Content-Security-Policy']
        script_src = next(parte for parte in politica.split(';') if parte.strip().startswith('script-src'))
        self.assertNotIn('unsafe-inline', script_src)

    def test_ninguna_plantilla_trae_scripts_en_linea(self):
        """Con la CSP sin 'unsafe-inline', un script en linea simplemente no correria: todo va en static/js/."""
        en_linea = re.compile(r'<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)[^>]*>', re.I)
        manejador = re.compile(r'<[^>]+\son[a-z]+\s*=', re.I)
        for plantilla in Path(settings.BASE_DIR, 'templates').rglob('*.html'):
            texto = plantilla.read_text(encoding='utf-8')
            self.assertIsNone(en_linea.search(texto), plantilla)
            self.assertIsNone(manejador.search(texto), plantilla)
