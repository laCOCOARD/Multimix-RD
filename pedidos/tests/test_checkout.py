from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.models import Producto
from catalogo.tests.test_modelos import crear_producto
from core.models import ConfiguracionTienda, CuentaBancaria
from pedidos.models import Pedido
from pedidos.whatsapp import construir_mensaje
from promociones.models import Cupon

from .utiles import zona_de_prueba


class CheckoutTests(TestCase):
    def setUp(self):
        config = ConfiguracionTienda.obtener()
        config.whatsapp = '18095550000'
        config.save()
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), stock_almacen=5)
        self.zona = zona_de_prueba()
        CuentaBancaria.objects.create(banco='Banco Popular', numero='123456789', titular='Multimix RD SRL')
        self.url = reverse('pedidos:checkout')

    def llenar_carrito(self, cantidad=2):
        self.client.post(reverse('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': cantidad})

    def datos(self, **cambios):
        datos = {
            'nombre': 'Ana Pérez', 'telefono': '(809) 555-1234', 'correo': '',
            'metodo_entrega': 'recoger', 'zona': '', 'direccion': '', 'referencia': '',
            'metodo_pago': 'transferencia', 'referencia_transferencia': '', 'cupon': '', 'notas': '',
            'sitio_web': '',
        }
        datos.update(cambios)
        return datos

    def errores(self, respuesta):
        return respuesta.context['formulario'].errors

    def test_carrito_vacio_redirige(self):
        self.assertRedirects(self.client.get(self.url), reverse('carrito:detalle'))
        self.assertRedirects(self.client.post(self.url, self.datos()), reverse('carrito:detalle'))

    def test_muestra_el_formulario_con_cuentas(self):
        self.llenar_carrito()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Banco Popular')
        self.assertContains(respuesta, 'RD$ 2,000.00')
        self.assertNotContains(respuesta, 'pago-contra_entrega')

    def test_flujo_completo_hasta_whatsapp(self):
        self.llenar_carrito(2)
        respuesta = self.client.post(self.url, self.datos(notas='Paso a las 5'))
        pedido = Pedido.objects.get()
        self.assertRedirects(
            respuesta, reverse('pedidos:confirmacion', args=[pedido.token]), fetch_redirect_response=False,
        )
        self.assertEqual(pedido.telefono, '8095551234')
        self.assertEqual(pedido.total, Decimal('2000.00'))
        self.assertEqual(pedido.estado, Pedido.Estado.PENDIENTE)
        self.assertEqual(pedido.ip, '127.0.0.1')
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_reservado, 2)

        pagina = self.client.get(respuesta.url)
        self.assertContains(pagina, pedido.numero)
        self.assertContains(pagina, 'Enviar pedido por WhatsApp')
        self.assertContains(pagina, 'Banco Popular')
        self.assertContains(pagina, 'data-abrir="1"')
        enlace = pagina.context['enlace_whatsapp']
        self.assertTrue(enlace.startswith('https://wa.me/18095550000?text='))
        self.assertEqual(parse_qs(urlparse(enlace).query)['text'], [construir_mensaje(pedido)])

        # El carrito queda vacio y WhatsApp solo se abre solo la primera vez.
        self.assertEqual(self.client.get(reverse('carrito:detalle')).context['lineas'], [])
        self.assertContains(self.client.get(respuesta.url), 'data-abrir="0"')

    def test_los_montos_enviados_por_el_navegador_se_ignoran(self):
        self.llenar_carrito(1)
        self.client.post(self.url, self.datos(total='1', subtotal='1', descuento='999', costo_envio='0', estado='pagado'))
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.total, Decimal('1000.00'))
        self.assertEqual(pedido.estado, Pedido.Estado.PENDIENTE)
        self.assertIsNone(pedido.fecha_pago)

    def test_envio_a_domicilio_suma_la_tarifa(self):
        self.llenar_carrito(1)
        self.client.post(self.url, self.datos(
            metodo_entrega='envio', zona=self.zona.pk, direccion='Calle 1 #5', referencia='Portón azul',
        ))
        pedido = Pedido.objects.get()
        self.assertEqual((pedido.costo_envio, pedido.total), (Decimal('250.00'), Decimal('1250.00')))
        self.assertEqual(pedido.zona, self.zona)

    def test_validaciones_del_servidor(self):
        self.llenar_carrito(1)
        respuesta = self.client.post(self.url, self.datos(nombre='A', telefono='555-1234', correo='malo'))
        self.assertEqual(set(self.errores(respuesta)), {'nombre', 'telefono', 'correo'})

        respuesta = self.client.post(self.url, self.datos(metodo_entrega='envio'))
        self.assertEqual(set(self.errores(respuesta)), {'zona', 'direccion'})

        respuesta = self.client.post(self.url, self.datos(
            metodo_entrega='envio', zona=self.zona.pk, direccion='Calle 1', metodo_pago='efectivo_recoger',
        ))
        self.assertEqual(set(self.errores(respuesta)), {'metodo_pago'})

        respuesta = self.client.post(self.url, self.datos(
            metodo_entrega='envio', zona=self.zona.pk, direccion='Calle 1', metodo_pago='contra_entrega',
        ))
        self.assertEqual(set(self.errores(respuesta)), {'metodo_pago'})
        self.assertEqual(Pedido.objects.count(), 0)

    def test_contra_entrega_cuando_esta_activado(self):
        config = ConfiguracionTienda.obtener()
        config.permitir_contra_entrega = True
        config.save()
        self.llenar_carrito(1)
        self.assertContains(self.client.get(self.url), 'pago-contra_entrega')
        self.client.post(self.url, self.datos(
            metodo_entrega='envio', zona=self.zona.pk, direccion='Calle 1', metodo_pago='contra_entrega',
        ))
        self.assertEqual(Pedido.objects.get().metodo_pago, Pedido.Pago.CONTRA_ENTREGA)

    def test_zona_inactiva_no_se_acepta(self):
        self.zona.activa = False
        self.zona.save()
        self.llenar_carrito(1)
        respuesta = self.client.post(self.url, self.datos(metodo_entrega='envio', zona=self.zona.pk, direccion='Calle 1'))
        self.assertIn('zona', self.errores(respuesta))

    def test_honeypot_bloquea_bots(self):
        self.llenar_carrito(1)
        respuesta = self.client.post(self.url, self.datos(sitio_web='http://spam.example'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)

    @override_settings(PEDIDOS_MAX_POR_IP=1)
    def test_limite_de_pedidos_por_ip(self):
        self.llenar_carrito(1)
        self.client.post(self.url, self.datos())
        self.llenar_carrito(1)
        respuesta = self.client.post(self.url, self.datos())
        self.assertContains(respuesta, 'varios pedidos desde tu conexión')
        self.assertEqual(Pedido.objects.count(), 1)

    def test_cupon_en_el_checkout(self):
        Cupon.objects.create(codigo='BIENVENIDO10', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('10'))
        self.llenar_carrito(2)
        respuesta = self.client.post(self.url, self.datos(cupon='falso'))
        self.assertIn('cupon', self.errores(respuesta))
        self.client.post(self.url, self.datos(cupon='bienvenido10'))
        pedido = Pedido.objects.get()
        self.assertEqual((pedido.codigo_cupon, pedido.descuento, pedido.total),
                         ('BIENVENIDO10', Decimal('200.00'), Decimal('1800.00')))

    def test_stock_cambia_antes_de_confirmar(self):
        self.llenar_carrito(4)
        Producto.objects.filter(pk=self.producto.pk).update(stock_almacen=1)
        respuesta = self.client.post(self.url, self.datos(), follow=True)
        self.assertRedirects(respuesta, reverse('carrito:detalle'))
        self.assertContains(respuesta, 'Solo quedan 1')
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(respuesta.context['lineas'][0].cantidad, 1)

    def test_totales_en_vivo(self):
        Cupon.objects.create(codigo='DIEZ', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('10'))
        self.llenar_carrito(2)
        url = reverse('pedidos:totales')
        datos = self.client.post(url, {'metodo_entrega': 'recoger'}).json()
        self.assertEqual((datos['envio'], datos['total']), ('Gratis', 'RD$ 2,000.00'))
        self.assertEqual(datos['metodos_pago'], ['transferencia', 'efectivo_recoger'])

        datos = self.client.post(url, {'metodo_entrega': 'envio', 'zona': ''}).json()
        self.assertEqual(datos['envio'], 'Elige tu zona')

        datos = self.client.post(url, {'metodo_entrega': 'envio', 'zona': self.zona.pk, 'cupon': 'diez'}).json()
        self.assertEqual(
            (datos['subtotal'], datos['descuento'], datos['envio'], datos['total'], datos['cupon']),
            ('RD$ 2,000.00', 'RD$ 200.00', 'RD$ 250.00', 'RD$ 2,050.00', 'DIEZ'),
        )
        self.assertEqual(datos['metodos_pago'], ['transferencia'])

        datos = self.client.post(url, {'metodo_entrega': 'recoger', 'cupon': 'falso'}).json()
        self.assertFalse(datos['cupon_ok'])
        self.assertEqual(datos['total'], 'RD$ 2,000.00')
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_el_cliente_solo_avisa_la_transferencia(self):
        self.llenar_carrito(1)
        self.client.post(self.url, self.datos(transferencia_realizada='on', referencia_transferencia='TRX-1'))
        pedido = Pedido.objects.get()
        self.assertTrue(pedido.transferencia_realizada)
        self.assertEqual(pedido.estado, Pedido.Estado.PENDIENTE)
        self.assertContains(self.client.get(pedido.get_absolute_url()), 'Nos avisaste que ya transferiste')

    def test_aviso_de_transferencia_desde_la_confirmacion(self):
        self.llenar_carrito(1)
        self.client.post(self.url, self.datos())
        pedido = Pedido.objects.get()
        url = reverse('pedidos:avisar_transferencia', args=[pedido.token])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {'referencia_transferencia': 'REF-7', 'estado': 'pagado'})
        pedido.refresh_from_db()
        self.assertEqual(
            (pedido.transferencia_realizada, pedido.referencia_transferencia, pedido.estado),
            (True, 'REF-7', Pedido.Estado.PENDIENTE),
        )

    def test_confirmacion_solo_por_token(self):
        self.llenar_carrito(1)
        self.client.post(self.url, self.datos())
        pedido = Pedido.objects.get()
        self.assertEqual(self.client.get(f'/pedido/{pedido.pk}/').status_code, 404)
        self.assertEqual(self.client.get('/pedido/00000000-0000-4000-8000-000000000000/').status_code, 404)
        self.assertEqual(self.client.get(pedido.get_absolute_url()).status_code, 200)

    def test_los_datos_del_cliente_se_escapan(self):
        self.llenar_carrito(1)
        self.client.post(self.url, self.datos(nombre='<script>alert(1)</script>', notas='<b>hola</b>'))
        pagina = self.client.get(Pedido.objects.get().get_absolute_url())
        self.assertNotContains(pagina, '<script>alert(1)</script>')
        self.assertContains(pagina, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(pagina, '<b>hola</b>')
