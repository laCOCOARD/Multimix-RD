"""Videos de las tiendas (plan Premium): lectura del MP4, limites del plan, aprobacion, portada, vistas y panel."""
import struct
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto
from core.models import ConfiguracionTienda
from core.videos import DANADO, NO_ES_MP4, VideoInvalido, leer_video, validar_video
from planes import services
from planes.models import Plan, Video
from tiendas.models import Tienda
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

CLAVE = 'clave-segura-123'


def caja(tipo, contenido=b''):
    return struct.pack('>I4s', 8 + len(contenido), tipo.encode('latin-1')) + contenido


def _pista(numero, manejador, formato, escala, duracion):
    tkhd = caja('tkhd', struct.pack('>IIII', 0, 0, 0, numero) + bytes(68))
    mdhd = caja('mdhd', struct.pack('>IIIII', 0, 0, 0, escala, duracion) + bytes(4))
    hdlr = caja('hdlr', struct.pack('>II4s', 0, 0, manejador.encode()) + bytes(13))
    stsd = caja('stsd', struct.pack('>II', 0, 1) + caja(formato, bytes(70)))
    return caja('trak', tkhd + caja('mdia', mdhd + hdlr + caja('minf', caja('stbl', stsd))))


def mp4(segundos=10, imagen='avc1', sonido='mp4a', relleno=2000, duracion_general=True, moov_al_final=False):
    """Un MP4 minimo: solo las cajas que lee core.videos y un `mdat` de relleno en lugar de la imagen."""
    escala = 1000
    duracion = round(segundos * escala)
    mvhd = caja('mvhd', struct.pack('>IIIII', 0, 0, 0, escala, duracion if duracion_general else 0) + bytes(80))
    pistas = _pista(1, 'vide', imagen, escala, duracion)
    if sonido:
        pistas += _pista(2, 'soun', sonido, 44100, round(segundos * 44100))
    moov = caja('moov', mvhd + pistas)
    ftyp = caja('ftyp', b'isom' + bytes(4) + b'isomavc1mp41')
    mdat = caja('mdat', bytes(relleno))
    return ftyp + (mdat + moov if moov_al_final else moov + mdat)


def subido(datos=None, nombre='clip.mp4'):
    return SimpleUploadedFile(nombre, mp4() if datos is None else datos, content_type='video/mp4')


class LeerVideoTests(TestCase):
    def leer(self, datos):
        return leer_video(SimpleUploadedFile('clip.mp4', datos))

    def test_lee_duracion_y_formatos(self):
        info = self.leer(mp4(12.4))
        self.assertEqual((info.duracion, info.imagen, info.sonido), (12.4, 'avc1', 'mp4a'))
        self.assertIsNone(self.leer(mp4(5, sonido=None)).sonido)

    def test_moov_al_final_y_duracion_de_la_pista(self):
        # Muchos telefonos escriben el `moov` despues del video; y si la cabecera no dice la duracion, la da la pista.
        self.assertEqual(self.leer(mp4(8, moov_al_final=True)).duracion, 8)
        self.assertEqual(self.leer(mp4(9, duracion_general=False)).duracion, 9)

    def test_lo_que_no_es_un_mp4_o_esta_cortado(self):
        with self.assertRaisesMessage(VideoInvalido, NO_ES_MP4):
            self.leer(b'\x89PNG\r\n\x1a\n' + bytes(100))
        with self.assertRaisesMessage(VideoInvalido, DANADO):
            self.leer(mp4()[:200])
        with self.assertRaisesMessage(VideoInvalido, 'no trae imagen'):
            self.leer(caja('ftyp', b'isom' + bytes(4)) + caja('moov', caja('mvhd', bytes(100))))


class ValidarVideoTests(TestCase):
    def validar(self, datos=None, nombre='clip.mp4'):
        validar_video(subido(datos, nombre))

    def test_acepta_un_mp4_h264_dentro_de_los_limites(self):
        self.validar()
        self.validar(mp4(15.3))  # unas decimas de mas se toleran
        self.validar(mp4(10), nombre='clip.MOV')

    def test_rechaza_lo_que_no_reproducen_todos_los_telefonos(self):
        with self.assertRaisesMessage(ValidationError, 'HEVC'):
            self.validar(mp4(imagen='hvc1'))
        with self.assertRaisesMessage(ValidationError, 'sonido del video'):
            self.validar(mp4(sonido='Opus'))
        with self.assertRaisesMessage(ValidationError, NO_ES_MP4):
            self.validar(nombre='clip.webm')

    def test_duracion_y_peso_de_la_configuracion(self):
        with self.assertRaisesMessage(ValidationError, 'dura 20 segundos y el máximo es 15'):
            self.validar(mp4(20))
        with self.assertRaisesMessage(ValidationError, 'demasiado corto'):
            self.validar(mp4(0.5))
        config = ConfiguracionTienda.obtener()
        config.video_segundos_maximos = 30
        config.video_megas_maximos = 1
        config.save()
        self.validar(mp4(20))
        with self.assertRaisesMessage(ValidationError, 'el máximo es 1 MB'):
            self.validar(mp4(relleno=1024 * 1024))


class ConVideos(TestCase):
    def setUp(self):
        # En Windows un archivo abierto no se deja borrar: la carpeta temporal se limpia como se pueda.
        self.media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.media.cleanup)
        ajuste = self.settings(MEDIA_ROOT=self.media.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_superuser('admin', 'dueno@example.com', CLAVE)
        self.premium = Plan.objects.get(nombre='Premium')
        self.tienda = tienda_de_prueba(correo='tienda@example.com')
        self.ajena = tienda_de_prueba('Fitnes RD')
        self.vendedor = Usuario.objects.create_user('vendedor', 'vendedor@example.com', CLAVE)
        self.tienda.usuarios.add(self.vendedor)
        dar_acceso_al_panel([self.vendedor])
        self.crema = crear_producto(nombre='Crema', sku='C1', precio=Decimal('800'))
        self.pesas = crear_producto(nombre='Pesas', sku='P1', precio=Decimal('900'), tienda=self.ajena)
        config = ConfiguracionTienda.obtener()
        config.correo = 'sitio@example.com'
        config.save()

    def con_plan(self, tienda, plan=None):
        Tienda.objects.filter(pk=tienda.pk).update(plan=plan or self.premium)
        tienda.refresh_from_db()
        return tienda

    def video(self, tienda=None, **datos):
        valores = {'tienda': tienda or self.tienda, 'titulo': 'Nueva crema', 'archivo': subido(), 'aprobado': True}
        valores.update(datos)
        return Video.objects.create(**valores)

    def archivo_existe(self, nombre):
        return (Path(self.media.name) / nombre).exists()


class LimitesDelPlanTests(ConVideos):
    def test_el_premium_trae_un_video(self):
        self.assertEqual(self.premium.videos_portada, 1)
        self.assertEqual(Plan.objects.get(nombre='Estándar').videos_portada, 0)

    def test_sin_plan_no_hay_videos_y_el_plan_pone_el_limite(self):
        borrador = Video(tienda=self.tienda, titulo='Nuevo', archivo=subido())
        with self.assertRaisesMessage(ValidationError, 'no incluye videos'):
            borrador.full_clean()
        self.con_plan(self.tienda)
        borrador.full_clean()
        borrador.save()
        # Cuenta tambien los apagados: cada video ocupa almacenamiento.
        Video.objects.filter(pk=borrador.pk).update(activo=False)
        segundo = Video(tienda=self.tienda, titulo='Otro', archivo=subido())
        with self.assertRaisesMessage(ValidationError, 'Tu plan permite 1 video.'):
            segundo.full_clean()
        self.assertEqual(services.cupos_de_video(self.tienda), 0)

    def test_el_producto_es_de_la_misma_tienda(self):
        self.con_plan(self.tienda)
        video = Video(tienda=self.tienda, titulo='Ajeno', archivo=subido(), producto=self.pesas)
        with self.assertRaisesMessage(ValidationError, 'Elige un producto de tu tienda'):
            video.full_clean()

    def test_mide_el_video_y_borra_el_archivo_que_reemplaza(self):
        video = self.video(archivo=subido(mp4(12.5)))
        self.assertEqual(video.duracion, Decimal('12.5'))
        self.assertEqual(video.peso, len(mp4(12.5)))
        self.assertTrue(video.archivo.name.startswith('videos/') and video.archivo.name.endswith('.mp4'))
        anterior = video.archivo.name
        with self.captureOnCommitCallbacks(execute=True):
            video.archivo = subido(mp4(7), nombre='otro.mov')
            video.save()
        self.assertEqual(video.duracion, Decimal('7.0'))
        self.assertFalse(self.archivo_existe(anterior))
        actual = video.archivo.name
        with self.captureOnCommitCallbacks(execute=True):
            video.delete()
        self.assertFalse(self.archivo_existe(actual))


class SitioTests(ConVideos):
    def test_la_portada_muestra_los_videos_aprobados_como_anuncios(self):
        self.con_plan(self.tienda)
        video = self.video(producto=self.crema)
        portada = self.client.get('/')
        self.assertEqual(portada.context['historias'], [{'tienda': self.tienda, 'videos': [video]}])
        self.assertContains(portada, 'Videos de las tiendas')
        self.assertContains(portada, 'data-etiqueta="Anuncio"')
        self.assertContains(portada, f'data-producto="{self.crema.get_absolute_url()}"')
        self.assertContains(portada, 'js/historias')
        self.assertIn("media-src 'self' blob: https:", portada['Content-Security-Policy'])

    def test_solo_aprobados_activos_de_tiendas_activas_con_plan(self):
        self.con_plan(self.tienda)
        self.video(aprobado=False)
        self.video(tienda=self.ajena, titulo='Sin plan')
        self.assertEqual(services.historias_para_la_portada(), [])
        portada = self.client.get('/')
        self.assertNotContains(portada, 'Videos de las tiendas')
        self.assertNotContains(portada, 'js/historias')

        aprobado = Video.objects.get(tienda=self.tienda)
        Video.objects.filter(pk=aprobado.pk).update(aprobado=True)
        self.assertEqual(len(services.historias_para_la_portada()), 1)
        Video.objects.filter(pk=aprobado.pk).update(activo=False)
        self.assertEqual(services.historias_para_la_portada(), [])
        Video.objects.filter(pk=aprobado.pk).update(activo=True)
        Tienda.objects.filter(pk=self.tienda.pk).update(activa=False)
        self.assertEqual(services.historias_para_la_portada(), [])

    def test_si_le_bajan_el_plan_no_pasa_del_limite(self):
        self.con_plan(self.tienda)
        primero = self.video(titulo='Primero', orden=1)
        Video.objects.create(tienda=self.tienda, titulo='Segundo', archivo=subido(), aprobado=True, orden=2)
        self.assertEqual(services.historias_de_la_tienda(self.tienda)[0]['videos'], [primero])

    def test_la_pagina_de_la_tienda_ofrece_su_video(self):
        self.con_plan(self.tienda)
        self.video()
        pagina = self.client.get(self.tienda.get_absolute_url())
        self.assertContains(pagina, 'Ver nuestro video')
        self.assertContains(pagina, 'js/historias')
        ajena = self.client.get(self.ajena.get_absolute_url())
        self.assertNotContains(ajena, 'Ver nuestro video')

    def test_cuenta_una_vista_por_persona_y_solo_de_videos_visibles(self):
        self.con_plan(self.tienda)
        video = self.video()
        oculto = self.video(tienda=self.con_plan(self.ajena), aprobado=False)
        url = reverse('planes:vista_de_video', args=[video.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 204)
        self.client.post(url)
        self.client.post(reverse('planes:vista_de_video', args=[oculto.pk]))
        video.refresh_from_db()
        oculto.refresh_from_db()
        self.assertEqual((video.vistas, oculto.vistas), (1, 0))
        # Otra persona (otra sesion) si suma.
        self.client.logout()
        self.client.post(url)
        video.refresh_from_db()
        self.assertEqual(video.vistas, 2)


class PanelDeVideosTests(ConVideos):
    def setUp(self):
        super().setUp()
        self.con_plan(self.tienda)
        self.client.force_login(self.vendedor)

    def datos(self, **cambios):
        datos = {'tienda': self.tienda.pk, 'titulo': 'Mi video', 'archivo': subido(), 'producto': '',
                 'activo': 'on', 'orden': '0'}
        datos.update(cambios)
        return datos

    def test_la_tienda_sube_su_video_y_el_administrador_lo_aprueba(self):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('admin:planes_video_add'), self.datos(aprobado='on'))
        self.assertEqual(respuesta.status_code, 302)
        video = Video.objects.get()
        self.assertFalse(video.aprobado)
        self.assertEqual(video.duracion, Decimal('10.0'))
        self.assertEqual(mail.outbox[-1].to, ['sitio@example.com'])
        self.assertIn('Video por revisar', mail.outbox[-1].subject)
        # El vendedor no se lo aprueba a si mismo.
        self.client.post(reverse('admin:planes_video_changelist'), {
            'action': 'aprobar', '_selected_action': [video.pk],
        })
        video.refresh_from_db()
        self.assertFalse(video.aprobado)
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin:planes_video_changelist'), {
                'action': 'aprobar', '_selected_action': [video.pk],
            })
        video.refresh_from_db()
        self.assertTrue(video.aprobado)
        self.assertIsNotNone(video.revisado_el)
        self.assertEqual(sorted(mail.outbox[-1].to), ['tienda@example.com', 'vendedor@example.com'])

    def test_un_video_que_no_sirve_no_se_guarda(self):
        respuesta = self.client.post(reverse('admin:planes_video_add'), self.datos(archivo=subido(mp4(40))))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Recórtalo')
        self.assertFalse(Video.objects.exists())

    def test_cambiar_el_contenido_lo_devuelve_a_revision_y_apagarlo_no(self):
        video = self.video()
        url = reverse('admin:planes_video_change', args=[video.pk])
        self.client.post(url, self.datos(titulo=video.titulo, archivo='', activo=''))
        video.refresh_from_db()
        self.assertEqual((video.activo, video.aprobado), (False, True))
        self.client.post(url, self.datos(titulo='Otro título', archivo='', activo='on'))
        video.refresh_from_db()
        self.assertEqual((video.titulo, video.aprobado), ('Otro título', False))

    def test_cada_tienda_ve_y_cambia_solo_sus_videos(self):
        propio = self.video()
        ajeno = self.video(tienda=self.con_plan(self.ajena), titulo='De Fitnes')
        lista = self.client.get(reverse('admin:planes_video_changelist'))
        self.assertEqual(list(lista.context['cl'].result_list), [propio])
        self.assertNotEqual(self.client.get(reverse('admin:planes_video_change', args=[ajeno.pk])).status_code, 200)
        # Tampoco puede elegir un producto de otra tienda.
        Video.objects.filter(pk=propio.pk).delete()
        respuesta = self.client.post(reverse('admin:planes_video_add'), self.datos(producto=self.pesas.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Video.objects.filter(tienda=self.tienda).exists())

    def test_sin_cupo_o_sin_plan_no_puede_subir(self):
        self.video()
        self.assertEqual(self.client.get(reverse('admin:planes_video_add')).status_code, 403)
        lista = self.client.get(reverse('admin:planes_video_changelist'))
        self.assertContains(lista, 'ya tiene los 1 video(s)')
        Video.objects.all().delete()
        Tienda.objects.filter(pk=self.tienda.pk).update(plan=None)
        self.assertEqual(self.client.get(reverse('admin:planes_video_add')).status_code, 403)
        self.assertContains(self.client.get(reverse('admin:planes_video_changelist')), 'no incluye videos')

    @override_settings(VIDEOS_CONFIGURADOS=False)
    def test_sin_el_bucket_de_videos_no_se_ofrece(self):
        self.assertEqual(self.client.get(reverse('admin:planes_video_add')).status_code, 403)
        self.assertContains(self.client.get(reverse('admin:planes_video_changelist')), 'todavía no están disponibles')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('admin:planes_video_changelist')), 'SUPABASE_S3_BUCKET_VIDEOS')
