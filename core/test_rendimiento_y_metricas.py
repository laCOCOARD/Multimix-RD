"""Fase 4 del rediseño (2026-10-27): miniaturas de las fotos, medicion del negocio sin datos personales y los
indicadores del panel, cada uno visto solo por quien corresponde."""
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from PIL import Image

from catalogo.models import FotoProducto
from catalogo.services import crear_miniaturas_faltantes
from catalogo.tests.test_modelos import crear_producto, imagen_de_prueba
from core import metricas
from core.models import ConteoDiario
from pedidos.models import Pedido
from pedidos.tests.utiles import pedido_de_prueba
from tiendas.models import SolicitudTienda
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba

CLAVE = 'clave-segura-123'
NAVEGADOR = {'HTTP_USER_AGENT': 'Mozilla/5.0 (Linux; Android 14) Chrome/130 Mobile Safari/537.36'}
Evento = ConteoDiario.Evento


class ConMedia(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.media.cleanup)
        ajuste = self.settings(MEDIA_ROOT=self.media.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)


class MiniaturasTests(ConMedia):
    def test_la_foto_nueva_trae_su_miniatura_y_las_tarjetas_la_usan(self):
        producto = crear_producto(nombre='Lámpara')
        foto = FotoProducto.objects.create(producto=producto, imagen=imagen_de_prueba(tamano=(2000, 1000)))
        with Image.open(foto.imagen.path) as grande, Image.open(foto.miniatura.path) as chica:
            self.assertEqual((grande.size, chica.size, chica.format), ((1200, 600), (480, 240), 'WEBP'))
        self.assertEqual(foto.url_tarjeta, foto.miniatura.url)
        portada = self.client.get('/')
        self.assertContains(portada, foto.miniatura.url)
        self.assertNotContains(portada, f'src="{foto.imagen.url}"')
        # La ficha si muestra la foto grande.
        self.assertContains(self.client.get(producto.get_absolute_url()), f'src="{foto.imagen.url}"')
        # Al borrarla se van los dos archivos.
        rutas = [Path(foto.imagen.path), Path(foto.miniatura.path)]
        foto.delete()
        self.assertFalse(any(ruta.exists() for ruta in rutas))

    def test_las_fotos_de_antes_se_completan_de_a_pocas(self):
        producto = crear_producto(nombre='Lámpara')
        salida = BytesIO()
        Image.new('RGB', (1200, 1200), (10, 120, 200)).save(salida, 'WEBP')
        viejas = []
        for numero in range(3):
            foto = FotoProducto(producto=producto)
            foto.imagen.save(f'vieja-{numero}.webp', ContentFile(salida.getvalue()), save=False)
            FotoProducto.objects.bulk_create([foto])
            viejas.append(foto)
        # Sin miniatura todavia: la tarjeta usa la grande.
        primera = FotoProducto.objects.filter(miniatura='').first()
        self.assertEqual(primera.url_tarjeta, primera.imagen.url)
        self.assertEqual(crear_miniaturas_faltantes(limite=2), 2)
        self.assertEqual(crear_miniaturas_faltantes(limite=2), 1)
        self.assertEqual(crear_miniaturas_faltantes(limite=2), 0)
        for foto in FotoProducto.objects.all():
            with Image.open(foto.miniatura.path) as chica:
                self.assertEqual(chica.size, (480, 480))

    def test_una_foto_perdida_no_se_reintenta_para_siempre(self):
        producto = crear_producto(nombre='Lámpara')
        foto = FotoProducto(producto=producto, imagen='productos/no-existe.webp')
        FotoProducto.objects.bulk_create([foto])
        self.assertEqual(crear_miniaturas_faltantes(), 1)
        foto = FotoProducto.objects.get()
        self.assertEqual(foto.miniatura.name, foto.imagen.name)
        self.assertEqual(crear_miniaturas_faltantes(), 0)


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ConsultasTests(ConMedia):
    def test_la_portada_no_hace_una_consulta_por_producto(self):
        """La cantidad de consultas no crece con los productos (sin consultas repetidas por tarjeta).

        Con la cache de produccion: en las pruebas va apagada y la configuracion del sitio (que cada tarjeta mira para
        saber si el producto es "Nuevo") se leeria de la base cada vez.
        """
        from django.core.cache import cache

        self.addCleanup(cache.clear)
        def contar():
            self.client.get('/')
            with CaptureQueriesContext(connection) as consultas:
                self.assertEqual(self.client.get('/').status_code, 200)
            return len(consultas)

        for numero in range(3):
            crear_producto(nombre=f'Producto {numero}', sku=f'A{numero}')
        pocas = contar()
        for numero in range(9):
            producto = crear_producto(nombre=f'Otro {numero}', sku=f'B{numero}')
            FotoProducto.objects.create(producto=producto, imagen=imagen_de_prueba(tamano=(50, 50)))
        self.assertLessEqual(contar(), pocas + 2)


class MetricasTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.otra = tienda_de_prueba('Rincón Fitness', prefijo='FIT')
        self.producto = crear_producto(nombre='Lámpara de mesa', precio=Decimal('1000'))

    def total(self, evento, tienda=None):
        filas = ConteoDiario.objects.filter(evento=evento, tienda=tienda)
        return sum(filas.values_list('total', flat=True))

    def test_cuenta_el_recorrido_sin_datos_personales(self):
        self.client.get(reverse('tiendas:buscar'), {'q': 'lampara'}, **NAVEGADOR)
        self.client.get(reverse('tiendas:buscar'), {'q': 'zzzz'}, **NAVEGADOR)
        self.client.get(self.tienda.get_absolute_url(), **NAVEGADOR)
        self.client.get(self.producto.get_absolute_url(), **NAVEGADOR)
        self.client.get(self.producto.get_absolute_url(), **NAVEGADOR)
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1}, **NAVEGADOR)
        entrar_como_cliente(self.client)
        self.client.get(ruta('pedidos:checkout'), **NAVEGADOR)
        self.client.post(ruta('pedidos:checkout'), {'nombre': ''}, **NAVEGADOR)
        self.assertEqual(
            [self.total(Evento.BUSQUEDA), self.total(Evento.BUSQUEDA_SIN_RESULTADOS),
             self.total(Evento.VISITA_TIENDA, self.tienda), self.total(Evento.VISTA_PRODUCTO, self.tienda),
             self.total(Evento.AGREGADO_CARRITO, self.tienda), self.total(Evento.INICIO_COMPRA, self.tienda),
             self.total(Evento.ERROR_COMPRA, self.tienda)],
            [2, 1, 1, 2, 1, 1, 1],
        )
        # Una fila por dia, evento y tienda; nada de quien fue ni de lo que escribio.
        self.assertEqual(ConteoDiario.objects.filter(evento=Evento.VISTA_PRODUCTO).count(), 1)
        campos = {campo.name for campo in ConteoDiario._meta.get_fields()}
        self.assertEqual(campos, {'id', 'fecha', 'evento', 'tienda', 'total'})

    def test_no_cuenta_robots_ni_al_personal(self):
        self.client.get(self.producto.get_absolute_url())  # sin navegador
        self.client.get(self.producto.get_absolute_url(), HTTP_USER_AGENT='Googlebot/2.1 (+http://www.google.com/bot.html)')
        personal = get_user_model().objects.create_user('vendedor', 'v@example.com', CLAVE, is_staff=True)
        self.client.force_login(personal)
        self.client.get(self.producto.get_absolute_url(), **NAVEGADOR)
        self.assertFalse(ConteoDiario.objects.exists())

    def test_si_falla_al_contar_la_pagina_sigue(self):
        from unittest import mock

        with mock.patch.object(ConteoDiario.objects, 'filter', side_effect=metricas.DatabaseError('caida')):
            self.assertEqual(self.client.get(self.producto.get_absolute_url(), **NAVEGADOR).status_code, 200)

    def test_resumen_por_tienda_y_pedidos_reales(self):
        pedido_de_prueba(self.producto, 1)
        ConteoDiario.objects.create(fecha=metricas.timezone.localdate(), evento=Evento.VISTA_PRODUCTO, tienda=self.tienda, total=5)
        ConteoDiario.objects.create(fecha=metricas.timezone.localdate(), evento=Evento.VISTA_PRODUCTO, tienda=self.otra, total=7)
        propio = {fila['etiqueta']: fila['valor'] for fila in metricas.resumen([self.tienda])['embudo']}
        todo = {fila['etiqueta']: fila['valor'] for fila in metricas.resumen()['embudo']}
        self.assertEqual((propio['Productos vistos'], propio['Pedidos creados']), (5, 1))
        self.assertEqual(todo['Productos vistos'], 12)
        self.assertEqual(metricas.resumen([self.otra])['embudo'][4]['valor'], 0)


class IndicadoresDelPanelTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_superuser('admin', 'dueno@example.com', CLAVE)
        self.tienda = tienda_de_prueba()
        self.otra = tienda_de_prueba('Rincón Fitness', prefijo='FIT')
        self.vendedor = Usuario.objects.create_user('vendedor', 'vendedor@example.com', CLAVE)
        self.tienda.usuarios.add(self.vendedor)
        dar_acceso_al_panel([self.vendedor])
        hoy = metricas.timezone.localdate()
        ConteoDiario.objects.create(fecha=hoy, evento=Evento.VISITA_TIENDA, tienda=self.tienda, total=3)
        ConteoDiario.objects.create(fecha=hoy, evento=Evento.VISITA_TIENDA, tienda=self.otra, total=40)

    def test_el_administrador_ve_los_indicadores_del_sitio(self):
        for numero in range(3):
            SolicitudTienda.objects.create(nombre_responsable='X', nombre_comercial=f'N{numero}', correo='x@example.com',
                                           telefono='8095551234', descripcion='Dulces criollos de la casa.')
        self.client.force_login(self.admin)
        inicio = self.client.get(reverse('admin:index'))
        self.assertEqual(inicio.context['indicadores']['tiendas_activas'], 2)
        self.assertEqual(inicio.context['indicadores']['solicitudes_pendientes'], 3)
        # Con menos de 5 revisadas no se inventa un porcentaje.
        self.assertIsNone(inicio.context['indicadores']['conversion_solicitudes'])
        self.assertContains(inicio, 'Se calcula con 5 revisadas o más')
        self.assertEqual(inicio.context['actividad']['embudo'][0]['valor'], 43)
        SolicitudTienda.objects.update(estado='aprobada')
        for numero in range(2):
            SolicitudTienda.objects.create(nombre_responsable='X', nombre_comercial=f'R{numero}', correo='x@example.com',
                                           telefono='8095551234', descripcion='Dulces criollos de la casa.', estado='rechazada')
        self.assertEqual(self.client.get(reverse('admin:index')).context['indicadores']['conversion_solicitudes'], 60)

    def test_el_vendedor_ve_solo_lo_de_su_tienda(self):
        self.client.force_login(self.vendedor)
        inicio = self.client.get(reverse('admin:index'))
        self.assertNotIn('indicadores', inicio.context)
        self.assertEqual(inicio.context['actividad']['embudo'][0]['valor'], 3)
        self.assertContains(inicio, 'en tu tienda')
        self.assertNotContains(inicio, 'Solicitudes pendientes')
        self.assertNotContains(inicio, 'Tiendas activas')
