from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalogo.models import Producto
from catalogo.services import marcas_de
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba

from .test_modelos import crear_producto


class MarcaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tienda = tienda_de_prueba()
        cls.otra = tienda_de_prueba('Fitnes RD')
        cls.shampoo = crear_producto(nombre='Shampoo', sku='S1', marca='  Satinique ')
        cls.vitamina = crear_producto(nombre='Vitamina C', sku='V1', marca='Nutrilite')
        crear_producto(nombre='Proteína', sku='V2', marca='nutrilite')
        crear_producto(nombre='Sin marca', sku='X1')
        crear_producto(nombre='Oculto', sku='O1', marca='Fantasma', activo=False)
        crear_producto(nombre='Pesas', sku='P1', marca='Ajena', tienda=cls.otra)

    def test_la_marca_se_guarda_limpia_y_se_puede_buscar(self):
        self.assertEqual(self.shampoo.marca, 'Satinique')
        respuesta = self.client.get(ruta('catalogo:lista'), {'q': 'satinique'})
        self.assertEqual([p.nombre for p in respuesta.context['pagina']], ['Shampoo'])

    def test_marcas_de_la_tienda_sin_repetir_ni_cruzar(self):
        self.assertEqual(marcas_de(self.tienda), ['Nutrilite', 'Satinique'])
        self.assertEqual(marcas_de(self.otra), ['Ajena'])

    def test_filtro_por_marca_sin_importar_mayusculas(self):
        respuesta = self.client.get(ruta('catalogo:lista'), {'marca': 'NUTRILITE'})
        self.assertEqual({p.nombre for p in respuesta.context['pagina']}, {'Vitamina C', 'Proteína'})
        self.assertContains(respuesta, '<option value="Nutrilite" selected>')
        self.assertContains(respuesta, 'Limpiar filtros')

    def test_la_ficha_enlaza_a_su_marca(self):
        respuesta = self.client.get(self.vitamina.get_absolute_url())
        self.assertContains(respuesta, '?marca=Nutrilite')

    def test_cambiar_solo_la_marca_refresca_la_busqueda(self):
        self.vitamina.marca = 'Amway'
        self.vitamina.save(update_fields=['marca'])
        self.assertIn('amway', Producto.objects.get(pk=self.vitamina.pk).texto_busqueda)


class SugerenciasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.otra = tienda_de_prueba('Fitnes RD')
        cls.lampara = crear_producto(nombre='Lámpara de mesa', sku='L1', precio=Decimal('1500'))
        crear_producto(nombre='Lámpara oculta', sku='L2', activo=False)
        crear_producto(nombre='Lámpara de gimnasio', sku='L3', tienda=cls.otra)

    def nombres(self, respuesta):
        return [fila['nombre'] for fila in respuesta.json()['resultados']]

    def test_sugiere_solo_lo_de_la_tienda_y_a_la_venta(self):
        respuesta = self.client.get(ruta('catalogo:sugerencias'), {'q': 'lampara'})
        self.assertEqual(self.nombres(respuesta), ['Lámpara de mesa'])
        fila = respuesta.json()['resultados'][0]
        self.assertEqual((fila['url'], fila['precio'], fila['tienda']),
                         (self.lampara.get_absolute_url(), 'RD$ 1,500.00', ''))

    def test_el_buscador_del_sitio_sugiere_de_todas_las_tiendas(self):
        respuesta = self.client.get(reverse('tiendas:sugerencias'), {'q': 'lampara'})
        self.assertEqual(set(self.nombres(respuesta)), {'Lámpara de mesa', 'Lámpara de gimnasio'})
        self.assertEqual({fila['tienda'] for fila in respuesta.json()['resultados']}, {'Multimix RD', 'Fitnes RD'})

    def test_necesita_al_menos_dos_letras(self):
        for texto in ('', 'l', '   '):
            self.assertEqual(self.nombres(self.client.get(ruta('catalogo:sugerencias'), {'q': texto})), [])

    def test_no_sugiere_de_una_tienda_apagada(self):
        self.otra.activa = False
        self.otra.save()
        self.assertEqual(self.client.get(ruta('catalogo:sugerencias', tienda=self.otra), {'q': 'lampara'}).status_code, 404)
        respuesta = self.client.get(reverse('tiendas:sugerencias'), {'q': 'lampara'})
        self.assertEqual(self.nombres(respuesta), ['Lámpara de mesa'])

    def test_solo_get(self):
        self.assertEqual(self.client.post(ruta('catalogo:sugerencias')).status_code, 405)


class ComprarAhoraTests(TestCase):
    def test_lleva_directo_al_checkout_con_el_producto_en_el_carrito(self):
        producto = crear_producto(nombre='Taza')
        entrar_como_cliente(self.client)
        respuesta = self.client.post(ruta('carrito:agregar'), {'producto_id': producto.pk, 'cantidad': 2, 'comprar': '1'})
        self.assertRedirects(respuesta, ruta('pedidos:checkout'), fetch_redirect_response=False)
        self.assertContains(self.client.get(ruta('pedidos:checkout')), 'Taza')

    def test_si_no_se_puede_comprar_no_va_al_checkout(self):
        producto = crear_producto(nombre='Taza', stock_almacen=0)
        respuesta = self.client.post(ruta('carrito:agregar'), {'producto_id': producto.pk, 'comprar': '1'})
        self.assertRedirects(respuesta, ruta('carrito:detalle'), fetch_redirect_response=False)

    def test_la_ficha_ofrece_comprar_ahora_y_compartir(self):
        respuesta = self.client.get(crear_producto(nombre='Taza').get_absolute_url())
        self.assertContains(respuesta, 'name="comprar"')
        self.assertContains(respuesta, 'js-compartir')
