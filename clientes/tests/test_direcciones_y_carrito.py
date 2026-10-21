"""Direcciones guardadas, carrito guardado en la cuenta, recordatorio del carrito y volver a pedir."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.tests.test_modelos import crear_producto
from clientes import services
from clientes.models import CarritoGuardado, Direccion
from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from pedidos.tests.utiles import zona_de_prueba
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba

Estado = Pedido.Estado


class DireccionesTests(TestCase):
    def setUp(self):
        self.ana = entrar_como_cliente(self.client)
        self.luis = services.registrar_cliente('Luis Gil', 'luis@example.com', 'clave-segura-123')
        self.de_luis = Direccion.objects.create(usuario=self.luis, nombre='Casa', sector='Gazcue', direccion='Calle 2')

    def test_agrega_y_la_primera_queda_por_defecto(self):
        self.client.post(reverse('clientes:direcciones'), {'nombre': 'Casa', 'sector': 'Naco', 'direccion': 'Calle 1'})
        self.client.post(reverse('clientes:direcciones'), {'nombre': 'Trabajo', 'sector': 'Piantini', 'direccion': 'Av. 27'})
        casa, trabajo = services.direcciones_de(self.ana).order_by('id')
        self.assertTrue(casa.principal)
        self.assertFalse(trabajo.principal)
        self.client.post(reverse('clientes:principal_direccion', args=[trabajo.pk]))
        self.assertEqual(services.direcciones_de(self.ana).first(), trabajo)
        # Al borrar la principal, otra pasa a serlo.
        self.client.post(reverse('clientes:borrar_direccion', args=[trabajo.pk]))
        casa.refresh_from_db()
        self.assertTrue(casa.principal)

    def test_no_toca_las_direcciones_de_otro(self):
        pagina = self.client.get(reverse('clientes:direcciones'))
        self.assertNotContains(pagina, 'Gazcue')
        self.assertEqual(self.client.get(reverse('clientes:editar_direccion', args=[self.de_luis.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('clientes:borrar_direccion', args=[self.de_luis.pk])).status_code, 404)
        self.assertTrue(Direccion.objects.filter(pk=self.de_luis.pk).exists())

    def test_maximo_de_direcciones(self):
        for numero in range(Direccion.MAXIMO):
            Direccion.objects.create(usuario=self.ana, nombre=f'D{numero}', sector='Naco', direccion=f'Calle {numero}')
        respuesta = self.client.post(reverse('clientes:direcciones'), {'nombre': 'Otra', 'sector': 'X', 'direccion': 'Y'})
        self.assertEqual(services.direcciones_de(self.ana).count(), Direccion.MAXIMO)
        self.assertContains(respuesta, 'el máximo')

    def test_el_pedido_guarda_las_direcciones_nuevas_sin_repetir(self):
        producto = crear_producto(precio=Decimal('500'))
        zona = zona_de_prueba()

        def comprar(sector, direccion):
            self.client.post(ruta('carrito:agregar'), {'producto_id': producto.pk, 'cantidad': 1})
            self.client.post(ruta('pedidos:checkout'), {
                'nombre': 'Ana Pérez', 'telefono': '8095551234', 'metodo_entrega': 'envio', 'zona': zona.pk,
                'sector': sector, 'direccion': direccion, 'metodo_pago': 'transferencia', 'acepta_terminos': 'on',
            })

        comprar('Naco', 'Calle 1 #5')
        comprar('naco', 'calle 1 #5')
        comprar('Piantini', 'Av. 27')
        self.assertEqual(Pedido.objects.count(), 3)
        self.assertEqual(
            list(services.direcciones_de(self.ana).order_by('id').values_list('nombre', 'direccion')),
            [('Casa', 'Calle 1 #5'), ('Dirección 2', 'Av. 27')],
        )
        self.client.post(ruta('carrito:agregar'), {'producto_id': producto.pk, 'cantidad': 1})
        checkout = self.client.get(ruta('pedidos:checkout'))
        self.assertContains(checkout, 'Mis direcciones')
        self.assertContains(checkout, 'data-direccion="Av. 27"')
        self.assertNotContains(checkout, 'Gazcue')


class CarritoGuardadoTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), controla_stock=False)
        self.otro = crear_producto(nombre='Mesa', precio=Decimal('3000'), controla_stock=False)
        self.ana = entrar_como_cliente(self.client)

    def agregar(self, cliente, producto, cantidad=1):
        cliente.post(ruta('carrito:agregar'), {'producto_id': producto.pk, 'cantidad': cantidad})

    def test_el_carrito_se_recupera_en_otro_equipo(self):
        self.agregar(self.client, self.producto, 2)
        guardado = CarritoGuardado.objects.get(usuario=self.ana)
        self.assertEqual(guardado.datos[str(tienda_de_prueba().pk)]['items'], {str(self.producto.pk): 2})

        otro_equipo = Client()
        self.agregar(otro_equipo, self.otro)  # sin sesion
        otro_equipo.force_login(self.ana)
        pagina = otro_equipo.get(ruta('carrito:detalle'))
        self.assertEqual({linea.producto for linea in pagina.context['lineas']}, {self.producto, self.otro})
        # Lo unido queda tambien en la cuenta.
        guardado.refresh_from_db()
        self.assertEqual(len(guardado.datos[str(tienda_de_prueba().pk)]['items']), 2)

    def test_al_comprar_el_carrito_guardado_se_vacia(self):
        self.agregar(self.client, self.producto)
        self.client.post(ruta('pedidos:checkout'), {
            'nombre': 'Ana Pérez', 'telefono': '8095551234', 'metodo_entrega': 'recoger',
            'metodo_pago': 'transferencia', 'acepta_terminos': 'on',
        })
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(CarritoGuardado.objects.get(usuario=self.ana).datos, {})

    def test_el_personal_del_panel_no_guarda_carrito(self):
        vendedor = get_user_model().objects.create_user('vendedor', password='x', is_staff=True)
        self.client.force_login(vendedor)
        self.agregar(self.client, self.producto)
        self.assertFalse(CarritoGuardado.objects.filter(usuario=vendedor).exists())


class RecordatorioTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), controla_stock=False)
        self.ana = entrar_como_cliente(self.client)
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        CarritoGuardado.objects.update(actualizado=timezone.now() - timedelta(days=2))

    def test_un_recordatorio_por_cada_vez_que_lo_deja(self):
        self.assertEqual(services.recordar_carritos_abandonados(), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, [self.ana.email])
        self.assertIn('Lámpara', correo.body)
        self.assertIn(ruta('carrito:detalle'), correo.body)
        self.assertEqual(services.recordar_carritos_abandonados(), 0)

        # Si despues vuelve a tocar el carrito y lo deja otra vez, se le recuerda de nuevo.
        CarritoGuardado.objects.update(
            recordado=timezone.now() - timedelta(days=3), actualizado=timezone.now() - timedelta(days=2),
        )
        self.assertEqual(services.recordar_carritos_abandonados(), 1)

    def test_ni_muy_pronto_ni_muy_tarde(self):
        CarritoGuardado.objects.update(actualizado=timezone.now() - timedelta(hours=3))
        self.assertEqual(services.recordar_carritos_abandonados(), 0)
        CarritoGuardado.objects.update(actualizado=timezone.now() - timedelta(days=10))
        self.assertEqual(services.recordar_carritos_abandonados(), 0)

    def test_lo_que_ya_no_se_vende_no_se_recuerda(self):
        self.producto.activo = False
        self.producto.save()
        self.assertEqual(services.recordar_carritos_abandonados(), 0)
        self.assertEqual(mail.outbox, [])

    def test_el_enlace_del_correo_los_apaga(self):
        url = reverse('clientes:apagar_recordatorios', args=[services.token_recordatorios(self.ana)])
        self.client.logout()
        self.assertContains(self.client.get(url), 'Dejar de recibir recordatorios')
        self.client.post(url)
        self.ana.perfil.refresh_from_db()
        self.assertFalse(self.ana.perfil.recordatorios)
        self.assertEqual(services.recordar_carritos_abandonados(), 0)
        self.assertContains(
            self.client.post(reverse('clientes:apagar_recordatorios', args=['falso'])), 'Enlace no válido',
        )


class VolverAPedirTests(TestCase):
    def setUp(self):
        self.lampara = crear_producto(nombre='Lámpara', precio=Decimal('1000'), controla_stock=False)
        self.mesa = crear_producto(nombre='Mesa', precio=Decimal('3000'), controla_stock=False)
        entrar_como_cliente(self.client)
        for producto, cantidad in ((self.lampara, 2), (self.mesa, 1)):
            self.client.post(ruta('carrito:agregar'), {'producto_id': producto.pk, 'cantidad': cantidad})
        self.client.post(ruta('pedidos:checkout'), {
            'nombre': 'Ana Pérez', 'telefono': '8095551234', 'metodo_entrega': 'recoger',
            'metodo_pago': 'efectivo_recoger', 'acepta_terminos': 'on',
        })
        self.pedido = Pedido.objects.get()
        cambiar_estado(self.pedido, Estado.ENTREGADO)

    def test_pone_otra_vez_los_productos_en_el_carrito(self):
        self.assertContains(self.client.get(reverse('clientes:cuenta')), 'Volver a pedir')
        self.mesa.activo = False
        self.mesa.save()
        respuesta = self.client.post(reverse('pedidos:volver_a_pedir', args=[self.pedido.token]))
        self.assertRedirects(respuesta, ruta('carrito:detalle'), fetch_redirect_response=False)
        carrito = self.client.get(ruta('carrito:detalle'))
        self.assertEqual([(l.producto, l.cantidad) for l in carrito.context['lineas']], [(self.lampara, 2)])
        self.assertContains(carrito, '&quot;Mesa&quot; ya no se vende.')
