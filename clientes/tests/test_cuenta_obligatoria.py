from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto
from pedidos.tests.utiles import pedido_de_prueba
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba


@override_settings(CUENTA_OBLIGATORIA=True)
class CuentaObligatoriaTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))

    def test_sin_sesion_todo_lleva_a_entrar(self):
        entrar = reverse('clientes:entrar')
        for url in (reverse('tiendas:portada'), self.tienda.get_absolute_url(), self.producto.get_absolute_url(),
                    ruta('catalogo:lista'), ruta('carrito:detalle'), ruta('pedidos:checkout'), reverse('tiendas:buscar')):
            self.assertRedirects(self.client.get(url), f'{entrar}?next={url}', fetch_redirect_response=False, msg_prefix=url)

    def test_lo_necesario_para_entrar_abre_sin_sesion(self):
        for url in (reverse('clientes:entrar'), reverse('clientes:registro'), reverse('clientes:recuperar'),
                    reverse('core:terminos'), reverse('core:pagina', args=['privacidad']), reverse('core:robots'),
                    reverse('core:salud'), reverse('sitemap'), reverse('admin:login')):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_la_pagina_de_entrar_no_ofrece_el_menu_de_la_tienda(self):
        pagina = self.client.get(reverse('clientes:entrar'))
        self.assertContains(pagina, 'Entra para comprar')
        self.assertNotContains(pagina, 'Todos los productos')
        self.assertContains(self.client.get(reverse('clientes:registro')), 'política de privacidad')

    def test_el_enlace_privado_de_un_pedido_abre_sin_sesion(self):
        pedido = pedido_de_prueba(self.producto, 1)
        self.assertContains(self.client.get(pedido.get_absolute_url()), pedido.numero)

    def test_con_sesion_se_navega_y_al_salir_vuelve_a_entrar(self):
        entrar_como_cliente(self.client)
        self.assertContains(self.client.get(reverse('tiendas:portada')), 'Todos los productos')
        self.assertContains(self.client.get(self.producto.get_absolute_url()), 'Lámpara')
        self.assertRedirects(self.client.post(reverse('clientes:salir')), reverse('clientes:entrar'))
