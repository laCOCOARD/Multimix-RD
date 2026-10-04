from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from catalogo.models import Producto
from catalogo.tests.test_modelos import crear_producto
from promociones.models import Cupon

FETCH = {'HTTP_X_REQUESTED_WITH': 'fetch'}


class CarritoVistasTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), stock_almacen=5)

    def agregar(self, cantidad=1, **extra):
        return self.client.post(
            reverse('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': cantidad}, **extra,
        )

    def test_agregar_sin_javascript_redirige_con_mensaje(self):
        respuesta = self.agregar(2)
        self.assertRedirects(respuesta, reverse('carrito:detalle'), fetch_redirect_response=False)
        pagina = self.client.get(reverse('carrito:detalle'))
        self.assertContains(pagina, 'se agregó al carrito')
        self.assertContains(pagina, 'RD$ 2,000.00')
        self.assertEqual(pagina.context['carrito_cantidad'], 2)

    def test_next_externo_se_ignora(self):
        respuesta = self.client.post(reverse('carrito:agregar'), {
            'producto_id': self.producto.pk, 'cantidad': 1, 'next': 'https://malicioso.example/',
        })
        self.assertRedirects(respuesta, reverse('carrito:detalle'))

    def test_agregar_con_fetch_devuelve_json(self):
        datos = self.agregar(2, **FETCH).json()
        self.assertTrue(datos['ok'])
        self.assertEqual(datos['cantidad_total'], 2)
        self.assertEqual(datos['total'], 'RD$ 2,000.00')

    def test_agregar_mas_de_lo_disponible_avisa(self):
        datos = self.agregar(9, **FETCH).json()
        self.assertEqual(datos['cantidad_total'], 5)
        self.assertIn('Solo hay 5', datos['mensaje'])

    def test_agregar_agotado_falla(self):
        Producto.objects.filter(pk=self.producto.pk).update(stock_almacen=0)
        respuesta = self.agregar(1, **FETCH)
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['ok'])

    def test_actualizar_y_eliminar_con_fetch(self):
        self.agregar(1)
        datos = self.client.post(
            reverse('carrito:actualizar'), {'producto_id': self.producto.pk, 'cantidad': 4}, **FETCH,
        ).json()
        self.assertEqual(datos['lineas'][str(self.producto.pk)], {'cantidad': 4, 'subtotal': 'RD$ 4,000.00'})
        datos = self.client.post(reverse('carrito:eliminar'), {'producto_id': self.producto.pk}, **FETCH).json()
        self.assertTrue(datos['vacio'])

    def test_actualizar_no_agrega_productos_ajenos_al_carrito(self):
        respuesta = self.client.post(
            reverse('carrito:actualizar'), {'producto_id': self.producto.pk, 'cantidad': 2}, **FETCH,
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['cantidad_total'], 0)

    def test_el_carrito_se_ajusta_si_cambio_el_stock(self):
        self.agregar(4)
        Producto.objects.filter(pk=self.producto.pk).update(stock_almacen=2)
        pagina = self.client.get(reverse('carrito:detalle'))
        self.assertContains(pagina, 'Solo quedan 2')
        self.assertEqual(pagina.context['lineas'][0].cantidad, 2)

    def test_cupon_aplicar_y_quitar(self):
        Cupon.objects.create(codigo='DIEZ', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('10'))
        self.agregar(2)
        self.client.post(reverse('carrito:cupon_aplicar'), {'codigo': 'nada'})
        self.assertContains(self.client.get(reverse('carrito:detalle')), 'no existe o no está activo')
        self.client.post(reverse('carrito:cupon_aplicar'), {'codigo': 'diez'})
        pagina = self.client.get(reverse('carrito:detalle'))
        self.assertContains(pagina, 'Cupón DIEZ aplicado.')
        self.assertEqual(pagina.context['resumen'].total, Decimal('1800.00'))
        self.client.post(reverse('carrito:cupon_quitar'))
        self.assertEqual(self.client.get(reverse('carrito:detalle')).context['resumen'].total, Decimal('2000.00'))

    def test_exige_csrf_y_post(self):
        estricto = Client(enforce_csrf_checks=True)
        respuesta = estricto.post(reverse('carrito:agregar'), {'producto_id': self.producto.pk})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.client.get(reverse('carrito:agregar')).status_code, 405)
