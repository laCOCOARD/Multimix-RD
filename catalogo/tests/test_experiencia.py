from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo import services
from catalogo.models import Categoria
from opiniones.models import Resena
from tiendas.tests.utiles import entrar_como_cliente, ruta, tienda_de_prueba

from .test_modelos import crear_producto


class NavegarSinCuentaTests(TestCase):
    """Como en las grandes tiendas: se mira y se arma el carrito sin cuenta; la cuenta se pide al pagar."""

    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))

    def test_se_navega_sin_cuenta_y_la_cuenta_se_pide_al_pagar(self):
        for url in ('/', reverse('tiendas:buscar'), self.tienda.get_absolute_url(), self.producto.get_absolute_url()):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 2})
        checkout = ruta('pedidos:checkout')
        self.assertContains(self.client.get(ruta('carrito:detalle')), 'Iniciar sesión y continuar')

        respuesta = self.client.get(checkout)
        entrar = f"{reverse('clientes:entrar')}?next={checkout}"
        self.assertRedirects(respuesta, entrar, fetch_redirect_response=False)
        self.assertContains(self.client.get(entrar), 'Tu carrito te espera')

        # Al entrar el carrito sigue ahi y llega directo al checkout.
        get_user_model().objects.create_user('ana@example.com', 'ana@example.com', 'clave-segura-123')
        respuesta = self.client.post(entrar, {'username': 'ana@example.com', 'password': 'clave-segura-123', 'next': checkout})
        self.assertRedirects(respuesta, checkout, fetch_redirect_response=False)
        self.assertContains(self.client.get(checkout), 'Lámpara')


class FichaDeProductoTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        self.lampara = crear_producto(nombre='Lámpara', sku='L1')
        self.mesa = crear_producto(nombre='Mesa de noche', sku='M1')

    def test_recuerda_los_vistos_recientemente_de_la_misma_tienda(self):
        otra = tienda_de_prueba('Fitnes RD')
        pesas = crear_producto(nombre='Pesas', sku='P1', tienda=otra)
        self.client.get(pesas.get_absolute_url())
        self.client.get(self.lampara.get_absolute_url())
        pagina = self.client.get(self.mesa.get_absolute_url())
        # Dentro de una tienda solo salen los suyos: su boton agrega al carrito de esa tienda.
        self.assertEqual(pagina.context['vistos'], [self.lampara])
        # En la portada del sitio salen todos, el mas reciente primero.
        self.assertEqual(self.client.get('/').context['vistos'], [self.mesa, self.lampara, pesas])

    def test_cuenta_regresiva_solo_si_la_oferta_termina_pronto(self):
        ahora = timezone.now()
        self.lampara.precio_oferta = Decimal('50')
        self.lampara.oferta_fin = ahora + timedelta(days=2)
        self.lampara.save()
        self.assertContains(self.client.get(self.lampara.get_absolute_url()), 'La oferta termina')
        self.lampara.oferta_fin = ahora + timedelta(days=30)
        self.lampara.save()
        self.assertNotContains(self.client.get(self.lampara.get_absolute_url()), 'La oferta termina')

    def test_las_tarjetas_muestran_las_estrellas_de_las_resenas_publicadas(self):
        usuarios = [entrar_como_cliente(self.client, f'c{n}@example.com') for n in range(3)]
        for usuario, estrellas, estado in zip(usuarios, (5, 4, 1), ('aprobada', 'aprobada', 'pendiente')):
            Resena.objects.create(tienda=self.tienda, producto=self.lampara, usuario=usuario, estrellas=estrellas,
                                  comentario='Muy buena lámpara.', estado=estado)
        producto = services.filtrar_catalogo({}, tienda=self.tienda).get(pk=self.lampara.pk)
        # La pendiente no cuenta.
        self.assertEqual((producto.valoracion_promedio, producto.valoracion_total), (4.5, 2))
        self.assertContains(self.client.get(ruta('catalogo:lista')), '4.5 <span>(2)</span>', html=False)


class SugerenciasTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()
        hogar = Categoria.objects.create(nombre='Hogar')
        self.lampara = crear_producto(nombre='Lámpara', sku='L1', categoria=hogar)
        self.mesa = crear_producto(nombre='Mesa', sku='M1', categoria=hogar)
        self.agotado = crear_producto(nombre='Silla', sku='S1', categoria=hogar, stock_almacen=0)

    def test_el_carrito_sugiere_de_la_misma_categoria_sin_repetir_ni_agotados(self):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.lampara.pk, 'cantidad': 1})
        pagina = self.client.get(ruta('carrito:detalle'))
        self.assertEqual(pagina.context['sugeridos'], [self.mesa])
        self.assertContains(pagina, 'Completa tu pedido')

    def test_una_busqueda_sin_resultados_sugiere_productos(self):
        pagina = self.client.get(reverse('tiendas:buscar'), {'q': 'xyz-no-existe'})
        self.assertContains(pagina, 'Quizás te interese')
        self.assertTrue(pagina.context['sugeridos'])
        self.assertEqual(self.client.get(reverse('tiendas:buscar'), {'q': 'lampara'}).context['sugeridos'], [])

    def test_la_portada_lleva_los_datos_del_sitio_para_google(self):
        self.assertContains(self.client.get('/'), '"@type": "SearchAction"')
        self.assertContains(self.client.get(self.lampara.get_absolute_url()), '"@type": "BreadcrumbList"')
