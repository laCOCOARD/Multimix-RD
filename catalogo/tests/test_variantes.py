"""Variantes de producto (talla, color, tamaño) y galeria deslizable."""
from decimal import Decimal

import tablib
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalogo import services
from catalogo.models import Disponibilidad, FotoProducto, Producto
from catalogo.resources import ProductoResource
from tiendas.tests.utiles import ruta, tienda_de_prueba

from .test_modelos import crear_producto, imagen_de_prueba


class VariantesTests(TestCase):
    def setUp(self):
        self.roja = crear_producto(
            nombre='Camiseta roja', sku='CAM-R', precio=Decimal('800'), nombre_variante='Rojo', tipo_variante='Color',
        )
        self.azul = crear_producto(
            nombre='Camiseta azul', sku='CAM-A', precio=Decimal('850'), variante_de=self.roja, nombre_variante='Azul',
        )
        self.negra = crear_producto(
            nombre='Camiseta negra', sku='CAM-N', variante_de=self.roja, nombre_variante='Negro',
            disponibilidad=Disponibilidad.AGOTADO,
        )

    def test_el_catalogo_muestra_solo_el_principal_con_sus_opciones(self):
        pagina = self.client.get(ruta('catalogo:lista'))
        self.assertEqual(list(pagina.context['pagina'].object_list), [self.roja])
        self.assertContains(pagina, '3 opciones')
        # Si el principal deja de venderse, las variantes salen sueltas.
        self.roja.activo = False
        self.roja.save()
        pagina = self.client.get(ruta('catalogo:lista'))
        self.assertCountEqual(pagina.context['pagina'].object_list, [self.azul, self.negra])

    def test_la_ficha_ofrece_las_opciones(self):
        pagina = self.client.get(self.azul.get_absolute_url())
        self.assertEqual(pagina.context['opciones'], [self.roja, self.azul, self.negra])
        self.assertContains(pagina, 'Color:')
        self.assertContains(pagina, f'href="{self.roja.get_absolute_url()}"')
        self.assertContains(pagina, 'mm-variante activa')
        self.assertContains(pagina, 'mm-variante agotada')
        # Un producto sin variantes no muestra selector.
        suelto = crear_producto(nombre='Taza', sku='TAZA')
        self.assertEqual(self.client.get(suelto.get_absolute_url()).context['opciones'], [])

    def test_cada_variante_se_compra_por_separado(self):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.azul.pk, 'cantidad': 1})
        lineas = self.client.get(ruta('carrito:detalle')).context['lineas']
        self.assertEqual([(linea.producto, linea.precio_unitario) for linea in lineas], [(self.azul, Decimal('850'))])

    def test_reglas_del_grupo(self):
        otra_tienda = crear_producto(nombre='Ajena', sku='AJ', tienda=tienda_de_prueba('Fitnes RD'))
        casos = [
            Producto(tienda=self.roja.tienda, categoria=self.roja.categoria, nombre='X', sku='X1', precio=1,
                     variante_de=self.azul, nombre_variante='Verde'),          # variante de una variante
            Producto(tienda=self.roja.tienda, categoria=self.roja.categoria, nombre='X', sku='X2', precio=1,
                     variante_de=otra_tienda, nombre_variante='Verde'),        # de otra tienda
            Producto(tienda=self.roja.tienda, categoria=self.roja.categoria, nombre='X', sku='X3', precio=1,
                     variante_de=self.roja),                                   # sin opcion
        ]
        for producto in casos:
            with self.assertRaises(ValidationError):
                producto.full_clean()
        # El principal, que ya tiene variantes, no puede volverse variante.
        self.roja.variante_de, self.roja.nombre_variante = crear_producto(sku='OTRO'), 'Rojo'
        with self.assertRaises(ValidationError):
            self.roja.full_clean()

    def test_importar_variantes_por_sku(self):
        datos = tablib.Dataset(headers=['sku', 'nombre', 'categoria', 'precio', 'variante_de', 'nombre_variante'])
        datos.append(['CAM-V', 'Camiseta verde', 'General', '800', 'cam-r', 'Verde'])
        resultado = ProductoResource(tienda=self.roja.tienda).import_data(datos, dry_run=False)
        self.assertFalse(resultado.has_errors() or resultado.has_validation_errors())
        verde = Producto.objects.get(sku='CAM-V')
        self.assertEqual((verde.variante_de, verde.nombre_variante), (self.roja, 'Verde'))
        # El SKU del principal se busca solo en la tienda que se importa.
        datos = tablib.Dataset(headers=['sku', 'nombre', 'categoria', 'precio', 'variante_de', 'nombre_variante'])
        datos.append(['FIT-V', 'Otra', 'General', '800', 'CAM-R', 'Verde'])
        ajena = ProductoResource(tienda=tienda_de_prueba('Fitnes RD')).import_data(datos, dry_run=True)
        self.assertTrue(ajena.has_errors() or ajena.has_validation_errors())

    def test_el_panel_solo_ofrece_principales_de_sus_tiendas(self):
        admin = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'clave-segura-123')
        self.client.force_login(admin)
        formulario = self.client.get(reverse('admin:catalogo_producto_change', args=[self.roja.pk])).context['adminform']
        opciones = formulario.form.fields['variante_de'].queryset
        self.assertNotIn(self.roja, opciones)
        self.assertNotIn(self.azul, opciones)


class GaleriaTests(TestCase):
    def test_todas_las_fotos_en_la_pista_deslizable(self):
        producto = crear_producto(nombre='Lámpara')
        for orden in range(3):
            FotoProducto.objects.create(producto=producto, imagen=imagen_de_prueba(tamano=(40, 40)), orden=orden)
        pagina = self.client.get(producto.get_absolute_url())
        self.assertContains(pagina, 'js-galeria-pista')
        self.assertContains(pagina, 'class="mm-galeria-foto"', count=3)
        self.assertContains(pagina, 'js-galeria-puntos')
        # La primera foto carga de inmediato; las demas, cuando se deslizan.
        self.assertContains(pagina, '(foto 2)"\n                       width="800" height="800" loading="lazy"')
        self.assertNotContains(pagina, 'alt="Lámpara"\n                       width="800" height="800" loading="lazy"')

    def test_sin_fotos_no_hay_pista(self):
        pagina = self.client.get(crear_producto(nombre='Sin foto').get_absolute_url())
        self.assertNotContains(pagina, 'js-galeria-pista')
        self.assertEqual(services.opciones_de(pagina.context['producto']), [])
