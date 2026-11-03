"""Ficha para comprar y carrito de todas las tiendas (pedido del dueño el 2026-11-02): las tarjetas llevan a la ficha;
la ficha muestra entrega con zonas, pago, devoluciones, el mismo producto en otras tiendas y similares; el carrito de
la cabecera se ve y se edita sin cuenta."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalogo.models import Producto
from catalogo.services import en_otras_tiendas, similares_en_otras_tiendas
from catalogo.tests.test_modelos import crear_producto
from pedidos.tests.utiles import zona_de_prueba
from tiendas.tests.utiles import ruta, tienda_de_prueba


class FichaParaComprarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.multimix = tienda_de_prueba()
        cls.otra = tienda_de_prueba('Otra Tienda')
        cls.tercera = tienda_de_prueba('Tercera')
        cls.crema = crear_producto(nombre='Crema hidratante', sku='CR-1', precio=Decimal('1000'))
        # El mismo producto en otras tiendas: por SKU (mas barato) y por nombre (mas caro).
        cls.barata = crear_producto(nombre='Crema hidratante 50 ml', sku='cr-1', precio=Decimal('850'), tienda=cls.otra)
        cls.cara = crear_producto(nombre='CREMA HIDRATANTE', sku='X-9', precio=Decimal('1200'), tienda=cls.tercera)
        cls.agotada = crear_producto(nombre='Crema hidratante', sku='CR-2', precio=Decimal('500'), tienda=cls.tercera,
                                     disponibilidad=Producto.Disponibilidad.AGOTADO)
        cls.parecido = crear_producto(nombre='Jabón de avena', sku='J-1', tienda=cls.otra)
        zona_de_prueba('Santo Domingo', '250')
        zona_de_prueba('Mi barrio', '0')

    def test_el_mismo_producto_en_otras_tiendas_del_mas_barato_al_mas_caro(self):
        otras = en_otras_tiendas(self.crema)
        self.assertEqual(otras, [self.barata, self.cara])
        self.assertEqual([o.ahorro for o in otras], [Decimal('150'), 0])
        ficha = self.client.get(self.crema.get_absolute_url())
        self.assertContains(ficha, 'También lo venden otras tiendas')
        self.assertContains(ficha, 'Ahorras RD$ 150.00')
        self.assertEqual(ficha.context['mas_barato_en'], self.barata)
        self.assertContains(ficha, 'lo tiene en RD$ 850.00')

    def test_similares_de_otras_tiendas_sin_repetir_los_mismos(self):
        similares = similares_en_otras_tiendas(self.crema, excluir=[self.barata.pk, self.cara.pk])
        self.assertEqual(similares, [self.parecido])
        ficha = self.client.get(self.crema.get_absolute_url())
        self.assertContains(ficha, 'Similares en otras tiendas')
        self.assertIn(self.parecido, ficha.context['similares'])
        # En la ficha, la tarjeta de otra tienda dice quien lo vende.
        self.assertContains(ficha, 'Vendido por')

    def test_la_ficha_muestra_entrega_pago_y_devoluciones(self):
        ficha = self.client.get(self.crema.get_absolute_url())
        for texto in ('Entrega', 'Santo Domingo', 'RD$ 250.00', 'Gratis', 'Para recoger: listo', 'Cambios y devoluciones',
                      'Comprar ahora', 'Agregar al carrito', 'js-paso-cantidad', 'js/cantidad'):
            self.assertContains(ficha, texto)

    def test_las_tarjetas_no_tienen_botones_de_compra(self):
        lista = self.client.get(ruta('catalogo:lista'))
        self.assertNotContains(lista, 'mm-tarjeta-comprar')
        self.assertContains(lista, f'class="stretched-link" href="{self.crema.get_absolute_url()}"')


class CarritoDeTodasLasTiendasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.multimix = tienda_de_prueba()
        cls.otra = tienda_de_prueba('Otra Tienda')
        cls.crema = crear_producto(nombre='Crema', sku='C1', precio=Decimal('1000'))
        cls.jabon = crear_producto(nombre='Jabón', sku='J1', precio=Decimal('300'), tienda=cls.otra)

    def setUp(self):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.crema.pk, 'cantidad': 1})
        self.client.post(ruta('carrito:agregar', tienda=self.otra), {'producto_id': self.jabon.pk, 'cantidad': 2})
        self.url = reverse('carrito_global:global')

    def test_se_ve_sin_cuenta_y_pide_entrar_al_pagar(self):
        carrito = self.client.get(self.url)
        self.assertEqual(carrito.status_code, 200)
        self.assertContains(carrito, 'Crema')
        self.assertContains(carrito, 'Jabón')
        self.assertContains(carrito, 'RD$ 1,600.00')
        self.assertContains(carrito, 'Iniciar sesión y continuar')

    def test_cambia_la_cantidad_y_quita_productos_y_vuelve_al_carrito(self):
        respuesta = self.client.post(ruta('carrito:actualizar', tienda=self.otra),
                                     {'producto_id': self.jabon.pk, 'cantidad': 3, 'next': self.url})
        self.assertRedirects(respuesta, self.url, fetch_redirect_response=False)
        self.assertContains(self.client.get(self.url), 'RD$ 1,900.00')
        respuesta = self.client.post(ruta('carrito:eliminar'), {'producto_id': self.crema.pk, 'next': self.url})
        self.assertRedirects(respuesta, self.url, fetch_redirect_response=False)
        carrito = self.client.get(self.url)
        self.assertNotContains(carrito, 'Crema')
        self.assertContains(carrito, 'RD$ 900.00')
