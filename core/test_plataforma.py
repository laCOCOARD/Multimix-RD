import json
import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalogo.models import Disponibilidad
from catalogo.tests.test_modelos import crear_producto
from clientes.services import registrar_cliente
from core import tareas
from opiniones import services as opiniones
from opiniones.models import Resena
from pedidos.models import Pedido
from pedidos.reportes import rango, reporte_de_ventas
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import pedido_de_prueba
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

CLAVE = 'clave-segura-123'
CACHE_REAL = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'pruebas-de-plataforma'}}
Estado = Pedido.Estado


class ReporteDeVentasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_superuser('admin', 'admin@example.com', CLAVE)
        cls.propia = tienda_de_prueba()
        cls.ajena = tienda_de_prueba('Fitnes RD')
        cls.vendedor = Usuario.objects.create_user('vendedor', password=CLAVE)
        cls.propia.usuarios.add(cls.vendedor)
        dar_acceso_al_panel([cls.vendedor])
        cls.lampara = crear_producto(nombre='Lámpara', sku='L1', precio=Decimal('1000'))
        cls.pesas = crear_producto(nombre='Pesas', sku='P1', precio=Decimal('2500'), tienda=cls.ajena)

        cls.cobrado = cambiar_estado(pedido_de_prueba(cls.lampara, 2), Estado.PAGADO)
        cls.pendiente = pedido_de_prueba(cls.lampara, 1)
        cancelado = cambiar_estado(pedido_de_prueba(cls.lampara, 1), Estado.PAGADO)
        cambiar_estado(cancelado, Estado.CANCELADO)
        reembolsado = cambiar_estado(pedido_de_prueba(cls.lampara, 3), Estado.PAGADO)
        reembolsado = cambiar_estado(reembolsado, Estado.ENTREGADO)
        cambiar_estado(reembolsado, Estado.REEMBOLSADO)
        cls.ajeno = cambiar_estado(pedido_de_prueba(cls.pesas, 1), Estado.PAGADO)

    def test_solo_cuenta_lo_cobrado_que_no_se_cancelo_ni_se_reembolso(self):
        hoy = timezone.localdate()
        reporte = reporte_de_ventas(Pedido.objects.filter(tienda=self.propia), hoy, hoy)
        self.assertEqual((reporte['cobrado'], reporte['pedidos'], reporte['promedio']), (Decimal('2000.00'), 1, Decimal('2000.00')))
        self.assertEqual(reporte['reembolsos'], {'pedidos': 1, 'monto': Decimal('3000.00')})
        self.assertEqual([(f['dia'], f['pedidos'], f['cobrado']) for f in reporte['por_dia']], [(hoy, 1, Decimal('2000.00'))])
        self.assertEqual([(f['metodo'], f['cobrado']) for f in reporte['por_pago']], [('Transferencia bancaria', Decimal('2000.00'))])
        self.assertEqual([(f['nombre_producto'], f['unidades']) for f in reporte['productos']], [('Lámpara', 2)])

        ayer = hoy - timedelta(days=1)
        self.assertEqual(reporte_de_ventas(Pedido.objects.all(), ayer, ayer)['pedidos'], 0)

    def test_el_rango_se_corrige_solo(self):
        hoy = timezone.localdate()
        self.assertEqual(rango('', ''), (hoy - timedelta(days=29), hoy))
        self.assertEqual(rango('no-es-fecha', '2999-01-01'), (hoy - timedelta(days=29), hoy))
        self.assertEqual(rango('2020-01-01', '2020-01-10'), (hoy.replace(2020, 1, 1), hoy.replace(2020, 1, 10)))
        desde, hasta = rango('2000-01-01', '')
        self.assertEqual((hasta - desde).days, 366)

    def test_cada_vendedor_ve_el_reporte_de_su_tienda(self):
        url = reverse('admin:pedidos_pedido_reporte')
        self.client.force_login(self.vendedor)
        pagina = self.client.get(url)
        self.assertEqual(pagina.context['reporte']['cobrado'], Decimal('2000.00'))
        self.assertNotContains(pagina, 'Pesas')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).context['reporte']['cobrado'], Decimal('4500.00'))

    def test_descarga_csv_y_pide_permiso(self):
        url = reverse('admin:pedidos_pedido_reporte')
        self.client.force_login(self.vendedor)
        respuesta = self.client.get(url, {'formato': 'csv'})
        self.assertEqual(respuesta['Content-Type'], 'text/csv; charset=utf-8')
        contenido = respuesta.content.decode('utf-8-sig')
        self.assertIn('Dia,Pedidos,Cobrado (RD$)', contenido)
        self.assertIn('Total,1,2000.00', contenido)
        self.client.force_login(get_user_model().objects.create_user('sin-permisos', is_staff=True))
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_el_historial_de_acciones_es_solo_del_administrador(self):
        url = reverse('admin:admin_logentry_changelist')
        self.client.force_login(self.vendedor)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:admin_logentry_add')).status_code, 403)


class DatosEstructuradosTests(TestCase):
    def datos(self, producto):
        pagina = self.client.get(producto.get_absolute_url()).content.decode()
        return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', pagina, re.S).group(1))

    def test_producto_con_su_oferta_real_y_sin_valoracion_inventada(self):
        producto = crear_producto(nombre='Vitamina C', marca='Nutrilite', precio=Decimal('1000'), precio_oferta=Decimal('800'))
        datos = self.datos(producto)
        self.assertEqual((datos['@type'], datos['name'], datos['brand']['name']), ('Product', 'Vitamina C', 'Nutrilite'))
        self.assertEqual((datos['offers']['price'], datos['offers']['priceCurrency']), ('800.00', 'DOP'))
        self.assertEqual(datos['offers']['availability'], 'https://schema.org/InStock')
        self.assertTrue(datos['url'].startswith('http://testserver/tienda/'))
        self.assertNotIn('aggregateRating', datos)

    def test_disponibilidad_y_valoracion_cuando_hay_resenas_publicadas(self):
        producto = crear_producto(nombre='Taza', controla_stock=False, disponibilidad=Disponibilidad.BAJO_PEDIDO)
        self.assertEqual(self.datos(producto)['offers']['availability'], 'https://schema.org/BackOrder')
        ana = registrar_cliente('Ana Pérez', 'ana@example.com', CLAVE)
        opiniones.guardar_resena(ana, producto, 4, 'Buen producto, lo recomiendo.')
        self.assertNotIn('aggregateRating', self.datos(producto))  # por revisar: todavia no cuenta
        Resena.objects.update(estado=Resena.Estado.APROBADA)
        self.assertEqual(self.datos(producto)['aggregateRating'], {'@type': 'AggregateRating', 'ratingValue': '4.0', 'reviewCount': 1})

    def test_el_texto_del_producto_no_puede_cerrar_el_script(self):
        producto = crear_producto(nombre='Taza </script><script>alert(1)</script>', descripcion='<b>hola</b> & más')
        pagina = self.client.get(producto.get_absolute_url()).content.decode()
        self.assertNotIn('</script><script>alert(1)', pagina)
        self.assertEqual(self.datos(producto)['description'], '<b>hola</b> & más')


class PlataformaTests(TestCase):
    def test_salud(self):
        respuesta = self.client.get(reverse('core:salud'))
        self.assertEqual((respuesta.status_code, respuesta.content), (200, b'ok'))

    def test_cabecera_de_politica_de_contenido(self):
        politica = self.client.get(reverse('tiendas:portada'))['Content-Security-Policy']
        for regla in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "form-action 'self'", 'https://cdn.jsdelivr.net'):
            self.assertIn(regla, politica)

    @override_settings(CACHES=CACHE_REAL, TAREAS_AUTOMATICAS=True)
    def test_una_visita_cancela_los_pedidos_vencidos_como_mucho_una_vez_por_hora(self):
        cache.delete(tareas.CLAVE)
        producto = crear_producto(stock_almacen=5)
        vencido = pedido_de_prueba(producto, 2)
        reciente = pedido_de_prueba(producto, 1)
        Pedido.objects.filter(pk=vencido.pk).update(creado=timezone.now() - timedelta(hours=49))

        self.client.get(reverse('core:salud'))
        vencido.refresh_from_db()
        reciente.refresh_from_db()
        producto.refresh_from_db()
        self.assertEqual((vencido.estado, reciente.estado, producto.stock_reservado), (Estado.CANCELADO, Estado.PENDIENTE, 1))

        # Dentro de la misma hora no se repite.
        Pedido.objects.filter(pk=reciente.pk).update(creado=timezone.now() - timedelta(hours=49))
        self.client.get(reverse('core:salud'))
        reciente.refresh_from_db()
        self.assertEqual(reciente.estado, Estado.PENDIENTE)
        cache.delete(tareas.CLAVE)

    def test_en_las_pruebas_el_mantenimiento_esta_apagado(self):
        self.assertFalse(tareas.ejecutar_si_toca())
