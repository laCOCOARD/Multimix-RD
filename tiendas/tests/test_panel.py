"""El panel de cada vendedor: ve y cambia solo lo de su tienda. El administrador principal ve todo."""
import tempfile
from decimal import Decimal
from unittest import mock

import tablib
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, Producto
from catalogo.resources import COLUMNAS
from catalogo.tests.test_modelos import crear_producto, imagen_de_prueba
from core.models import ConfiguracionTienda, CuentaBancaria
from pedidos.models import Pedido, ZonaEnvio
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import cupon_de_prueba, pedido_de_prueba, zona_de_prueba
from promociones.models import Cupon
from tiendas import services
from tiendas.models import Tienda

from .utiles import tienda_de_prueba

Estado = Pedido.Estado
CSV = '1'  # posicion de CSV en IMPORT_EXPORT_FORMATS


class PanelDeVendedores(TestCase):
    """Dos tiendas, cada una con su vendedor y con un producto, cupon, zona, cuenta y pedido propios."""

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_superuser('admin', 'admin@example.com', 'clave-segura-123')
        cls.propia = tienda_de_prueba()
        cls.ajena = tienda_de_prueba('Fitnes RD')
        cls.vendedor = Usuario.objects.create_user('vendedor', password='clave-segura-123')
        cls.otro_vendedor = Usuario.objects.create_user('otro', password='clave-segura-123')
        for tienda, usuario in ((cls.propia, cls.vendedor), (cls.ajena, cls.otro_vendedor)):
            tienda.usuarios.add(usuario)
            services.dar_acceso_al_panel([usuario])

        cls.lampara = crear_producto(nombre='Lámpara', sku='L1', precio=Decimal('1000'))
        cls.pesas = crear_producto(nombre='Pesas rusas', sku='P1', precio=Decimal('2500'), tienda=cls.ajena)
        cls.cupon_propio = cupon_de_prueba('MULTI10')
        cls.cupon_ajeno = cupon_de_prueba('FIT10', tienda=cls.ajena)
        cls.zona_propia = zona_de_prueba('Santo Domingo')
        cls.zona_ajena = zona_de_prueba('Zona de Fitnes', tienda=cls.ajena)
        cls.cuenta_propia = CuentaBancaria.objects.create(tienda=cls.propia, banco='Popular', numero='111', titular='M')
        cls.cuenta_ajena = CuentaBancaria.objects.create(tienda=cls.ajena, banco='Banreservas', numero='222', titular='F')
        cls.pedido_propio = pedido_de_prueba(cls.lampara, 2, nombre='Ana Pérez', telefono='8095551234')
        cls.pedido_ajeno = pedido_de_prueba(
            cls.pesas, 1, nombre='Carlos Ajeno', telefono='8295557777',
            metodo_entrega=Pedido.Entrega.ENVIO, zona=cls.zona_ajena, direccion='Calle 9',
        )

    def setUp(self):
        self.client.force_login(self.vendedor)

    def lista(self, nombre, **filtros):
        respuesta = self.client.get(reverse(f'admin:{nombre}_changelist'), filtros)
        return list(respuesta.context['cl'].result_list)


class ListasYDetalleTests(PanelDeVendedores):
    AJENOS = [
        ('catalogo_producto', 'pesas'), ('pedidos_pedido', 'pedido_ajeno'), ('promociones_cupon', 'cupon_ajeno'),
        ('pedidos_zonaenvio', 'zona_ajena'), ('core_cuentabancaria', 'cuenta_ajena'),
    ]

    def test_las_listas_solo_traen_lo_de_su_tienda(self):
        self.assertEqual(self.lista('catalogo_producto'), [self.lampara])
        self.assertEqual(self.lista('pedidos_pedido'), [self.pedido_propio])
        self.assertEqual(self.lista('promociones_cupon'), [self.cupon_propio])
        self.assertEqual(self.lista('pedidos_zonaenvio'), [self.zona_propia])
        self.assertEqual(self.lista('core_cuentabancaria'), [self.cuenta_propia])
        # Buscar tampoco encuentra lo de otra tienda.
        self.assertEqual(self.lista('catalogo_producto', q='P1'), [])
        self.assertEqual(self.lista('pedidos_pedido', q=self.pedido_ajeno.numero), [])

    def test_los_filtros_no_revelan_datos_de_otra_tienda(self):
        pedidos = self.client.get(reverse('admin:pedidos_pedido_changelist'))
        self.assertNotContains(pedidos, 'Zona de Fitnes')
        self.assertNotContains(pedidos, 'Fitnes RD')
        self.assertNotContains(pedidos, 'Carlos Ajeno')

    def test_lo_ajeno_no_se_abre_ni_se_borra_por_su_direccion(self):
        for nombre, atributo in self.AJENOS:
            objeto = getattr(self, atributo)
            for accion in ('change', 'delete', 'history'):
                url = reverse(f'admin:{nombre}_{accion}', args=[objeto.pk])
                self.assertNotEqual(self.client.get(url).status_code, 200, url)
            self.client.post(reverse(f'admin:{nombre}_delete', args=[objeto.pk]), {'post': 'yes'})
            self.assertTrue(type(objeto).objects.filter(pk=objeto.pk).exists(), nombre)

    def test_las_acciones_masivas_no_tocan_lo_ajeno(self):
        self.client.post(reverse('admin:catalogo_producto_changelist'), {
            'action': 'desactivar', '_selected_action': [self.lampara.pk, self.pesas.pk],
        })
        self.assertFalse(Producto.objects.get(pk=self.lampara.pk).activo)
        self.assertTrue(Producto.objects.get(pk=self.pesas.pk).activo)

        self.client.post(reverse('admin:pedidos_pedido_changelist'), {
            'action': 'marcar_cancelado', '_selected_action': [self.pedido_propio.pk, self.pedido_ajeno.pk],
        })
        estados = dict(Pedido.objects.values_list('pk', 'estado'))
        self.assertEqual(estados[self.pedido_propio.pk], Estado.CANCELADO)
        self.assertEqual(estados[self.pedido_ajeno.pk], Estado.PENDIENTE)

        self.client.post(reverse('admin:pedidos_pedido_changelist'), {
            'action': 'delete_selected', '_selected_action': [self.pedido_ajeno.pk], 'post': 'yes',
        })
        self.assertTrue(Pedido.objects.filter(pk=self.pedido_ajeno.pk).exists())

    def test_no_cambia_el_estado_de_un_pedido_ajeno(self):
        url = reverse('admin:pedidos_pedido_estado', args=[self.pedido_ajeno.pk])
        self.assertEqual(self.client.post(url, {'estado': 'pagado'}).status_code, 404)
        self.pedido_ajeno.refresh_from_db()
        self.assertEqual(self.pedido_ajeno.estado, Estado.PENDIENTE)
        propio = reverse('admin:pedidos_pedido_estado', args=[self.pedido_propio.pk])
        self.client.post(propio, {'estado': 'pagado'})
        self.pedido_propio.refresh_from_db()
        self.assertEqual(self.pedido_propio.estado, Estado.PAGADO)

    def test_lo_del_administrador_principal_esta_cerrado(self):
        cerradas = [
            reverse('admin:catalogo_categoria_changelist'), reverse('admin:catalogo_categoria_add'),
            reverse('admin:core_configuraciontienda_change', args=[ConfiguracionTienda.obtener().pk]),
            reverse('admin:auth_user_changelist'), reverse('admin:tiendas_tienda_add'),
            reverse('admin:tiendas_tienda_delete', args=[self.propia.pk]),
        ]
        for url in cerradas:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_el_administrador_principal_ve_todas_las_tiendas(self):
        self.client.force_login(self.admin)
        self.assertCountEqual(self.lista('catalogo_producto'), [self.lampara, self.pesas])
        self.assertCountEqual(self.lista('pedidos_pedido'), [self.pedido_propio, self.pedido_ajeno])
        self.assertEqual(self.lista('pedidos_pedido', tienda__id__exact=self.ajena.pk), [self.pedido_ajeno])
        self.assertContains(self.client.get(reverse('admin:pedidos_pedido_changelist')), 'Fitnes RD')
        detalle = self.client.get(reverse('admin:pedidos_pedido_change', args=[self.pedido_ajeno.pk]))
        self.assertEqual(detalle.status_code, 200)

    def test_personal_sin_tienda_no_ve_nada(self):
        suelto = get_user_model().objects.create_user('suelto', password='clave-segura-123')
        services.dar_acceso_al_panel([suelto])
        self.client.force_login(suelto)
        for nombre in ('catalogo_producto', 'pedidos_pedido', 'promociones_cupon', 'tiendas_tienda'):
            self.assertEqual(self.lista(nombre), [], nombre)
        self.client.post(reverse('admin:pedidos_zonaenvio_add'), {'nombre': 'Colada', 'tarifa': '10', 'orden': '0'})
        self.assertFalse(ZonaEnvio.objects.filter(nombre='Colada').exists())


class CrearYEditarTests(PanelDeVendedores):
    def producto(self, **cambios):
        datos = {
            'tienda': self.propia.pk, 'nombre': 'Taza', 'slug': '', 'sku': 'T1',
            'categoria': self.lampara.categoria_id, 'descripcion': '', 'precio': '300', 'stock_almacen': '5',
            'activo': 'on', 'fotos-TOTAL_FORMS': 0, 'fotos-INITIAL_FORMS': 0,
        }
        datos.update(cambios)
        return datos

    def test_lo_que_crea_queda_en_su_tienda(self):
        formulario = self.client.get(reverse('admin:catalogo_producto_add'))
        self.assertContains(formulario, f'<input type="hidden" name="tienda" value="{self.propia.pk}"')
        self.assertNotContains(formulario, 'Fitnes RD')
        self.client.post(reverse('admin:catalogo_producto_add'), self.producto())
        self.assertEqual(Producto.objects.get(sku='T1').tienda, self.propia)

        self.client.post(reverse('admin:promociones_cupon_add'), {
            'tienda': self.propia.pk, 'codigo': 'nuevo', 'tipo': 'porcentaje', 'valor': '5', 'compra_minima': '0',
            'activo': 'on',
        })
        self.assertEqual(Cupon.objects.get(codigo='NUEVO').tienda, self.propia)

    def test_no_puede_crear_en_otra_tienda(self):
        respuesta = self.client.post(reverse('admin:catalogo_producto_add'), self.producto(tienda=self.ajena.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('tienda', respuesta.context['adminform'].form.errors)
        self.assertFalse(Producto.objects.filter(sku='T1').exists())

    def test_no_puede_pasar_un_producto_a_otra_tienda(self):
        url = reverse('admin:catalogo_producto_change', args=[self.lampara.pk])
        self.client.post(url, self.producto(tienda=self.ajena.pk, nombre='Lámpara nueva', sku='L1', slug='lampara'))
        self.lampara.refresh_from_db()
        self.assertEqual((self.lampara.tienda, self.lampara.nombre), (self.propia, 'Lámpara nueva'))

    def test_el_sku_se_repite_entre_tiendas_pero_no_en_la_propia(self):
        # P1 ya existe en la otra tienda: aqui se puede usar.
        self.client.post(reverse('admin:catalogo_producto_add'), self.producto(sku='p1'))
        self.assertEqual(Producto.objects.filter(sku='P1').count(), 2)
        respuesta = self.client.post(reverse('admin:catalogo_producto_add'), self.producto(sku='L1', nombre='Otra'))
        self.assertContains(respuesta, 'Ya tienes un producto con ese SKU.')
        self.assertEqual(Producto.objects.filter(tienda=self.propia, sku='L1').count(), 1)
        # Al editar, el SKU repetido tambien se avisa en vez de fallar.
        taza = Producto.objects.get(tienda=self.propia, sku='P1')
        respuesta = self.client.post(
            reverse('admin:catalogo_producto_change', args=[taza.pk]), self.producto(sku='L1', slug=taza.slug),
        )
        self.assertContains(respuesta, 'Ya tienes un producto con ese SKU.')

    def test_el_administrador_elige_la_tienda_al_crear(self):
        self.client.force_login(self.admin)
        formulario = self.client.get(reverse('admin:catalogo_producto_add'))
        self.assertContains(formulario, 'Fitnes RD')
        self.client.post(reverse('admin:catalogo_producto_add'), self.producto(tienda=self.ajena.pk))
        self.assertEqual(Producto.objects.get(sku='T1').tienda, self.ajena)


class ImportarYFotosTests(PanelDeVendedores):
    def importar(self, filas, tienda):
        datos = tablib.Dataset(*filas, headers=COLUMNAS)
        archivo = SimpleUploadedFile('productos.csv', datos.export('csv').encode(), content_type='text/csv')
        respuesta = self.client.post(reverse('admin:catalogo_producto_import'), {
            'import_file': archivo, 'format': CSV, 'resource': '0', 'tienda': tienda.pk,
        })
        confirmar = respuesta.context.get('confirm_form')
        if confirmar is not None:
            self.client.post(reverse('admin:catalogo_producto_process_import'), confirmar.initial)
        return respuesta

    def test_importar_no_pisa_el_mismo_sku_de_otra_tienda(self):
        fila = ['P1', 'Pesas de la casa', 'General', '', '900', '', '', '', 7, 0, 0, 1]
        self.importar([fila], self.propia)
        self.pesas.refresh_from_db()
        self.assertEqual((self.pesas.nombre, self.pesas.precio), ('Pesas rusas', Decimal('2500.00')))
        nuevo = Producto.objects.get(tienda=self.propia, sku='P1')
        self.assertEqual((nuevo.nombre, nuevo.stock_almacen), ('Pesas de la casa', 7))

    def test_importar_actualiza_por_sku_dentro_de_la_tienda(self):
        self.importar([['l1', 'Lámpara renovada', 'General', '', '1200', '', '', '', 30, 1, 0, 1]], self.propia)
        self.lampara.refresh_from_db()
        self.assertEqual((self.lampara.nombre, self.lampara.precio), ('Lámpara renovada', Decimal('1200.00')))
        self.assertEqual(Producto.objects.filter(tienda=self.propia).count(), 1)

    def test_no_importa_en_una_tienda_ajena(self):
        respuesta = self.importar([['N1', 'Colado', 'General', '', '10', '', '', '', 1, 0, 0, 1]], self.ajena)
        self.assertIn('tienda', respuesta.context['form'].errors)
        self.assertFalse(Producto.objects.filter(sku='N1').exists())

    def test_solo_el_administrador_crea_categorias_al_importar(self):
        fila = ['N1', 'Silla', 'Muebles', '', '2500', '', '', '', 8, 0, 0, 1]
        self.importar([fila], self.propia)
        self.assertFalse(Categoria.objects.filter(nombre='Muebles').exists())
        self.assertFalse(Producto.objects.filter(sku='N1').exists())
        self.client.force_login(self.admin)
        self.importar([fila], self.propia)
        self.assertEqual(Producto.objects.get(sku='N1').categoria.nombre, 'Muebles')

    def test_exportar_solo_trae_sus_productos(self):
        url = reverse('admin:catalogo_producto_export')
        formulario = self.client.get(url).context['form']
        campos = {nombre: 'on' for nombre, campo in formulario.fields.items() if getattr(campo, 'is_selectable_field', False)}
        respuesta = self.client.post(url, {'format': CSV, 'resource': '0', **campos})
        contenido = respuesta.content.decode()
        self.assertIn('L1', contenido)
        self.assertNotIn('P1', contenido)
        self.assertNotIn('Pesas', contenido)

    def test_fotos_por_sku_solo_en_su_tienda(self):
        url = reverse('admin:catalogo_producto_fotos_por_sku')
        with tempfile.TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            # El vendedor no llega al producto P1, que es de la otra tienda, ni diciendo que es suya.
            respuesta = self.client.post(
                url, {'fotos': [imagen_de_prueba('P1.png'), imagen_de_prueba('L1.png')], 'tienda': self.ajena.pk},
            )
            self.assertContains(respuesta, '1 foto(s) asignadas, 1 sin asignar.')
            self.assertFalse(self.pesas.fotos.exists())
            self.assertEqual(self.lampara.fotos.count(), 1)

            # El administrador principal maneja varias tiendas: tiene que elegir una.
            self.client.force_login(self.admin)
            self.assertContains(self.client.get(url), '<select name="tienda"')
            self.client.post(url, {'fotos': imagen_de_prueba('P1.png')})
            self.assertFalse(self.pesas.fotos.exists())
            self.client.post(url, {'fotos': imagen_de_prueba('P1.png'), 'tienda': self.ajena.pk})
            self.assertEqual(self.pesas.fotos.count(), 1)


class VentasYClientesTests(PanelDeVendedores):
    def test_el_resumen_es_de_su_tienda(self):
        cambiar_estado(self.pedido_propio, Estado.PAGADO)
        cambiar_estado(self.pedido_ajeno, Estado.PAGADO)
        respuesta = self.client.get(reverse('admin:index'))
        resumen = respuesta.context['resumen']
        self.assertEqual(resumen['ventas_mes'], Decimal('2000.00'))
        self.assertEqual(list(resumen['ultimos_pedidos']), [self.pedido_propio])
        self.assertEqual([fila['producto__nombre'] for fila in resumen['mas_vendidos']], ['Lámpara'])
        self.assertNotIn('ventas_por_tienda', respuesta.context)
        self.assertContains(respuesta, 'Resumen de Multimix RD')
        self.assertNotContains(respuesta, 'Fitnes RD')
        self.assertNotContains(respuesta, 'Pesas rusas')

    def test_el_administrador_ve_el_total_y_el_desglose(self):
        cambiar_estado(self.pedido_propio, Estado.PAGADO)
        cambiar_estado(self.pedido_ajeno, Estado.PAGADO)
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('admin:index'))
        self.assertEqual(respuesta.context['resumen']['ventas_mes'], Decimal('4750.00'))
        desglose = {t.nombre: (t.ventas_mes, t.pedidos_mes, t.pendientes) for t in respuesta.context['ventas_por_tienda']}
        self.assertEqual(desglose, {
            'Multimix RD': (Decimal('2000.00'), 1, 0), 'Fitnes RD': (Decimal('2750.00'), 1, 0),
        })
        self.assertContains(respuesta, 'Ventas del mes por tienda')

    def test_clientes_de_su_tienda(self):
        cambiar_estado(self.pedido_propio, Estado.PAGADO)
        pedido_de_prueba(self.lampara, 1, nombre='Ana P. de Gómez', telefono='8095551234', correo='')
        url = reverse('admin:pedidos_pedido_clientes')
        self.assertContains(self.client.get(reverse('admin:pedidos_pedido_changelist')), url)
        respuesta = self.client.get(url)
        (fila,) = respuesta.context['filas']
        # Una fila por telefono, con el nombre del pedido mas reciente y lo cobrado hasta ahora.
        self.assertEqual(
            (fila['nombre'], fila['telefono'], fila['correo'], fila['total_pedidos'], fila['comprado']),
            ('Ana P. de Gómez', '8095551234', 'ana@example.com', 2, Decimal('2000.00')),
        )
        self.assertContains(respuesta, 'https://wa.me/18095551234')
        self.assertNotContains(respuesta, 'Carlos Ajeno')
        self.assertNotContains(respuesta, '829-555-7777')
        self.assertEqual(self.client.get(url, {'q': 'carlos'}).context['filas'], [])
        self.assertEqual(len(self.client.get(url, {'q': '809-555'}).context['filas']), 1)

    def test_el_administrador_ve_los_clientes_por_tienda(self):
        pedido_de_prueba(self.pesas, 1, nombre='Ana Pérez', telefono='8095551234')
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('admin:pedidos_pedido_clientes'))
        vistos = sorted((fila['tienda'], fila['telefono']) for fila in respuesta.context['filas'])
        # Quien compra en dos tiendas es un cliente en cada una.
        self.assertEqual(vistos, [
            ('Fitnes RD', '8095551234'), ('Fitnes RD', '8295557777'), ('Multimix RD', '8095551234'),
        ])
        self.assertContains(respuesta, '<th scope="col">Tienda</th>', html=True)

    def test_sin_permiso_no_ve_clientes(self):
        lector = get_user_model().objects.create_user('lector', password='clave-segura-123', is_staff=True)
        self.propia.usuarios.add(lector)
        self.client.force_login(lector)
        self.assertEqual(self.client.get(reverse('admin:pedidos_pedido_clientes')).status_code, 403)


class TiendaAdminTests(PanelDeVendedores):
    def datos(self, **cambios):
        datos = {
            'nombre': 'Multimix RD', 'banner_titulo': 'Bienvenidos', 'banner_subtitulo': '',
            'banner_texto_boton': 'Ver catálogo', 'whatsapp': '18095551111', 'telefono': '', 'correo': '',
            'horario': '', 'direccion_tienda': 'Calle 1', 'facebook': '', 'instagram': '', 'tiktok': '',
        }
        datos.update(cambios)
        return datos

    def test_el_vendedor_entra_directo_a_su_tienda_y_edita_sus_datos(self):
        editar = reverse('admin:tiendas_tienda_change', args=[self.propia.pk])
        self.assertRedirects(self.client.get(reverse('admin:tiendas_tienda_changelist')), editar)
        self.client.post(editar, self.datos(permitir_contra_entrega='on'))
        self.propia.refresh_from_db()
        self.assertEqual(
            (self.propia.whatsapp, self.propia.direccion_tienda, self.propia.permitir_contra_entrega),
            ('18095551111', 'Calle 1', True),
        )

    def test_el_vendedor_no_cambia_lo_que_decide_el_administrador(self):
        editar = reverse('admin:tiendas_tienda_change', args=[self.propia.pk])
        formulario = self.client.get(editar)
        for campo in ('name="slug"', 'name="prefijo"', 'name="activa"', 'name="usuarios"', 'name="orden"'):
            self.assertNotContains(formulario, campo)
        self.client.post(editar, self.datos(
            slug='robada', prefijo='ZZZ', orden='9', usuarios=[self.vendedor.pk, self.otro_vendedor.pk],
        ))
        self.propia.refresh_from_db()
        self.assertEqual((self.propia.slug, self.propia.prefijo, self.propia.orden), ('multimix-rd', 'MMX', 0))
        self.assertTrue(self.propia.activa)
        self.assertEqual(list(self.propia.usuarios.all()), [self.vendedor])

    def test_el_vendedor_no_abre_la_tienda_de_otro(self):
        ajena = reverse('admin:tiendas_tienda_change', args=[self.ajena.pk])
        self.assertNotEqual(self.client.get(ajena).status_code, 200)
        self.client.post(ajena, self.datos(nombre='Fitnes RD', whatsapp='18090000000'))
        self.ajena.refresh_from_db()
        self.assertEqual(self.ajena.whatsapp, '')

    def test_el_administrador_crea_la_tienda_y_le_da_acceso_al_vendedor(self):
        nuevo = get_user_model().objects.create_user('alfonso', password='clave-segura-123')
        self.client.force_login(self.admin)
        self.client.post(reverse('admin:tiendas_tienda_add'), self.datos(
            nombre='Calzado Alfonso', slug='', prefijo='', activa='on', orden='0', usuarios=[nuevo.pk], whatsapp='',
        ))
        tienda = Tienda.objects.get(nombre='Calzado Alfonso')
        self.assertEqual((tienda.slug, tienda.prefijo), ('calzado-alfonso', 'CAL'))

        # Con solo asignarlo ya puede entrar al panel, y ve su tienda vacia.
        self.client.force_login(get_user_model().objects.get(pk=nuevo.pk))
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.assertEqual(self.lista('catalogo_producto'), [])
        self.assertEqual(self.lista('pedidos_pedido'), [])

    def test_avisa_que_las_imagenes_no_se_guardaron_si_el_formulario_tiene_errores(self):
        # El navegador olvida los archivos elegidos cuando el formulario vuelve con errores.
        self.client.force_login(self.admin)
        crear = reverse('admin:tiendas_tienda_add')
        nueva = self.datos(nombre='MaxFit Proteínas', slug='', prefijo='', activa='on', orden='0')
        with tempfile.TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            respuesta = self.client.post(crear, {**nueva, 'whatsapp': '555', 'logo': imagen_de_prueba('logo.png')})
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, 'vuelve a elegir las imágenes')
            self.assertFalse(Tienda.objects.filter(nombre='MaxFit Proteínas').exists())
            # Sin archivos no hay nada que avisar.
            self.assertNotContains(self.client.post(crear, {**nueva, 'whatsapp': '555'}), 'vuelve a elegir las imágenes')

            self.client.post(crear, {
                **nueva, 'prefijo': 'max', 'whatsapp': '829-555-1234',
                'logo': imagen_de_prueba('Logo MaxFit Proteínas.PNG'),
                'banner_imagen': imagen_de_prueba('diseño banner.jpg', 'JPEG'),
            })
            tienda = Tienda.objects.get(nombre='MaxFit Proteínas')
            self.assertEqual((tienda.prefijo, tienda.whatsapp), ('MAX', '18295551234'))
            # El nombre del archivo no se conserva: Supabase rechaza los que traen tildes o ñ.
            self.assertRegex(tienda.logo.name, r'^tiendas/[0-9a-f]{32}\.png$')
            self.assertRegex(tienda.banner_imagen.name, r'^tiendas/[0-9a-f]{32}\.jpg$')
            portada = self.client.get('/')
            self.assertContains(portada, tienda.logo.url)
            self.assertContains(portada, tienda.banner_imagen.url)

    def test_si_el_almacenamiento_de_fotos_falla_avisa_y_no_guarda_nada(self):
        editar = reverse('admin:tiendas_tienda_change', args=[self.propia.pk])
        datos = self.datos(direccion_tienda='Calle nueva', logo=imagen_de_prueba('logo.png'))
        with mock.patch.object(FileSystemStorage, '_save', side_effect=OSError('el almacenamiento no responde')):
            with self.assertLogs('core.admin_avisos', level='ERROR'):
                respuesta = self.client.post(editar, datos)
        self.assertRedirects(respuesta, editar, fetch_redirect_response=False)
        self.assertContains(self.client.get(editar), 'No se pudo guardar la imagen')
        self.propia.refresh_from_db()
        self.assertEqual((self.propia.logo.name, self.propia.direccion_tienda), ('', ''))

    def test_el_prefijo_no_cambia_despues_de_crear_la_tienda(self):
        self.client.force_login(self.admin)
        editar = reverse('admin:tiendas_tienda_change', args=[self.ajena.pk])
        self.assertNotContains(self.client.get(editar), 'name="prefijo"')
        self.client.post(editar, self.datos(
            nombre='Fitnes RD', slug='fitnes-rd', prefijo='XXX', activa='on', orden='0', whatsapp='',
        ))
        self.ajena.refresh_from_db()
        self.assertEqual(self.ajena.prefijo, 'FIT')
