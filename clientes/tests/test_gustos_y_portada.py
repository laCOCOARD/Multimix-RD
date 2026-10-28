"""Ajustes del dueño del 2026-10-27/28: gustos del cliente al crear la cuenta, promociones segun lo que busca o le
gusta, menu de las 3 barras en botones, portada sin "Descubre productos" ni "Compra con confianza", y nada de
cantidades a la vista del cliente."""
import re
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria
from catalogo.tests.test_modelos import crear_producto
from clientes.models import Perfil
from core.models import PaginaInformativa
from pedidos.models import Pedido
from pedidos.tests.utiles import zona_de_prueba
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba

CLAVE = 'clave-segura-123'


class GustosTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.belleza = Categoria.objects.create(nombre='Belleza')
        self.hogar = Categoria.objects.create(nombre='Hogar')
        self.crema = crear_producto(nombre='Crema', sku='C1', categoria=self.belleza, precio=Decimal('800'))
        self.olla = crear_producto(nombre='Olla', sku='O1', categoria=self.hogar, precio=Decimal('2500'))

    def registrar(self, siguiente=''):
        datos = {'nombre': 'Ana Pérez', 'correo': 'ana@example.com', 'telefono': '809-555-1234', 'clave': CLAVE,
                 'clave_repetida': CLAVE, 'sitio_web': ''}
        url = reverse('clientes:registro') + (f'?next={siguiente}' if siguiente else '')
        return self.client.post(url, datos)

    def test_se_pregunta_una_sola_vez_al_crear_la_cuenta(self):
        respuesta = self.registrar(siguiente='/buscar/')
        self.assertRedirects(respuesta, f"{reverse('clientes:gustos')}?next=%2Fbuscar%2F", fetch_redirect_response=False)
        pagina = self.client.get(respuesta.url)
        self.assertContains(pagina, 'Cuéntanos qué te gusta')
        for pregunta in ('¿Qué te gusta comprar?', '¿Qué buscas más seguido?', '¿Cuánto sueles gastar en una compra?',
                         '¿Cómo prefieres recibir tus compras?'):
            self.assertContains(pagina, pregunta)
        self.assertContains(pagina, 'Ahora no')
        # "Ahora no": sigue a donde iba y no se le vuelve a preguntar.
        self.assertRedirects(self.client.post(reverse('clientes:gustos'), {'omitir': '1', 'next': '/buscar/'}), '/buscar/',
                             fetch_redirect_response=False)
        perfil = Perfil.objects.get(usuario__username='ana@example.com')
        self.assertEqual((perfil.preguntar_gustos, perfil.gustos), (False, {}))
        # Desde "Mi cuenta" se pueden contestar despues.
        self.assertContains(self.client.get(reverse('clientes:cuenta')), reverse('clientes:gustos'))
        self.assertNotContains(self.client.get(reverse('clientes:gustos')), 'Ahora no')

    def test_las_respuestas_ordenan_buscador_promociones_y_entrega(self):
        self.registrar()
        self.client.post(reverse('clientes:gustos'), {
            'categorias': [str(self.hogar.pk)], 'busca': 'ofertas', 'presupuesto': '1000_3000', 'entrega': 'envio',
        })
        perfil = Perfil.objects.get(usuario__username='ana@example.com')
        self.assertEqual(perfil.gustos, {'categorias': [self.hogar.pk], 'busca': 'ofertas', 'presupuesto': '1000_3000',
                                         'entrega': 'envio'})
        # Buscador sin orden elegido: lo de sus categorias primero (la olla es mas vieja que la crema).
        self.assertEqual(list(self.client.get(reverse('tiendas:buscar')).context['pagina'])[0], self.olla)
        # Con un orden elegido manda ese orden.
        por_precio = list(self.client.get(reverse('tiendas:buscar'), {'orden': 'precio_asc'}).context['pagina'])
        self.assertEqual(por_precio[0], self.crema)
        # Promociones: las dos en oferta; la olla coincide en categoria y presupuesto.
        for producto in (self.crema, self.olla):
            producto.precio_oferta = producto.precio * Decimal('0.9')
            producto.save()
        portada = self.client.get('/')
        self.assertEqual(portada.context['promociones'][0].titulo, 'Olla')
        self.assertTrue(portada.context['promociones_personalizadas'])
        self.assertContains(portada, 'Elegidas para ti')
        self.assertEqual(portada.context['categorias'][0], self.hogar)
        # Checkout: a domicilio marcado, porque la tienda tiene zonas.
        zona_de_prueba()
        Perfil.objects.filter(usuario__username='ana@example.com').update(correo_verificado=True)
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.crema.pk, 'cantidad': 1})
        checkout = self.client.get(ruta('pedidos:checkout'))
        self.assertEqual(checkout.context['formulario'].initial['metodo_entrega'], Pedido.Entrega.ENVIO)
        # Borrar las respuestas: ya no se usan.
        self.client.post(reverse('clientes:gustos'), {'borrar': '1'})
        self.assertEqual(Perfil.objects.get(usuario__username='ana@example.com').gustos, {})

    def test_la_politica_de_privacidad_lo_explica(self):
        self.assertIn('preguntas sobre tus gustos', PaginaInformativa.objects.get(slug='privacidad').contenido)


class PortadaYMenuTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.belleza = Categoria.objects.create(nombre='Belleza')
        self.hogar = Categoria.objects.create(nombre='Hogar')
        self.crema = crear_producto(nombre='Crema hidratante', sku='C1', categoria=self.belleza, precio=Decimal('800'))
        self.olla = crear_producto(nombre='Olla de presión', sku='O1', categoria=self.hogar, precio=Decimal('2500'))
        for producto in (self.crema, self.olla):
            producto.precio_oferta = producto.precio * Decimal('0.8')
            producto.save()

    def test_las_promociones_rotan_segun_lo_que_busca(self):
        portada = self.client.get('/')
        self.assertEqual(len(portada.context['promociones']), 2)
        self.assertContains(portada, 'js-promos')
        self.assertFalse(portada.context['promociones_personalizadas'])
        primera = portada.context['promociones'][0].titulo
        otra = 'Olla de presión' if primera == 'Crema hidratante' else 'Crema hidratante'
        palabra = 'olla' if otra == 'Olla de presión' else 'crema'
        self.client.get(reverse('tiendas:buscar'), {'q': palabra})
        portada = self.client.get('/')
        self.assertEqual(portada.context['promociones'][0].titulo, otra)
        self.assertTrue(portada.context['promociones_personalizadas'])

    def test_portada_sin_secciones_quitadas_y_sin_cantidades(self):
        portada = self.client.get('/')
        for quitado in ('Descubre productos', 'Compra con confianza', 'Promociones de nuestras tiendas',
                        'Tu compra, protegida', 'mm-categoria-total'):
            self.assertNotContains(portada, quitado)
        # Ninguna cifra de productos ("4 productos", "1 producto").
        self.assertIsNone(re.search(r'\d+\s+productos?', portada.content.decode()))

    def test_menu_en_botones(self):
        menu = self.client.get('/')
        for seccion in ('menu-comprar', 'menu-cuenta', 'menu-ayuda'):
            self.assertContains(menu, f'data-bs-target="#{seccion}"')
            self.assertContains(menu, f'id="{seccion}" data-bs-parent="#menu-secciones"')
        self.assertContains(menu, 'mm-menu-vender')
        entrar_como_cliente(self.client)
        self.assertContains(self.client.get('/'), 'Cerrar sesión')
