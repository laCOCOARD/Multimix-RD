"""Fase 3 del rediseño (2026-10-27): el recorrido completo de compra, el buscador del sitio y la ficha del producto.

Todo con datos de prueba: ningun pago real (la transferencia la confirma la tienda; la tarjeta no esta conectada).
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto
from core.models import ConfiguracionTienda
from pedidos.models import Pedido
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba

from .utiles import zona_de_prueba


class RecorridoDeCompraTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.lampara = crear_producto(nombre='Lámpara de mesa', precio=Decimal('1000'))
        self.mesa = crear_producto(nombre='Mesa de noche', sku='M1', precio=Decimal('2500'))
        self.zona = zona_de_prueba()
        self.cliente = entrar_como_cliente(self.client, 'ana@example.com')

    def test_de_la_ficha_a_la_confirmacion(self):
        # 1. Ficha: agrega dos lamparas y una mesa.
        self.assertContains(self.client.get(self.lampara.get_absolute_url()), 'Agregar al carrito')
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.lampara.pk, 'cantidad': 2})
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.mesa.pk, 'cantidad': 1})
        # 2. Carrito: ve los articulos, cambia la cantidad y elimina uno; el total lo calcula el servidor.
        carrito = self.client.get(ruta('carrito:detalle'))
        self.assertContains(carrito, 'Lámpara de mesa')
        self.assertContains(carrito, 'RD$ 4,500.00')
        self.client.post(ruta('carrito:actualizar'), {'producto_id': self.lampara.pk, 'cantidad': 3})
        self.client.post(ruta('carrito:eliminar'), {'producto_id': self.mesa.pk})
        carrito = self.client.get(ruta('carrito:detalle'))
        self.assertEqual([(linea.producto, linea.cantidad) for linea in carrito.context['lineas']], [(self.lampara, 3)])
        self.assertEqual(carrito.context['resumen'].subtotal, Decimal('3000'))
        # Una cantidad absurda no pasa del tope por producto.
        self.client.post(ruta('carrito:actualizar'), {'producto_id': self.lampara.pk, 'cantidad': 100000})
        self.assertLess(self.client.get(ruta('carrito:detalle')).context['lineas'][0].cantidad, 100000)
        self.client.post(ruta('carrito:actualizar'), {'producto_id': self.lampara.pk, 'cantidad': 3})

        # 3. Checkout: envio a domicilio, pago contra transferencia; un total inventado por el navegador se ignora.
        checkout = self.client.get(ruta('pedidos:checkout'))
        self.assertContains(checkout, 'Todavía no disponible')  # la tarjeta no se ofrece como si funcionara
        respuesta = self.client.post(ruta('pedidos:checkout'), {
            'nombre': 'Ana Pérez', 'telefono': '809-555-1234', 'metodo_entrega': 'envio', 'zona': self.zona.pk,
            'sector': 'Naco', 'direccion': 'Calle 1 #2', 'referencia': '', 'metodo_pago': 'transferencia',
            'referencia_transferencia': '', 'cupon': '', 'notas': '', 'sitio_web': '', 'acepta_terminos': 'on',
            'total': '1', 'subtotal': '1', 'precio': '1',
        })
        pedido = Pedido.objects.get()
        self.assertRedirects(respuesta, pedido.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(
            (pedido.subtotal, pedido.costo_envio, pedido.total, pedido.cliente, pedido.tienda),
            (Decimal('3000'), self.zona.tarifa, Decimal('3000') + self.zona.tarifa, self.cliente, self.tienda),
        )
        self.assertEqual(pedido.estado, Pedido.Estado.PENDIENTE)

        # 4. Confirmacion clara, con el numero y el total; el carrito queda vacio.
        confirmacion = self.client.get(pedido.get_absolute_url())
        self.assertContains(confirmacion, pedido.numero)
        self.assertContains(confirmacion, 'Recibimos tu pedido')
        self.assertContains(confirmacion, 'Pendiente de pago')
        self.assertContains(self.client.get(ruta('carrito:detalle')), 'Tu carrito está vacío')

        # 5. Otro cliente no ve el pedido en su cuenta.
        entrar_como_cliente(self.client, 'luis@example.com', 'Luis Gil')
        self.assertNotContains(self.client.get(reverse('clientes:cuenta')), pedido.numero)


class FichaDelProductoTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.producto = crear_producto(nombre='Lámpara de mesa', precio=Decimal('1000'), stock_almacen=2)

    def test_muestra_la_tienda_que_lo_vende_y_sus_formas_de_pago_reales(self):
        ficha = self.client.get(self.producto.get_absolute_url())
        self.assertContains(ficha, 'Vendido por')
        self.assertContains(ficha, f'href="{self.tienda.get_absolute_url()}"')
        self.assertContains(ficha, 'Formas de pago: Transferencia bancaria, Efectivo al recoger.')
        self.assertContains(ficha, 'Código (SKU)')
        # Sin cuentas la tienda no recibe transferencias: la ficha no las ofrece; sin zonas, solo retiro.
        self.tienda.cuentas.all().delete()
        ficha = self.client.get(self.producto.get_absolute_url())
        self.assertContains(ficha, 'Formas de pago: Efectivo al recoger.')
        self.assertContains(ficha, 'Por ahora solo retiro en la tienda.')
        self.assertNotContains(ficha, 'Transferencia bancaria')

    def test_sin_mensajes_de_urgencia_por_existencias(self):
        # Lleva inventario y quedan 2 (por debajo del umbral): no se dice "¡Quedan 2!".
        ficha = self.client.get(self.producto.get_absolute_url())
        self.assertNotContains(ficha, 'Quedan')
        self.assertContains(ficha, 'Disponible')
        # Nunca la cantidad de unidades (pedido del dueño el 2026-10-27), ni con la opcion vieja encendida.
        config = ConfiguracionTienda.obtener()
        config.mostrar_cantidad_exacta = True
        config.save()
        ficha = self.client.get(self.producto.get_absolute_url())
        self.assertNotContains(ficha, 'unidades')
        self.assertNotContains(ficha, 'max="2"')


class BuscadorDelSitioTests(TestCase):
    def setUp(self):
        self.multimix = tienda_de_prueba(banner_subtitulo='Salud, belleza y bienestar')
        self.fitnes = tienda_de_prueba('Rincón Fitness', prefijo='FIT', banner_subtitulo='Accesorios para entrenar')
        self.crema = crear_producto(nombre='Crema hidratante', precio=Decimal('800'))
        self.pesas = crear_producto(nombre='Pesas de 5 libras', sku='P1', precio=Decimal('2400'), tienda=self.fitnes)
        self.url = reverse('tiendas:buscar')

    def test_encuentra_tiendas_y_productos(self):
        respuesta = self.client.get(self.url, {'q': 'rincon'})
        self.assertEqual(respuesta.context['tiendas_encontradas'], [self.fitnes])
        self.assertContains(respuesta, 'Resultados para «rincon»')
        # Tambien por lo que vende (descripcion), sin tildes ni mayusculas.
        self.assertEqual(self.client.get(self.url, {'q': 'ENTRENAR'}).context['tiendas_encontradas'], [self.fitnes])
        self.assertEqual(list(self.client.get(self.url, {'q': 'crema'}).context['pagina']), [self.crema])

    def test_filtros_de_tienda_y_precio_y_limpiar(self):
        respuesta = self.client.get(self.url, {'tienda': self.fitnes.slug})
        self.assertEqual(list(respuesta.context['pagina']), [self.pesas])
        self.assertContains(respuesta, 'Limpiar filtros')
        self.assertContains(respuesta, 'Quitar el filtro de tienda Rincón Fitness')
        self.assertEqual(list(self.client.get(self.url, {'precio_max': '1000'}).context['pagina']), [self.crema])
        self.assertEqual(list(self.client.get(self.url, {'precio_min': '1000'}).context['pagina']), [self.pesas])
        # Un filtro que no vale se ignora en lugar de romper la pagina.
        respuesta = self.client.get(self.url, {'tienda': 'no-existe', 'precio_min': 'abc'})
        self.assertEqual(len(respuesta.context['pagina'].object_list), 2)
        self.assertFalse(respuesta.context['hay_filtros'])
        # Una tienda apagada no se puede elegir.
        self.fitnes.activa = False
        self.fitnes.save()
        self.assertEqual(list(self.client.get(self.url, {'tienda': self.fitnes.slug}).context['pagina']), [self.crema])

    def test_sin_resultados_lo_dice_y_sugiere(self):
        respuesta = self.client.get(self.url, {'q': 'xyzxyz'})
        self.assertContains(respuesta, 'No encontramos productos para «xyzxyz»')
        respuesta = self.client.get(self.url, {'q': 'crema', 'precio_min': '5000'})
        self.assertContains(respuesta, 'Ningún producto cumple con esos filtros.')

    def test_sugerencias_con_tiendas_y_productos(self):
        datos = self.client.get(reverse('tiendas:sugerencias'), {'q': 'fitness'}).json()
        self.assertEqual([tienda['nombre'] for tienda in datos['tiendas']], ['Rincón Fitness'])
        self.assertEqual(datos['tiendas'][0]['detalle'], 'Tienda')
        datos = self.client.get(reverse('tiendas:sugerencias'), {'q': 'pesas'}).json()
        self.assertEqual([producto['nombre'] for producto in datos['resultados']], ['Pesas de 5 libras'])
        self.assertEqual(datos['resultados'][0]['tienda'], 'Rincón Fitness')
        # Vacio o una sola letra: nada.
        self.assertEqual(self.client.get(reverse('tiendas:sugerencias'), {'q': 'c'}).json(),
                         {'resultados': [], 'tiendas': []})
