from django.core.exceptions import ValidationError
from django.test import TestCase

from catalogo.models import Categoria
from catalogo.services import categorias_de, categorias_de_portada
from tiendas.tests.utiles import ruta, tienda_de_prueba

from .test_modelos import crear_producto


class SubcategoriasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tienda = tienda_de_prueba()
        cls.belleza = Categoria.objects.create(nombre='Belleza', orden=1)
        cls.maquillaje = Categoria.objects.create(nombre='Maquillaje', padre=cls.belleza)
        cls.cabello = Categoria.objects.create(nombre='Cabello', padre=cls.belleza)
        cls.hogar = Categoria.objects.create(nombre='Hogar', orden=2)
        Categoria.objects.create(nombre='Vacía', orden=3)
        crear_producto(nombre='Labial', sku='M1', categoria=cls.maquillaje)
        crear_producto(nombre='Shampoo', sku='C1', categoria=cls.cabello)
        crear_producto(nombre='Lámpara', sku='H1', categoria=cls.hogar)

    def test_la_categoria_principal_lista_lo_de_sus_subcategorias(self):
        nombres = lambda slug: {p.nombre for p in self.client.get(ruta('catalogo:categoria', slug)).context['pagina']}
        self.assertEqual(nombres(self.belleza.slug), {'Labial', 'Shampoo'})
        self.assertEqual(nombres(self.maquillaje.slug), {'Labial'})
        self.assertEqual(nombres(self.hogar.slug), {'Lámpara'})

    def test_el_menu_trae_la_principal_con_sus_subcategorias_debajo(self):
        # Belleza no tiene productos propios: aparece porque sus subcategorias si tienen.
        self.assertEqual([c.nombre for c in categorias_de(self.tienda)], ['Belleza', 'Cabello', 'Maquillaje', 'Hogar'])
        self.assertEqual([c.nombre for c in categorias_de(tienda_de_prueba('Fitnes RD'))], [])
        self.assertEqual(len(categorias_de_portada(self.tienda)), 4)
        self.assertContains(self.client.get(ruta('catalogo:lista')), '<span class="ms-3">Maquillaje</span>')

    def test_una_subcategoria_apagada_no_aporta_productos(self):
        self.maquillaje.activa = False
        self.maquillaje.save()
        pagina = self.client.get(ruta('catalogo:categoria', self.belleza.slug))
        self.assertEqual({p.nombre for p in pagina.context['pagina']}, {'Shampoo'})

    def test_solo_dos_niveles(self):
        with self.assertRaises(ValidationError):
            Categoria(nombre='Labiales mate', padre=self.maquillaje).full_clean()
        self.belleza.padre = self.hogar
        with self.assertRaises(ValidationError):
            self.belleza.full_clean()
        self.hogar.padre = self.hogar
        with self.assertRaises(ValidationError):
            self.hogar.full_clean()
        Categoria(nombre='Cocina', padre=Categoria.objects.get(pk=self.hogar.pk)).full_clean()
