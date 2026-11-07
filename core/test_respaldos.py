import gzip
import json
import shutil
import tempfile
from datetime import timedelta

from django.core.files.storage import storages
from django.test import TestCase, override_settings
from django.utils import timezone

from catalogo.models import Producto
from core import respaldos
from catalogo.tests.test_modelos import crear_producto


class RespaldosTests(TestCase):
    def setUp(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        ajustes = override_settings(STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
            'privado': {'BACKEND': 'django.core.files.storage.FileSystemStorage', 'OPTIONS': {'location': carpeta}},
        })
        ajustes.enable()
        self.addCleanup(ajustes.disable)

    def test_el_respaldo_trae_los_datos_y_se_puede_leer(self):
        producto = crear_producto(nombre='Perfume de prueba')
        ruta = respaldos.respaldar()
        with storages['privado'].open(ruta) as archivo:
            filas = json.loads(gzip.decompress(archivo.read()))
        modelos = {fila['model'] for fila in filas}
        self.assertIn('catalogo.producto', modelos)
        self.assertNotIn('sessions.session', modelos)
        self.assertTrue(any(f['fields'].get('nombre') == producto.nombre for f in filas))

    def test_loaddata_lo_restaura(self):
        from django.core.management import call_command

        producto = crear_producto(nombre='Reloj de prueba')
        ruta = respaldos.respaldar()
        Producto.objects.all().delete()
        call_command('loaddata', storages['privado'].path(ruta), verbosity=0)
        self.assertTrue(Producto.objects.filter(nombre=producto.nombre).exists())

    def test_solo_respalda_una_vez_por_semana(self):
        ahora = timezone.now()
        self.assertIsNotNone(respaldos.respaldar_si_toca(ahora))
        self.assertIsNone(respaldos.respaldar_si_toca(ahora + timedelta(days=6)))
        self.assertIsNotNone(respaldos.respaldar_si_toca(ahora + timedelta(days=7)))
        self.assertEqual(len(respaldos.respaldos()), 2)

    def test_guarda_solo_los_ultimos(self):
        ahora = timezone.now()
        for semana in range(respaldos.GUARDAR + 3):
            respaldos.respaldar(ahora + timedelta(days=7 * semana))
        lista = respaldos.respaldos()
        self.assertEqual(len(lista), respaldos.GUARDAR)
        self.assertEqual(timezone.localtime(lista[0][0]).date(), timezone.localtime(
            ahora + timedelta(days=7 * (respaldos.GUARDAR + 2))).date())

    @override_settings(SUPABASE_BUCKET_PRIVADO='', STORAGES={
        'default': {'BACKEND': 'storages.backends.s3.S3Storage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        'privado': {'BACKEND': 'storages.backends.s3.S3Storage'},
    })
    def test_sin_bucket_privado_no_respalda_en_el_publico(self):
        self.assertFalse(respaldos.disponible())
        self.assertIsNone(respaldos.respaldar_si_toca())
        self.assertEqual(Producto.objects.count(), 0)
