"""Lo que ve el cliente: el directorio, y que cada tienda tenga su catalogo, su carrito y sus pedidos aparte."""
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.tests.test_modelos import crear_producto
from core.models import CuentaBancaria
from pedidos.models import Pedido
from pedidos.tests.utiles import cupon_de_prueba, zona_de_prueba
from tiendas.models import Tienda

from .utiles import ruta, tienda_de_prueba

FETCH = {'HTTP_X_REQUESTED_WITH': 'fetch'}


class DosTiendas(TestCase):
    """Dos tiendas con su producto, su zona, su cupon y su cuenta. `multimix` es la que ya existia."""

    @classmethod
    def setUpTestData(cls):
        cls.multimix = tienda_de_prueba(whatsapp='18095550000')
        cls.fitnes = tienda_de_prueba('Fitnes RD', whatsapp='18295559999', banner_subtitulo='Todo para entrenar.')
        cls.lampara = crear_producto(nombre='Lámpara', sku='L1', precio=Decimal('1000'))
        cls.pesas = crear_producto(nombre='Pesas rusas', sku='P1', precio=Decimal('2500'), tienda=cls.fitnes)
        cls.zona_multimix = zona_de_prueba('Santo Domingo', '250')
        cls.zona_fitnes = zona_de_prueba('Santiago', '150', tienda=cls.fitnes)
        cupon_de_prueba('MULTI10')
        cupon_de_prueba('FIT10', tienda=cls.fitnes)
        CuentaBancaria.objects.create(tienda=cls.multimix, banco='Banco Popular', numero='111', titular='Multimix')
        CuentaBancaria.objects.create(tienda=cls.fitnes, banco='Banreservas', numero='222', titular='Fitnes')

    def agregar(self, producto, tienda, cantidad=1, **extra):
        return self.client.post(
            ruta('carrito:agregar', tienda=tienda), {'producto_id': producto.pk, 'cantidad': cantidad}, **extra,
        )

    def pedir(self, tienda, **cambios):
        datos = {
            'nombre': 'Ana Pérez', 'telefono': '809-555-1234', 'correo': '', 'metodo_entrega': 'recoger',
            'zona': '', 'direccion': '', 'referencia': '', 'metodo_pago': 'transferencia',
            'referencia_transferencia': '', 'cupon': '', 'notas': '', 'sitio_web': '',
        }
        datos.update(cambios)
        return self.client.post(ruta('pedidos:checkout', tienda=tienda), datos)


class DirectorioTests(DosTiendas):
    def test_la_portada_lista_las_tiendas_activas(self):
        Tienda.objects.create(nombre='En preparación', activa=False)
        respuesta = self.client.get('/')
        self.assertEqual(list(respuesta.context['tiendas']), [self.fitnes, self.multimix])
        self.assertContains(respuesta, 'href="/tienda/fitnes-rd/"')
        self.assertContains(respuesta, 'Todo para entrenar.')
        self.assertNotContains(respuesta, 'En preparación')
        # En el sitio no hay carrito: se compra dentro de cada tienda.
        self.assertNotContains(respuesta, 'js-contador-carrito')

    def test_la_portada_no_se_parece_al_inicio_de_una_tienda(self):
        portada = self.client.get('/')
        # Sin banner, sin boton de catalogo y sin el lema de ninguna tienda en su encabezado.
        self.assertNotContains(portada, 'mm-banner')
        self.assertNotContains(portada, 'Ver catálogo')
        self.assertNotContains(portada, 'Tu tienda de bienestar')
        self.assertContains(portada, 'Elige una tienda y empieza a comprar')
        self.assertContains(portada, 'Busca un producto en todas las tiendas')
        self.assertContains(portada, 'Tiendas de emprendedores en un solo lugar.')
        # El inicio de cada tienda si conserva su banner.
        tienda = self.client.get(self.multimix.get_absolute_url())
        self.assertContains(tienda, 'mm-banner-titulo')
        self.assertContains(tienda, 'Tu tienda de bienestar')

    def test_cada_tienda_lleva_su_marca_y_el_camino_de_regreso(self):
        respuesta = self.client.get(self.fitnes.get_absolute_url())
        self.assertContains(respuesta, '<span class="mm-logo-texto">Fitnes RD</span>', html=True)
        self.assertContains(respuesta, 'Todas las tiendas de Multimix RD')
        self.assertContains(respuesta, 'https://wa.me/18295559999')
        self.assertNotContains(respuesta, 'https://wa.me/18095550000')

    def test_tienda_apagada_desaparece_del_sitio(self):
        Tienda.objects.filter(pk=self.fitnes.pk).update(activa=False)
        for url in (self.fitnes.get_absolute_url(), self.pesas.get_absolute_url(),
                    ruta('carrito:detalle', tienda=self.fitnes), ruta('pedidos:checkout', tienda=self.fitnes)):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertNotContains(self.client.get(reverse('tiendas:buscar')), 'Pesas rusas')
        self.assertNotContains(self.client.get('/sitemap.xml'), '/tienda/fitnes-rd/')

    def test_buscador_del_sitio_lleva_a_la_tienda_de_cada_producto(self):
        respuesta = self.client.get(reverse('tiendas:buscar'))
        self.assertCountEqual([p.nombre for p in respuesta.context['pagina']], ['Lámpara', 'Pesas rusas'])
        self.assertContains(respuesta, self.pesas.get_absolute_url())
        self.assertContains(respuesta, 'Fitnes RD')
        self.assertContains(respuesta, 'Ver en la tienda')
        self.assertNotContains(respuesta, 'js-agregar')
        respuesta = self.client.get(reverse('tiendas:buscar'), {'q': 'pesas'})
        self.assertEqual([p.nombre for p in respuesta.context['pagina']], ['Pesas rusas'])

    def test_paginas_del_sitio(self):
        self.assertContains(self.client.get(reverse('core:terminos')), 'responde por sus productos')
        sitemap = self.client.get('/sitemap.xml')
        for url in ('/tienda/multimix-rd/', '/tienda/fitnes-rd/', self.pesas.get_absolute_url(), '/terminos/'):
            self.assertContains(sitemap, url)
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /tienda/*/carrito/')

    def test_enlaces_de_cuando_habia_una_sola_tienda(self):
        self.assertRedirects(
            self.client.get('/catalogo/', {'q': 'lampara'}), '/tienda/multimix-rd/catalogo/?q=lampara',
            fetch_redirect_response=False,
        )
        respuesta = self.client.get(f'/producto/{self.lampara.slug}/')
        self.assertRedirects(respuesta, self.lampara.get_absolute_url())
        self.assertRedirects(self.client.get('/como-comprar/'), ruta('core:como_comprar'))
        Tienda.objects.update(activa=False)
        self.assertEqual(self.client.get('/catalogo/').status_code, 404)


class CatalogoPorTiendaTests(DosTiendas):
    def test_cada_tienda_muestra_solo_su_catalogo(self):
        nombres = [p.nombre for p in self.client.get(ruta('catalogo:lista', tienda=self.fitnes)).context['pagina']]
        self.assertEqual(nombres, ['Pesas rusas'])
        inicio = self.client.get(self.multimix.get_absolute_url())
        self.assertContains(inicio, 'Lámpara')
        self.assertNotContains(inicio, 'Pesas rusas')

    def test_un_producto_no_se_abre_desde_otra_tienda(self):
        ajena = ruta('catalogo:producto', self.pesas.slug, tienda=self.multimix)
        self.assertEqual(self.client.get(ajena).status_code, 404)
        self.assertEqual(self.client.get(self.pesas.get_absolute_url()).status_code, 200)

    def test_como_comprar_y_envios_son_de_la_tienda(self):
        pagos = self.client.get(ruta('core:como_comprar', tienda=self.fitnes))
        self.assertContains(pagos, 'Banreservas')
        self.assertNotContains(pagos, 'Banco Popular')
        envios = self.client.get(ruta('core:envios', tienda=self.fitnes))
        self.assertEqual(list(envios.context['zonas']), [self.zona_fitnes])

    def test_el_menu_trae_las_categorias_de_la_tienda(self):
        from catalogo.models import Categoria

        deportes = Categoria.objects.create(nombre='Deportes')
        crear_producto(nombre='Mat de yoga', sku='P2', categoria=deportes, tienda=self.fitnes)
        en_fitnes = self.client.get(self.fitnes.get_absolute_url())
        self.assertCountEqual([c.nombre for c in en_fitnes.context['categorias_menu']], ['General', 'Deportes'])
        en_multimix = self.client.get(self.multimix.get_absolute_url())
        self.assertEqual([c.nombre for c in en_multimix.context['categorias_menu']], ['General'])
        vacia = self.client.get(ruta('catalogo:categoria', deportes.slug, tienda=self.multimix))
        self.assertEqual(list(vacia.context['pagina']), [])


class CarritoPorTiendaTests(DosTiendas):
    def test_cada_tienda_tiene_su_carrito(self):
        self.agregar(self.lampara, self.multimix, 2)
        self.agregar(self.pesas, self.fitnes, 1)
        en_multimix = self.client.get(ruta('carrito:detalle', tienda=self.multimix))
        en_fitnes = self.client.get(ruta('carrito:detalle', tienda=self.fitnes))
        self.assertEqual([(l.producto, l.cantidad) for l in en_multimix.context['lineas']], [(self.lampara, 2)])
        self.assertEqual([(l.producto, l.cantidad) for l in en_fitnes.context['lineas']], [(self.pesas, 1)])
        self.assertEqual((en_multimix.context['carrito_cantidad'], en_fitnes.context['carrito_cantidad']), (2, 1))
        self.assertEqual(en_fitnes.context['resumen'].total, Decimal('2500.00'))

    def test_no_se_agrega_un_producto_de_otra_tienda(self):
        respuesta = self.agregar(self.pesas, self.multimix, **FETCH)
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['cantidad_total'], 0)
        self.assertEqual(self.client.session.get(settings.CARRITO_SESSION_ID), None)

    def test_el_cupon_solo_vale_en_su_tienda(self):
        self.agregar(self.pesas, self.fitnes)
        url = ruta('carrito:cupon_aplicar', tienda=self.fitnes)
        self.assertFalse(self.client.post(url, {'codigo': 'MULTI10'}, **FETCH).json()['ok'])
        datos = self.client.post(url, {'codigo': 'fit10'}, **FETCH).json()
        self.assertEqual((datos['ok'], datos['cupon'], datos['total']), (True, 'FIT10', 'RD$ 2,250.00'))

    def test_carrito_del_formato_anterior_se_descarta_sin_romper(self):
        sesion = self.client.session
        sesion[settings.CARRITO_SESSION_ID] = {'items': {str(self.lampara.pk): 3}, 'cupon': 'MULTI10'}
        sesion.save()
        self.assertEqual(self.client.get(ruta('carrito:detalle')).context['lineas'], [])
        self.agregar(self.lampara, self.multimix)
        self.assertEqual(
            self.client.session[settings.CARRITO_SESSION_ID],
            {str(self.multimix.pk): {'items': {str(self.lampara.pk): 1}, 'cupon': ''}},
        )


class PedidoPorTiendaTests(DosTiendas):
    def test_el_pedido_es_de_la_tienda_y_no_toca_el_otro_carrito(self):
        self.agregar(self.lampara, self.multimix, 2)
        self.agregar(self.pesas, self.fitnes, 1)
        respuesta = self.pedir(self.fitnes)
        pedido = Pedido.objects.get()
        self.assertRedirects(respuesta, pedido.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(pedido.tienda, self.fitnes)
        self.assertEqual(pedido.numero, f'FIT-{timezone.localdate().year}-00001')
        self.assertEqual([d.producto for d in pedido.detalles.all()], [self.pesas])
        self.assertEqual(pedido.total, Decimal('2500.00'))

        # El carrito de la otra tienda sigue como estaba.
        self.assertEqual(self.client.get(ruta('carrito:detalle', tienda=self.fitnes)).context['lineas'], [])
        self.assertEqual(len(self.client.get(ruta('carrito:detalle', tienda=self.multimix)).context['lineas']), 1)

    def test_la_confirmacion_lleva_los_datos_de_la_tienda_que_vendio(self):
        self.agregar(self.pesas, self.fitnes)
        pagina = self.client.get(self.pedir(self.fitnes).url)
        self.assertEqual(pagina.context['tienda'], self.fitnes)
        self.assertTrue(pagina.context['enlace_whatsapp'].startswith('https://wa.me/18295559999?text='))
        self.assertContains(pagina, 'Banreservas')
        self.assertNotContains(pagina, 'Banco Popular')
        self.assertContains(pagina, 'Compra en <strong>Fitnes RD</strong>')
        self.assertContains(pagina, 'data-abrir="1"')

    def test_cada_tienda_numera_sus_pedidos_por_separado(self):
        for tienda, producto in ((self.multimix, self.lampara), (self.fitnes, self.pesas), (self.fitnes, self.pesas)):
            self.agregar(producto, tienda)
            self.pedir(tienda)
        anio = timezone.localdate().year
        self.assertEqual(
            list(Pedido.objects.order_by('id').values_list('numero', flat=True)),
            [f'MMX-{anio}-00001', f'FIT-{anio}-00001', f'FIT-{anio}-00002'],
        )

    def test_zona_y_cupon_de_otra_tienda_no_se_aceptan(self):
        self.agregar(self.pesas, self.fitnes)
        envio = {'metodo_entrega': 'envio', 'direccion': 'Calle 1 #5'}
        respuesta = self.pedir(self.fitnes, zona=self.zona_multimix.pk, **envio)
        self.assertIn('zona', respuesta.context['formulario'].errors)
        respuesta = self.pedir(self.fitnes, cupon='MULTI10')
        self.assertIn('cupon', respuesta.context['formulario'].errors)
        self.assertEqual(Pedido.objects.count(), 0)

        self.pedir(self.fitnes, zona=self.zona_fitnes.pk, cupon='FIT10', **envio)
        pedido = Pedido.objects.get()
        self.assertEqual((pedido.descuento, pedido.costo_envio, pedido.total),
                         (Decimal('250.00'), Decimal('150.00'), Decimal('2400.00')))

    def test_los_totales_en_vivo_usan_las_zonas_de_la_tienda(self):
        self.agregar(self.pesas, self.fitnes)
        url = ruta('pedidos:totales', tienda=self.fitnes)
        datos = self.client.post(url, {'metodo_entrega': 'envio', 'zona': self.zona_multimix.pk}).json()
        self.assertEqual(datos['envio'], 'Elige tu zona')
        datos = self.client.post(url, {'metodo_entrega': 'envio', 'zona': self.zona_fitnes.pk}).json()
        self.assertEqual((datos['envio'], datos['total']), ('RD$ 150.00', 'RD$ 2,650.00'))

    def test_contra_entrega_se_activa_por_tienda(self):
        Tienda.objects.filter(pk=self.fitnes.pk).update(permitir_contra_entrega=True)
        self.agregar(self.pesas, self.fitnes)
        self.agregar(self.lampara, self.multimix)
        self.assertContains(self.client.get(ruta('pedidos:checkout', tienda=self.fitnes)), 'pago-contra_entrega')
        self.assertNotContains(self.client.get(ruta('pedidos:checkout', tienda=self.multimix)), 'pago-contra_entrega')

    def test_la_factura_sale_a_nombre_de_la_tienda(self):
        self.agregar(self.pesas, self.fitnes)
        self.pedir(self.fitnes)
        pedido = Pedido.objects.get()
        with patch('pedidos.factura_views.generar_imagen_factura', return_value=b'png') as generar:
            self.client.get(reverse('pedidos:factura', args=[pedido.token]))
        self.assertEqual(generar.call_args.args[:2], (pedido, 'Fitnes RD'))
        verificacion = self.client.get(reverse('pedidos:verificar_factura', args=[pedido.token]))
        self.assertContains(verificacion, 'registrado en Fitnes RD')
