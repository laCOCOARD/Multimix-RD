from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto
from clientes.models import Favorito
from clientes.services import registrar_cliente
from opiniones import services
from opiniones.models import Resena
from pedidos.models import Pedido
from pedidos.services import cambiar_estado, crear_pedido
from pedidos.tests.utiles import carrito_con, datos_pedido
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import ruta, tienda_de_prueba

CLAVE = 'clave-segura-123'
COMENTARIO = 'Muy buena calidad y llegó a tiempo.'


class ResenaTests(TestCase):
    def setUp(self):
        self.ana = registrar_cliente('Ana Pérez', 'ana@example.com', CLAVE)
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))
        self.url = ruta('catalogo:opinar', self.producto.slug)
        self.client.force_login(self.ana)

    def recibir(self, usuario):
        pedido = crear_pedido(carrito_con((self.producto, 1)), datos_pedido(), cliente=usuario)
        cambiar_estado(pedido, Pedido.Estado.PAGADO)
        cambiar_estado(pedido, Pedido.Estado.ENTREGADO)

    def test_la_resena_queda_por_revisar_y_no_se_publica_sola(self):
        respuesta = self.client.post(self.url, {'estrellas': '5', 'comentario': COMENTARIO}, follow=True)
        self.assertContains(respuesta, 'Gracias por tu opinión')
        resena = Resena.objects.get()
        self.assertEqual((resena.estado, resena.estrellas, resena.tienda, resena.compra_verificada),
                         (Resena.Estado.PENDIENTE, 5, self.producto.tienda, False))
        self.client.logout()
        pagina = self.client.get(self.producto.get_absolute_url())
        self.assertNotContains(pagina, COMENTARIO)
        self.assertContains(pagina, 'todavía no tiene opiniones publicadas')
        self.assertEqual(services.resumen(self.producto), {'total': 0, 'promedio': None})

    def test_publicada_se_ve_con_su_promedio_y_solo_el_primer_nombre(self):
        luis = registrar_cliente('Luis Gil', 'luis@example.com', CLAVE)
        services.guardar_resena(self.ana, self.producto, 5, COMENTARIO)
        services.guardar_resena(luis, self.producto, 4, 'Buen producto, aunque tardó un poco.')
        Resena.objects.update(estado=Resena.Estado.APROBADA)
        self.client.logout()
        pagina = self.client.get(self.producto.get_absolute_url())
        self.assertContains(pagina, COMENTARIO)
        self.assertContains(pagina, '<strong class="ms-2">Ana</strong>')
        self.assertNotContains(pagina, 'Pérez')
        self.assertNotContains(pagina, 'ana@example.com')
        self.assertEqual(services.resumen(self.producto), {'total': 2, 'promedio': 4.5})
        self.assertContains(pagina, '4,5 · 2 opiniones')

    def test_compra_verificada_solo_si_lo_recibio_con_su_cuenta(self):
        self.recibir(self.ana)
        self.assertTrue(services.guardar_resena(self.ana, self.producto, 5, COMENTARIO).compra_verificada)
        luis = registrar_cliente('Luis Gil', 'luis@example.com', CLAVE)
        crear_pedido(carrito_con((self.producto, 1)), datos_pedido(correo='luis@example.com'))  # invitado, sin entregar
        self.assertFalse(services.guardar_resena(luis, self.producto, 5, COMENTARIO).compra_verificada)

    def test_una_por_cliente_y_al_cambiarla_vuelve_a_revision(self):
        services.guardar_resena(self.ana, self.producto, 5, COMENTARIO)
        Resena.objects.update(estado=Resena.Estado.APROBADA)
        self.client.post(self.url, {'estrellas': '2', 'comentario': 'Dejó de funcionar a la semana.'})
        resena = Resena.objects.get()
        self.assertEqual((resena.estrellas, resena.estado), (2, Resena.Estado.PENDIENTE))

    def test_validaciones_y_sesion_obligatoria(self):
        for datos in ({'estrellas': '6', 'comentario': COMENTARIO}, {'estrellas': '5', 'comentario': 'corto'}, {}):
            self.client.post(self.url, datos)
        self.assertFalse(Resena.objects.exists())
        self.client.logout()
        respuesta = self.client.post(self.url, {'estrellas': '5', 'comentario': COMENTARIO})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('clientes:entrar'), respuesta.url)
        self.assertFalse(Resena.objects.exists())
        self.assertContains(self.client.get(self.producto.get_absolute_url()), 'Inicia sesión para opinar')

    def test_el_comentario_se_muestra_como_texto(self):
        services.guardar_resena(self.ana, self.producto, 5, '<script>alert(1)</script> excelente')
        Resena.objects.update(estado=Resena.Estado.APROBADA)
        pagina = self.client.get(self.producto.get_absolute_url())
        self.assertNotContains(pagina, '<script>alert(1)</script>')
        self.assertContains(pagina, '&lt;script&gt;alert(1)&lt;/script&gt;')


class ModeracionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_superuser('admin', 'admin@example.com', CLAVE)
        cls.propia = tienda_de_prueba()
        cls.ajena = tienda_de_prueba('Fitnes RD')
        cls.vendedor = Usuario.objects.create_user('vendedor', password=CLAVE)
        cls.propia.usuarios.add(cls.vendedor)
        dar_acceso_al_panel([cls.vendedor])
        ana = registrar_cliente('Ana Pérez', 'ana@example.com', CLAVE)
        cls.propia_resena = services.guardar_resena(ana, crear_producto(sku='L1'), 1, 'No me gustó para nada el producto.')
        cls.ajena_resena = services.guardar_resena(ana, crear_producto(sku='P1', tienda=cls.ajena), 5, COMENTARIO)
        cls.lista = reverse('admin:opiniones_resena_changelist')

    def test_la_tienda_ve_las_suyas_pero_no_puede_esconder_una_mala(self):
        self.client.force_login(self.vendedor)
        self.assertEqual(list(self.client.get(self.lista).context['cl'].queryset), [self.propia_resena])
        self.client.post(self.lista, {'action': 'rechazar', '_selected_action': [self.propia_resena.pk]})
        self.client.post(self.lista, {'action': 'publicar', '_selected_action': [self.propia_resena.pk]})
        self.propia_resena.refresh_from_db()
        self.assertEqual(self.propia_resena.estado, Resena.Estado.PENDIENTE)

    def test_el_administrador_publica_y_rechaza(self):
        self.client.force_login(self.admin)
        self.client.post(self.lista, {'action': 'publicar', '_selected_action': [self.propia_resena.pk]})
        self.client.post(self.lista, {'action': 'rechazar', '_selected_action': [self.ajena_resena.pk]})
        self.propia_resena.refresh_from_db()
        self.ajena_resena.refresh_from_db()
        self.assertEqual((self.propia_resena.estado, self.ajena_resena.estado), (Resena.Estado.APROBADA, Resena.Estado.RECHAZADA))
        self.assertEqual(self.client.get(reverse('admin:opiniones_resena_add')).status_code, 403)


class FavoritosTests(TestCase):
    def setUp(self):
        self.ana = registrar_cliente('Ana Pérez', 'ana@example.com', CLAVE)
        self.luis = registrar_cliente('Luis Gil', 'luis@example.com', CLAVE)
        self.producto = crear_producto(nombre='Lámpara')
        self.url = reverse('clientes:alternar_favorito', args=[self.producto.pk])
        self.client.force_login(self.ana)

    def test_guarda_quita_y_cada_cliente_ve_los_suyos(self):
        respuesta = self.client.post(self.url, {'next': self.producto.get_absolute_url()})
        self.assertRedirects(respuesta, self.producto.get_absolute_url(), fetch_redirect_response=False)
        self.assertContains(self.client.get(self.producto.get_absolute_url()), 'Quitar de favoritos')
        self.assertContains(self.client.get(reverse('clientes:favoritos')), 'Lámpara')

        self.client.force_login(self.luis)
        self.assertEqual(list(self.client.get(reverse('clientes:favoritos')).context['productos']), [])
        self.assertContains(self.client.get(self.producto.get_absolute_url()), 'Guardar en favoritos')

        self.client.force_login(self.ana)
        self.client.post(self.url)
        self.assertFalse(Favorito.objects.exists())

    def test_un_producto_que_deja_de_venderse_sale_de_la_lista(self):
        self.client.post(self.url)
        self.producto.activo = False
        self.producto.save()
        self.assertEqual(list(self.client.get(reverse('clientes:favoritos')).context['productos']), [])
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_sin_sesion_pide_entrar(self):
        self.client.logout()
        self.assertIn(reverse('clientes:entrar'), self.client.post(self.url).url)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertFalse(Favorito.objects.exists())

    def test_el_corazon_de_las_tarjetas(self):
        """En cualquier listado cada tarjeta lleva su corazon, lleno si el cliente ya lo guardo."""
        portada = self.client.get(reverse('tiendas:buscar'))
        self.assertContains(portada, f'action="{self.url}"')
        self.assertContains(portada, 'aria-pressed="false"')
        # tienda.js lo cambia sin recargar: la respuesta es JSON y no deja el mensaje para la pagina siguiente.
        respuesta = self.client.post(self.url, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(respuesta.json(), {
            'ok': True, 'favorito': True, 'mensaje': 'Guardamos "Lámpara" en tus favoritos.',
        })
        portada = self.client.get(reverse('tiendas:buscar'))
        self.assertContains(portada, 'aria-pressed="true"')
        self.assertNotContains(portada, 'Guardamos')
        self.assertFalse(self.client.post(self.url, headers={'X-Requested-With': 'fetch'}).json()['favorito'])
        # Sin sesion, el corazon lleva a entrar y vuelve a la pagina.
        self.client.logout()
        portada = self.client.get(reverse('tiendas:buscar'))
        self.assertContains(portada, f'{reverse("clientes:entrar")}?next={reverse("tiendas:buscar")}')
        self.assertNotContains(portada, f'action="{self.url}"')
