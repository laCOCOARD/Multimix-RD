import tempfile
from decimal import Decimal
from io import BytesIO, StringIO

import tablib
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from catalogo.models import Categoria, Producto
from catalogo.resources import COLUMNAS, ProductoResource
from catalogo.tests.test_modelos import crear_producto
from core.models import ConfiguracionTienda
from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import pedido_de_prueba
from promociones.models import Cupon

Estado = Pedido.Estado


class PanelBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'clave-segura-123')
        cls.producto = crear_producto(nombre='Lámpara', sku='L1', precio=Decimal('1000'), stock_almacen=10)

    def setUp(self):
        self.client.force_login(self.admin)


class PortadaTests(PanelBase):
    def test_ruta_del_panel_viene_de_la_configuracion(self):
        self.assertEqual(reverse('admin:index'), f'/{settings.ADMIN_URL}/')

    def test_exige_iniciar_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse('admin:index'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('login', respuesta.url)

    def test_resumen(self):
        cambiar_estado(pedido_de_prueba(self.producto, 2), Estado.PAGADO)
        pedido_de_prueba(self.producto, 1, transferencia_realizada=True)
        cancelado = cambiar_estado(pedido_de_prueba(self.producto, 1), Estado.PAGADO)
        cambiar_estado(cancelado, Estado.CANCELADO)
        crear_producto(nombre='Casi agotado', sku='B1', stock_almacen=2)
        crear_producto(nombre='Sin stock', sku='A1', stock_almacen=0)

        respuesta = self.client.get(reverse('admin:index'))
        resumen = respuesta.context['resumen']
        self.assertEqual(resumen['ventas_dia'], Decimal('2000.00'))
        self.assertEqual(resumen['ventas_mes'], Decimal('2000.00'))
        self.assertEqual(resumen['pedidos_pendientes'], 1)
        self.assertEqual(resumen['transferencias_por_verificar'], 1)
        self.assertEqual((resumen['total_stock_bajo'], resumen['total_agotados']), (1, 1))
        self.assertEqual(len(resumen['ultimos_pedidos']), 3)
        self.assertEqual([fila['unidades'] for fila in resumen['mas_vendidos']], [2])
        self.assertContains(respuesta, 'Ventas de hoy')
        self.assertContains(respuesta, 'RD$ 2,000.00')
        self.assertContains(respuesta, 'css/panel.css')


class ConfiguracionAdminTests(PanelBase):
    def test_no_se_crea_otra_ni_se_borra(self):
        config = ConfiguracionTienda.obtener()
        self.assertEqual(self.client.get(reverse('admin:core_configuraciontienda_add')).status_code, 403)
        borrar = reverse('admin:core_configuraciontienda_delete', args=[config.pk])
        self.assertEqual(self.client.post(borrar, {'post': 'yes'}).status_code, 403)
        self.assertEqual(ConfiguracionTienda.objects.count(), 1)

    def test_la_lista_lleva_a_editar(self):
        respuesta = self.client.get(reverse('admin:core_configuraciontienda_changelist'))
        self.assertRedirects(respuesta, reverse('admin:core_configuraciontienda_change', args=[1]))


class PedidoAdminTests(PanelBase):
    def accion(self, nombre, *pedidos):
        return self.client.post(
            reverse('admin:pedidos_pedido_changelist'),
            {'action': nombre, '_selected_action': [p.pk for p in pedidos]}, follow=True,
        )

    def test_lista_y_detalle(self):
        pedido = pedido_de_prueba(self.producto, 2)
        lista = self.client.get(reverse('admin:pedidos_pedido_changelist'))
        self.assertContains(lista, pedido.numero)
        self.assertContains(lista, 'https://wa.me/18095551234')
        self.assertContains(lista, 'panel-estado-pendiente')
        detalle = self.client.get(reverse('admin:pedidos_pedido_change', args=[pedido.pk]))
        self.assertContains(detalle, 'Lámpara')
        self.assertEqual(detalle.context['transiciones'], [('pagado', 'Pagado'), ('cancelado', 'Cancelado')])

    def test_no_se_crean_ni_se_borran_desde_el_panel(self):
        pedido = pedido_de_prueba(self.producto, 1)
        self.assertEqual(self.client.get(reverse('admin:pedidos_pedido_add')).status_code, 403)
        borrar = reverse('admin:pedidos_pedido_delete', args=[pedido.pk])
        self.assertEqual(self.client.post(borrar, {'post': 'yes'}).status_code, 403)

    def test_el_estado_no_se_edita_a_mano(self):
        pedido = pedido_de_prueba(self.producto, 1)
        self.client.post(reverse('admin:pedidos_pedido_change', args=[pedido.pk]), {
            'estado': 'entregado', 'total': '1', 'notas_internas': 'Cliente frecuente',
            'detalles-TOTAL_FORMS': 0, 'detalles-INITIAL_FORMS': 0,
        })
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.PENDIENTE)
        self.assertEqual(pedido.total, Decimal('1000.00'))
        self.assertEqual(pedido.notas_internas, 'Cliente frecuente')

    def test_acciones_usan_la_capa_de_servicios(self):
        pedido = pedido_de_prueba(self.producto, 2)
        respuesta = self.accion('marcar_enviado', pedido)
        self.assertContains(respuesta, 'no puede pasar a')
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.PENDIENTE)

        self.accion('marcar_pagado', pedido)
        self.accion('marcar_listo', pedido)
        respuesta = self.accion('marcar_entregado', pedido)
        self.assertContains(respuesta, '1 pedido(s) pasaron a')
        pedido.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.ENTREGADO)
        self.assertEqual((self.producto.stock_almacen, self.producto.stock_reservado), (8, 0))

    def test_botones_de_estado_en_el_detalle(self):
        pedido = pedido_de_prueba(self.producto, 2)
        url = reverse('admin:pedidos_pedido_estado', args=[pedido.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        respuesta = self.client.post(url, {'estado': 'cancelado'}, follow=True)
        self.assertContains(respuesta, 'pasó a')
        pedido.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.CANCELADO)
        self.assertEqual(self.producto.stock_reservado, 0)
        respuesta = self.client.post(url, {'estado': 'pagado'}, follow=True)
        self.assertContains(respuesta, 'no puede pasar a')

    def test_sin_permiso_no_cambia_estados(self):
        pedido = pedido_de_prueba(self.producto, 1)
        empleado = get_user_model().objects.create_user('lector', password='clave-segura-123', is_staff=True)
        self.client.force_login(empleado)
        url = reverse('admin:pedidos_pedido_estado', args=[pedido.pk])
        self.assertEqual(self.client.post(url, {'estado': 'pagado'}).status_code, 403)


class ProductoAdminTests(PanelBase):
    def test_lista_con_filtros(self):
        crear_producto(nombre='Casi agotado', sku='B1', stock_almacen=2)
        crear_producto(nombre='Sin stock', sku='A1', stock_almacen=0)
        crear_producto(nombre='Rebajado', sku='O1', precio_oferta=Decimal('500'))
        url = reverse('admin:catalogo_producto_changelist')

        def nombres(**filtros):
            return sorted(p.nombre for p in self.client.get(url, filtros).context['cl'].result_list)

        self.assertEqual(len(nombres()), 4)
        self.assertEqual(nombres(stock='bajo'), ['Casi agotado'])
        self.assertEqual(nombres(stock='agotado'), ['Sin stock'])
        self.assertEqual(nombres(oferta='vigente'), ['Rebajado'])
        self.assertEqual(nombres(q='L1'), ['Lámpara'])
        self.assertContains(self.client.get(url), 'Plantilla de Excel')

    def test_oferta_masiva_y_quitar_oferta(self):
        url = reverse('admin:catalogo_producto_changelist')
        seleccion = {'action': 'poner_oferta', '_selected_action': [self.producto.pk]}
        self.assertContains(self.client.post(url, seleccion), 'Aplicar oferta')
        self.client.post(url, {
            **seleccion, 'aplicar': '1', 'porcentaje': '15', 'inicio': '2026-01-01T08:00', 'fin': '2099-01-31T23:59',
        })
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio_oferta, Decimal('850.00'))
        self.assertTrue(self.producto.en_oferta)
        self.assertEqual(self.producto.oferta_fin.year, 2099)

        self.client.post(url, {'action': 'quitar_oferta', '_selected_action': [self.producto.pk]})
        self.producto.refresh_from_db()
        self.assertIsNone(self.producto.precio_oferta)

    def test_acciones_destacar_y_desactivar(self):
        url = reverse('admin:catalogo_producto_changelist')
        self.client.post(url, {'action': 'destacar', '_selected_action': [self.producto.pk]})
        self.client.post(url, {'action': 'desactivar', '_selected_action': [self.producto.pk]})
        self.producto.refresh_from_db()
        self.assertTrue(self.producto.destacado)
        self.assertFalse(self.producto.activo)

    def test_el_almacen_no_baja_de_lo_reservado(self):
        pedido_de_prueba(self.producto, 4)
        respuesta = self.client.post(reverse('admin:catalogo_producto_change', args=[self.producto.pk]), {
            'nombre': 'Lámpara', 'slug': 'lampara', 'sku': 'L1', 'categoria': self.producto.categoria_id,
            'descripcion': '', 'precio': '1000', 'stock_almacen': '3', 'activo': 'on',
            'fotos-TOTAL_FORMS': 0, 'fotos-INITIAL_FORMS': 0,
        })
        self.assertContains(respuesta, 'unidades reservadas')
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_almacen, 10)

    def test_plantilla_de_excel(self):
        respuesta = self.client.get(reverse('admin:catalogo_producto_plantilla'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('plantilla_productos.xlsx', respuesta['Content-Disposition'])
        hoja = load_workbook(BytesIO(respuesta.content)).active
        self.assertEqual([celda.value for celda in hoja[1]], COLUMNAS)

    def test_importar_crea_y_actualiza_por_sku(self):
        datos = tablib.Dataset(headers=COLUMNAS)
        datos.append(['l1', 'Lámpara renovada', 'General', '', '1200', '', '', '', 30, 1, 0, 1])
        datos.append(['N-1', 'Silla plegable', 'Muebles', 'Liviana', '2500', '1999', '', '', 8, 0, 1, 1])
        resultado = ProductoResource().import_data(datos, dry_run=False)
        self.assertFalse(resultado.has_errors() or resultado.has_validation_errors())

        self.producto.refresh_from_db()
        self.assertEqual((self.producto.nombre, self.producto.precio, self.producto.stock_almacen),
                         ('Lámpara renovada', Decimal('1200.00'), 30))
        silla = Producto.objects.get(sku='N-1')
        self.assertEqual((silla.categoria.nombre, silla.precio_oferta, silla.slug),
                         ('Muebles', Decimal('1999.00'), 'silla-plegable'))
        self.assertTrue(Categoria.objects.filter(nombre='Muebles').exists())

    def test_importar_rechaza_filas_invalidas(self):
        datos = tablib.Dataset(headers=COLUMNAS)
        datos.append(['M-1', 'Oferta mayor al precio', 'General', '', '100', '150', '', '', 1, 0, 0, 1])
        resultado = ProductoResource().import_data(datos, dry_run=True)
        self.assertTrue(resultado.has_validation_errors())
        self.assertFalse(Producto.objects.filter(sku='M-1').exists())

    def test_exportar_no_incluye_el_stock_reservado(self):
        exportado = ProductoResource().export()
        self.assertEqual(exportado.headers, COLUMNAS)
        self.assertEqual(exportado.dict[0]['sku'], 'L1')


class CargarDemoTests(TestCase):
    def test_carga_la_demo_y_se_puede_repetir(self):
        with tempfile.TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            call_command('cargar_demo', stdout=StringIO())
            totales = (Producto.objects.count(), Categoria.objects.count(), Pedido.objects.count())
            self.assertEqual(totales, (20, 6, 4))
            self.assertTrue(Cupon.objects.filter(codigo='BIENVENIDO10').exists())
            self.assertTrue(all(p.foto_principal for p in Producto.objects.prefetch_related('fotos')))
            self.assertTrue(ConfiguracionTienda.obtener().whatsapp)
            self.assertEqual(self.client.get('/').status_code, 200)

            call_command('cargar_demo', stdout=StringIO())
            self.assertEqual(
                (Producto.objects.count(), Categoria.objects.count(), Pedido.objects.count()), totales,
            )


class OtrosAdminTests(PanelBase):
    def test_listas_cargan(self):
        Cupon.objects.create(codigo='BIENVENIDO10', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('10'), usos_maximos=5)
        for nombre in ('promociones_cupon', 'pedidos_zonaenvio', 'catalogo_categoria', 'core_cuentabancaria'):
            respuesta = self.client.get(reverse(f'admin:{nombre}_changelist'))
            self.assertEqual(respuesta.status_code, 200, nombre)
        self.assertContains(self.client.get(reverse('admin:promociones_cupon_changelist')), '0 / 5')
