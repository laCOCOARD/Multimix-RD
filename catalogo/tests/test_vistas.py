from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo import services
from catalogo.models import Categoria, Producto
from core.models import ConfiguracionTienda
from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import pedido_de_prueba

from .test_modelos import crear_producto


class CatalogoVistasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hogar = Categoria.objects.create(nombre='Hogar')
        cls.tecnologia = Categoria.objects.create(nombre='Tecnología')
        cls.lampara = crear_producto(categoria=cls.hogar, nombre='Lámpara de mesa', sku='H1', precio=Decimal('1500'))
        cls.taza = crear_producto(
            categoria=cls.hogar, nombre='Taza térmica', sku='H2', precio=Decimal('600'), precio_oferta=Decimal('450'),
        )
        cls.audifonos = crear_producto(
            categoria=cls.tecnologia, nombre='Audífonos', sku='T1', precio=Decimal('2500'), stock_almacen=0,
            destacado=True,
        )
        cls.oculto = crear_producto(categoria=cls.hogar, nombre='Producto oculto', sku='H3', activo=False)

    def nombres(self, respuesta):
        return [p.nombre for p in respuesta.context['pagina']]

    def test_inicio_muestra_secciones(self):
        respuesta = self.client.get(reverse('catalogo:inicio'))
        self.assertEqual(respuesta.status_code, 200)
        titulos = [s['titulo'] for s in respuesta.context['secciones']]
        self.assertEqual(titulos, ['Ofertas', 'Destacados', 'Nuevos'])
        self.assertContains(respuesta, 'Multimix RD')
        self.assertContains(respuesta, 'RD$ 450.00')
        self.assertNotContains(respuesta, 'Producto oculto')

    def test_lista_excluye_inactivos(self):
        respuesta = self.client.get(reverse('catalogo:lista'))
        self.assertCountEqual(self.nombres(respuesta), ['Lámpara de mesa', 'Taza térmica', 'Audífonos'])

    def test_categoria_inactiva_oculta_sus_productos(self):
        Categoria.objects.filter(pk=self.tecnologia.pk).update(activa=False)
        self.assertNotIn('Audífonos', self.nombres(self.client.get(reverse('catalogo:lista'))))
        self.assertEqual(self.client.get(self.tecnologia.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(self.audifonos.get_absolute_url()).status_code, 404)

    def test_filtros(self):
        url = reverse('catalogo:lista')
        self.assertEqual(self.nombres(self.client.get(url, {'q': 'taza'})), ['Taza térmica'])
        # La busqueda ignora tildes y mayusculas, y exige todas las palabras.
        self.assertEqual(self.nombres(self.client.get(url, {'q': 'AUDIFONOS'})), ['Audífonos'])
        self.assertEqual(self.nombres(self.client.get(url, {'q': 'termica taza'})), ['Taza térmica'])
        self.assertEqual(self.nombres(self.client.get(url, {'q': 'taza lampara'})), [])
        self.assertEqual(self.nombres(self.client.get(url, {'q': 'h1'})), ['Lámpara de mesa'])
        self.assertEqual(self.nombres(self.client.get(url, {'oferta': 'on'})), ['Taza térmica'])
        self.assertCountEqual(
            self.nombres(self.client.get(url, {'disponibles': 'on'})), ['Lámpara de mesa', 'Taza térmica'],
        )
        # El rango usa el precio final: la taza cuesta 450 por la oferta.
        self.assertEqual(self.nombres(self.client.get(url, {'precio_max': '500'})), ['Taza térmica'])
        self.assertEqual(self.nombres(self.client.get(url, {'precio_min': '2000'})), ['Audífonos'])
        self.assertCountEqual(
            self.nombres(self.client.get(self.hogar.get_absolute_url())), ['Lámpara de mesa', 'Taza térmica'],
        )

    def test_filtros_invalidos_no_rompen(self):
        respuesta = self.client.get(reverse('catalogo:lista'), {'precio_min': 'abc', 'orden': 'x', 'pagina': 'zz'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(self.nombres(respuesta)), 3)

    def test_orden_por_precio_y_mas_vendidos(self):
        url = reverse('catalogo:lista')
        self.assertEqual(
            self.nombres(self.client.get(url, {'orden': 'precio_asc'})),
            ['Taza térmica', 'Lámpara de mesa', 'Audífonos'],
        )
        self.assertEqual(self.nombres(self.client.get(url, {'orden': 'precio_desc'}))[0], 'Audífonos')
        cambiar_estado(pedido_de_prueba(self.lampara, 3), Pedido.Estado.PAGADO)
        pedido_de_prueba(self.taza, 5)  # pendiente: no cuenta como venta
        self.assertEqual(self.nombres(self.client.get(url, {'orden': 'vendidos'}))[0], 'Lámpara de mesa')
        self.assertEqual(services.mas_vendidos(), [self.lampara])

    def test_paginacion(self):
        for numero in range(15):
            crear_producto(categoria=self.hogar, nombre=f'Extra {numero}', sku=f'X{numero}')
        respuesta = self.client.get(reverse('catalogo:lista'))
        self.assertEqual(len(respuesta.context['pagina']), 12)
        self.assertEqual(respuesta.context['pagina'].paginator.num_pages, 2)
        respuesta = self.client.get(reverse('catalogo:lista'), {'pagina': 2, 'orden': 'precio_asc'})
        self.assertEqual(len(respuesta.context['pagina']), 6)

    def test_nuevos_por_fecha_o_marca(self):
        Producto.objects.update(creado=timezone.now() - timedelta(days=40))
        self.assertEqual(services.nuevos(), [])
        Producto.objects.filter(pk=self.taza.pk).update(nuevo=True)
        self.assertEqual(services.nuevos(), [self.taza])

    def test_detalle_con_open_graph_y_relacionados(self):
        config = ConfiguracionTienda.obtener()
        config.whatsapp = '18095550000'
        config.save()
        respuesta = self.client.get(self.taza.get_absolute_url())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'property="og:title" content="Taza térmica · RD$ 450.00"')
        self.assertContains(respuesta, 'property="product:price:currency" content="DOP"')
        self.assertContains(respuesta, 'Preguntar por WhatsApp')
        self.assertContains(respuesta, 'https://wa.me/18095550000?text=')
        self.assertEqual(respuesta.context['relacionados'], [self.lampara])

    def test_detalle_disponibilidad(self):
        self.assertContains(self.client.get(self.audifonos.get_absolute_url()), 'Agotado')
        self.assertNotContains(self.client.get(self.audifonos.get_absolute_url()), 'Agregar al carrito')
        Producto.objects.filter(pk=self.lampara.pk).update(stock_almacen=3)
        respuesta = self.client.get(self.lampara.get_absolute_url())
        self.assertContains(respuesta, '¡Quedan 3!')
        self.assertContains(respuesta, 'max="3"')

    def test_producto_inactivo_da_404_propio(self):
        respuesta = self.client.get(self.oculto.get_absolute_url())
        self.assertEqual(respuesta.status_code, 404)
        self.assertTemplateUsed(respuesta, '404.html')

    def test_paginas_informativas_sitemap_y_robots(self):
        for nombre in ('core:como_comprar', 'core:envios'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)
        sitemap = self.client.get('/sitemap.xml')
        self.assertContains(sitemap, self.taza.get_absolute_url())
        self.assertNotContains(sitemap, self.oculto.get_absolute_url())
        robots = self.client.get('/robots.txt')
        self.assertEqual(robots['Content-Type'], 'text/plain; charset=utf-8')
        self.assertContains(robots, 'Sitemap: http://testserver/sitemap.xml')
