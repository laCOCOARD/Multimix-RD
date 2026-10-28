"""Lo que ve el cliente: el directorio, y que cada tienda tenga su catalogo, su carrito y sus pedidos aparte."""
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.tests.test_modelos import crear_producto
from core.models import CuentaDelSitio
from pedidos.models import Pedido
from pedidos.tests.utiles import cupon_de_prueba, zona_de_prueba
from tiendas.models import Tienda

from .utiles import entrar_como_cliente, ruta, tienda_de_prueba

FETCH = {'HTTP_X_REQUESTED_WITH': 'fetch'}


class DosTiendas(TestCase):
    """Dos tiendas con su producto, su zona, su cupon y su cuenta. `multimix` es la que ya existia."""

    @classmethod
    def setUpTestData(cls):
        cls.multimix = tienda_de_prueba(whatsapp='18095550000')
        cls.fitnes = tienda_de_prueba('Fitnes RD', whatsapp='18295559999', banner_subtitulo='Todo para entrenar.')
        cls.lampara = crear_producto(nombre='Lámpara', sku='L1', precio=Decimal('1000'))
        cls.pesas = crear_producto(nombre='Pesas rusas', sku='P1', precio=Decimal('2500'), tienda=cls.fitnes)
        cls.zona_multimix = zona_de_prueba('Santo Domingo', '250')
        cls.zona_fitnes = zona_de_prueba('Santiago', '150', tienda=cls.fitnes)
        cupon_de_prueba('MULTI10')
        cupon_de_prueba('FIT10', tienda=cls.fitnes)
        CuentaDelSitio.objects.create(banco='Banco Popular', numero='111', titular='Multimix')

    def setUp(self):
        entrar_como_cliente(self.client)

    def agregar(self, producto, tienda, cantidad=1, **extra):
        return self.client.post(
            ruta('carrito:agregar', tienda=tienda), {'producto_id': producto.pk, 'cantidad': cantidad}, **extra,
        )

    def pedir(self, tienda, **cambios):
        datos = {
            'nombre': 'Ana Pérez', 'telefono': '809-555-1234', 'metodo_entrega': 'recoger',
            'zona': '', 'direccion': '', 'referencia': '', 'metodo_pago': 'transferencia',
            'referencia_transferencia': '', 'cupon': '', 'notas': '', 'sitio_web': '', 'acepta_terminos': 'on',
        }
        datos.update(cambios)
        return self.client.post(ruta('pedidos:checkout', tienda=tienda), datos)


class DirectorioTests(DosTiendas):
    def test_la_portada_lista_las_tiendas_activas(self):
        Tienda.objects.create(nombre='En preparación', activa=False)
        respuesta = self.client.get('/')
        self.assertEqual(list(respuesta.context['tiendas']), [self.fitnes, self.multimix])
        self.assertContains(respuesta, 'href="/tienda/fitnes-rd/"')
        self.assertContains(respuesta, 'Todo para entrenar.')
        self.assertNotContains(respuesta, 'En preparación')
        # En el sitio no hay carrito: se compra dentro de cada tienda.
        self.assertNotContains(respuesta, 'js-contador-carrito')

    def test_la_portada_muestra_productos_de_todas_las_tiendas_con_su_vendedor(self):
        # Pedido del dueño el 2026-10-25: se compra sin conocer al vendedor, pero cada producto dice de que tienda es.
        # Desde el 2026-10-27 no hay "Descubre productos": salen en ofertas y en las promociones.
        for producto in (self.lampara, self.pesas):
            producto.precio_oferta = producto.precio * Decimal('0.8')
            producto.save()
        portada = self.client.get('/')
        self.assertNotContains(portada, 'Descubre productos')
        self.assertEqual({p.nombre for p in portada.context['ofertas']}, {'Lámpara', 'Pesas rusas'})
        self.assertContains(portada, 'Vendido por')
        self.assertContains(portada, f'<a href="{self.fitnes.get_absolute_url()}">Fitnes RD</a>', html=True)
        # Cada tarjeta compra en el carrito de su propia tienda.
        self.assertContains(portada, ruta('carrito:agregar', tienda=self.fitnes))
        self.assertContains(portada, ruta('carrito:agregar', tienda=self.multimix))
        self.assertContains(portada, 'data-tienda="Fitnes RD"')

    def test_la_portada_solo_ofrece_lo_que_se_puede_comprar_de_tiendas_activas(self):
        from catalogo.models import Categoria, Producto

        apagada = Tienda.objects.create(nombre='En preparación', activa=False)
        crear_producto(nombre='Producto de tienda apagada', sku='X1', tienda=apagada)
        oculta = Categoria.objects.create(nombre='Oculta', activa=False)
        crear_producto(nombre='Producto de categoría apagada', sku='X2', categoria=oculta)
        crear_producto(nombre='Producto inactivo', sku='X3', activo=False)
        crear_producto(nombre='Producto agotado', sku='X4', disponibilidad=Producto.Disponibilidad.AGOTADO)
        # Todos en oferta: si alguno se colara, saldria en ofertas o en las promociones.
        Producto.objects.update(precio_oferta=Decimal('500'))
        portada = self.client.get('/')
        self.assertEqual({p.nombre for p in portada.context['ofertas']}, {'Lámpara', 'Pesas rusas'})
        self.assertEqual({p.titulo for p in portada.context['promociones']}, {'Lámpara', 'Pesas rusas'})
        for nombre in ('tienda apagada', 'categoría apagada', 'Producto inactivo', 'Producto agotado', 'Oculta'):
            self.assertNotContains(portada, nombre)

    def test_la_seleccion_se_reparte_entre_las_tiendas(self):
        from catalogo.services import vitrina_del_sitio

        for numero in range(5):
            crear_producto(nombre=f'Lámpara {numero}', sku=f'L-{numero}', destacado=True)
        # Multimix tiene seis productos y Fitnes uno: con dos lugares, va uno de cada tienda.
        self.assertEqual({p.tienda for p in vitrina_del_sitio(2)}, {self.multimix, self.fitnes})
        self.assertEqual(len(vitrina_del_sitio(12)), 7)

    def test_dentro_de_una_tienda_se_alternan_las_categorias(self):
        from catalogo.models import Categoria
        from catalogo.services import vitrina_del_sitio

        # Lo ultimo que cargo Multimix es todo de Bebidas, pero la seleccion no sale solo de esa categoria.
        bebidas = Categoria.objects.create(nombre='Bebidas')
        for numero in range(4):
            crear_producto(nombre=f'Bebida {numero}', sku=f'B-{numero}', categoria=bebidas)
        de_multimix = [p for p in vitrina_del_sitio(12) if p.tienda == self.multimix]
        self.assertEqual({p.categoria.nombre for p in de_multimix[:2]}, {'Bebidas', 'General'})
        self.assertEqual(len(de_multimix), 5)

    def test_la_portada_no_se_parece_al_inicio_de_una_tienda(self):
        portada = self.client.get('/')
        # Sin el banner de las tiendas, sin su boton de catalogo y sin el lema de ninguna en su encabezado.
        self.assertNotContains(portada, 'mm-banner')
        self.assertNotContains(portada, 'Ver catálogo')
        self.assertNotContains(portada, 'Tu tienda de bienestar')
        self.assertContains(portada, 'Descubre. Compra. <span>Emprende.</span>', html=False)
        self.assertContains(portada, 'Conocer las tiendas')
        self.assertContains(portada, 'Explorar productos')
        self.assertContains(portada, f'href="{reverse("tiendas:directorio")}"')
        self.assertContains(portada, '¿Qué producto estás buscando?')
        self.assertContains(portada, 'Tiendas de emprendedores en un solo lugar.')
        # El inicio de cada tienda si conserva su banner, y su buscador busca dentro de ella.
        tienda = self.client.get(self.multimix.get_absolute_url())
        self.assertContains(tienda, 'mm-banner-titulo')
        self.assertContains(tienda, 'Tu tienda de bienestar')
        self.assertContains(tienda, 'placeholder="Buscar en Multimix RD"')

    def test_las_categorias_llevan_al_buscador_del_sitio_con_sus_subcategorias(self):
        from catalogo.models import Categoria

        belleza = Categoria.objects.create(nombre='Belleza', orden=1)
        maquillaje = Categoria.objects.create(nombre='Maquillaje', padre=belleza)
        crear_producto(nombre='Labial rojo', sku='B1', categoria=maquillaje, tienda=self.fitnes)
        crear_producto(nombre='Crema facial', sku='B2', categoria=belleza)
        Categoria.objects.create(nombre='Sin productos')
        portada = self.client.get('/')
        categorias = {c.nombre: c.total_productos for c in portada.context['categorias']}
        # Solo las principales con algo a la venta, con lo de sus subcategorias y de todas las tiendas.
        self.assertEqual(categorias, {'Belleza': 2, 'General': 2})
        self.assertContains(portada, '/buscar/?categoria=belleza')

        resultado = self.client.get(reverse('tiendas:buscar'), {'categoria': 'belleza'})
        self.assertEqual({p.nombre for p in resultado.context['pagina']}, {'Labial rojo', 'Crema facial'})
        self.assertEqual(resultado.context['categoria'], belleza)
        self.assertContains(resultado, '<h1 class="h3 mb-1">Belleza</h1>', html=True)
        # Se puede seguir buscando dentro de la categoria.
        resultado = self.client.get(reverse('tiendas:buscar'), {'categoria': 'belleza', 'q': 'labial'})
        self.assertEqual([p.nombre for p in resultado.context['pagina']], ['Labial rojo'])
        # Una categoria que no existe o esta apagada no rompe la busqueda: se ignora.
        Categoria.objects.filter(pk=belleza.pk).update(activa=False)
        for slug in ('belleza', 'no-existe'):
            resultado = self.client.get(reverse('tiendas:buscar'), {'categoria': slug})
            self.assertIsNone(resultado.context['categoria'])
            self.assertEqual(resultado.status_code, 200)

    def test_las_ofertas_salen_aparte_y_no_se_repiten(self):
        self.pesas.precio_oferta = Decimal('2000')
        self.pesas.save()
        portada = self.client.get('/')
        self.assertEqual(portada.context['ofertas'], [self.pesas])
        self.assertContains(portada, 'Ver todas las ofertas')
        self.assertContains(portada, 'Oferta -20%')
        # Sin ofertas vigentes no hay seccion de ofertas, y el enlace "Ofertas" lo dice en vez de "no encontramos".
        self.pesas.precio_oferta = None
        self.pesas.save()
        self.assertNotContains(self.client.get('/'), 'Ver todas las ofertas')
        self.assertContains(self.client.get(reverse('tiendas:buscar'), {'oferta': 'on'}), 'Por ahora no hay ofertas')

    def test_directorio_de_todas_las_tiendas(self):
        from catalogo.models import Categoria

        Tienda.objects.create(nombre='En preparación', activa=False)
        # Una camisa en dos tallas es un producto: el conteo es el del catalogo de la tienda.
        ropa = Categoria.objects.create(nombre='Ropa')
        camisa = crear_producto(nombre='Camisa', sku='C1', categoria=ropa, tienda=self.fitnes, nombre_variante='S')
        crear_producto(nombre='Camisa M', sku='C2', categoria=ropa, tienda=self.fitnes, variante_de=camisa,
                       nombre_variante='M')
        respuesta = self.client.get(reverse('tiendas:directorio'))
        self.assertEqual(respuesta.status_code, 200)
        tiendas = {t.nombre: t for t in respuesta.context['tiendas']}
        self.assertEqual(set(tiendas), {'Fitnes RD', 'Multimix RD'})
        self.assertEqual(tiendas['Fitnes RD'].total_productos, 2)
        self.assertCountEqual(tiendas['Fitnes RD'].categorias_principales, ['General', 'Ropa'])
        # El cliente no ve cuantos productos tiene cada tienda (pedido del dueño el 2026-10-27).
        self.assertNotContains(respuesta, '2 productos')
        self.assertContains(respuesta, 'href="/tienda/fitnes-rd/"')
        self.assertNotContains(respuesta, 'En preparación')
        self.assertContains(self.client.get('/sitemap.xml'), reverse('tiendas:directorio'))
        # Por paginas cuando son muchas.
        with patch('tiendas.views.TIENDAS_POR_PAGINA', 1):
            primera = self.client.get(reverse('tiendas:directorio'))
            self.assertEqual([t.nombre for t in primera.context['tiendas']], ['Fitnes RD'])
            segunda = self.client.get(reverse('tiendas:directorio'), {'pagina': 2})
            self.assertEqual([t.nombre for t in segunda.context['tiendas']], ['Multimix RD'])

    def test_la_portada_muestra_solo_las_primeras_tiendas(self):
        with patch('tiendas.views.TIENDAS_EN_PORTADA', 1):
            portada = self.client.get('/')
        self.assertEqual(portada.context['tiendas'], [self.fitnes])
        self.assertContains(portada, 'Ver todas las tiendas')
        self.assertNotContains(self.client.get('/'), 'Ver todas las tiendas')

    def test_quien_quiere_vender_escribe_al_sitio(self):
        from core.models import ConfiguracionTienda, PaginaInformativa

        configuracion = ConfiguracionTienda.obtener()
        configuracion.whatsapp = '8095550123'
        configuracion.save()
        portada = self.client.get('/')
        self.assertContains(portada, 'id="vender"')
        self.assertContains(portada, 'https://wa.me/18095550123?text=Hola%2C%20quiero%20vender')
        configuracion.whatsapp = ''
        configuracion.correo = 'hola@example.com'
        configuracion.save()
        self.assertContains(self.client.get('/'), 'mailto:hola@example.com?subject=')
        # Sin WhatsApp ni correo, la pagina de contacto; sin ella tampoco no hay a donde escribir, pero desde la Fase 2
        # (2026-10-27) siempre queda el formulario de solicitud.
        configuracion.correo = ''
        configuracion.save()
        self.assertEqual(self.client.get('/').context['vender'], {'url': '/pagina/contacto/', 'medio': 'pagina'})
        PaginaInformativa.objects.filter(slug='contacto').update(publicada=False)
        portada = self.client.get('/')
        self.assertIsNone(portada.context['vender'])
        self.assertContains(portada, 'id="vender"')
        self.assertContains(portada, reverse('tiendas:solicitar_tienda'))
        self.assertNotContains(portada, '¿Prefieres hablar antes?')

    def test_el_panel_solo_se_enlaza_a_quien_tiene_acceso(self):
        from django.conf import settings as ajustes
        from django.contrib.auth import get_user_model

        url_del_panel = f'/{ajustes.ADMIN_URL}/'
        # Clientes y visitantes no ven la direccion del panel en ninguna pagina del sitio.
        for url in ('/', reverse('tiendas:directorio'), reverse('tiendas:buscar'), self.fitnes.get_absolute_url()):
            self.assertNotContains(self.client.get(url), url_del_panel, msg_prefix=url)
        self.client.post(reverse('clientes:salir'))
        self.assertNotContains(self.client.get('/'), url_del_panel)
        vendedor = get_user_model().objects.create_user('vendedor', 'v@example.com', 'clave-segura-123')
        self.fitnes.usuarios.add(vendedor)
        from tiendas.services import dar_acceso_al_panel
        dar_acceso_al_panel([vendedor])
        self.client.force_login(vendedor)
        portada = self.client.get('/')
        self.assertContains(portada, url_del_panel)
        self.assertContains(portada, 'Mi panel')
        self.assertEqual(self.client.get(url_del_panel).status_code, 200)

    def barra_del_telefono(self, respuesta):
        html = respuesta.content.decode()
        inicio = html.index('<nav class="mm-barra-movil"')
        return html[inicio:html.index('</nav>', inicio)]

    def test_la_barra_del_telefono_lleva_a_lo_principal(self):
        # Pedido del dueño el 2026-10-26: barra abajo solo en el telefono (la oculta el CSS en la PC).
        barra = self.barra_del_telefono(self.client.get('/'))
        for etiqueta in ('Inicio', 'Tiendas', 'Buscar', 'Ofertas', 'Mi cuenta'):
            self.assertIn(etiqueta, barra)
        self.assertIn('href="/" aria-current="page"', barra)
        self.assertIn(f'href="{reverse("tiendas:directorio")}"', barra)
        self.assertIn(f'href="{reverse("tiendas:buscar")}?oferta=on"', barra)
        # En el sitio no hay carrito: cada tienda tiene el suyo.
        self.assertNotIn('js-contador-carrito', barra)
        # Dentro de una tienda: su inicio, su catalogo y su carrito con el contador.
        barra = self.barra_del_telefono(self.client.get(ruta('catalogo:lista', tienda=self.fitnes)))
        self.assertIn(f'href="{ruta("catalogo:lista", tienda=self.fitnes)}" aria-current="page"', barra)
        self.assertIn(f'href="{ruta("carrito:detalle", tienda=self.fitnes)}"', barra)
        self.assertIn('js-contador-carrito', barra)
        self.assertNotIn(ruta('carrito:detalle', tienda=self.multimix), barra)
        # La cuenta se marca en sus paginas.
        barra = self.barra_del_telefono(self.client.get(reverse('clientes:cuenta')))
        self.assertIn(f'href="{reverse("clientes:cuenta")}" aria-current="page"', barra)

    def test_sin_sesion_y_con_la_cuenta_obligatoria_no_hay_barra(self):
        self.client.post(reverse('clientes:salir'))
        with self.settings(CUENTA_OBLIGATORIA=True):
            self.assertNotContains(self.client.get(reverse('clientes:entrar')), 'mm-barra-movil')

    def test_el_menu_ofrece_entrar_a_quien_no_tiene_sesion(self):
        self.assertContains(self.client.get('/'), 'Cerrar sesión')
        self.client.post(reverse('clientes:salir'))
        portada = self.client.get('/')
        self.assertNotContains(portada, 'Cerrar sesión')
        self.assertContains(portada, f'href="{reverse("clientes:registro")}"')

    def test_cada_tienda_lleva_su_marca_y_el_camino_de_regreso(self):
        respuesta = self.client.get(self.fitnes.get_absolute_url())
        self.assertContains(respuesta, '<span class="mm-logo-texto">Fitnes RD</span>', html=True)
        self.assertContains(respuesta, 'Todas las tiendas de Multimix RD')
        self.assertContains(respuesta, 'https://wa.me/18295559999')
        self.assertNotContains(respuesta, 'https://wa.me/18095550000')

    def test_tienda_apagada_desaparece_del_sitio(self):
        Tienda.objects.filter(pk=self.fitnes.pk).update(activa=False)
        for url in (self.fitnes.get_absolute_url(), self.pesas.get_absolute_url(),
                    ruta('carrito:detalle', tienda=self.fitnes), ruta('pedidos:checkout', tienda=self.fitnes)):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertNotContains(self.client.get(reverse('tiendas:buscar')), 'Pesas rusas')
        self.assertNotContains(self.client.get('/sitemap.xml'), '/tienda/fitnes-rd/')

    def test_buscador_del_sitio_lleva_a_la_tienda_de_cada_producto(self):
        respuesta = self.client.get(reverse('tiendas:buscar'))
        self.assertCountEqual([p.nombre for p in respuesta.context['pagina']], ['Lámpara', 'Pesas rusas'])
        self.assertContains(respuesta, self.pesas.get_absolute_url())
        self.assertContains(respuesta, 'Fitnes RD')
        # Cada resultado se agrega o se compra en el carrito de su propia tienda.
        self.assertContains(respuesta, ruta('carrito:agregar', tienda=self.fitnes))
        self.assertContains(respuesta, ruta('carrito:agregar', tienda=self.multimix))
        self.assertContains(respuesta, 'name="comprar"')
        respuesta = self.client.get(reverse('tiendas:buscar'), {'q': 'pesas'})
        self.assertEqual([p.nombre for p in respuesta.context['pagina']], ['Pesas rusas'])

    def test_paginas_del_sitio(self):
        self.assertContains(self.client.get(reverse('core:terminos')), 'responde por sus productos')
        sitemap = self.client.get('/sitemap.xml')
        for url in ('/tienda/multimix-rd/', '/tienda/fitnes-rd/', self.pesas.get_absolute_url(), '/terminos/'):
            self.assertContains(sitemap, url)
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /tienda/*/carrito/')

    def test_enlaces_de_cuando_habia_una_sola_tienda(self):
        self.assertRedirects(
            self.client.get('/catalogo/', {'q': 'lampara'}), '/tienda/multimix-rd/catalogo/?q=lampara',
            fetch_redirect_response=False,
        )
        respuesta = self.client.get(f'/producto/{self.lampara.slug}/')
        self.assertRedirects(respuesta, self.lampara.get_absolute_url())
        # La guia "Como comprar" ya no existe: su enlace lleva al inicio de la tienda.
        self.assertRedirects(
            self.client.get('/como-comprar/'), '/tienda/multimix-rd/como-comprar/', target_status_code=301,
        )
        self.assertRedirects(self.client.get('/tienda/multimix-rd/como-comprar/'), self.multimix.get_absolute_url(),
                             status_code=301)
        Tienda.objects.update(activa=False)
        self.assertEqual(self.client.get('/catalogo/').status_code, 404)


class CatalogoPorTiendaTests(DosTiendas):
    def test_cada_tienda_muestra_solo_su_catalogo(self):
        nombres = [p.nombre for p in self.client.get(ruta('catalogo:lista', tienda=self.fitnes)).context['pagina']]
        self.assertEqual(nombres, ['Pesas rusas'])
        inicio = self.client.get(self.multimix.get_absolute_url())
        self.assertContains(inicio, 'Lámpara')
        self.assertNotContains(inicio, 'Pesas rusas')

    def test_un_producto_no_se_abre_desde_otra_tienda(self):
        ajena = ruta('catalogo:producto', self.pesas.slug, tienda=self.multimix)
        self.assertEqual(self.client.get(ajena).status_code, 404)
        self.assertEqual(self.client.get(self.pesas.get_absolute_url()).status_code, 200)

    def test_envios_son_de_la_tienda(self):
        envios = self.client.get(ruta('core:envios', tienda=self.fitnes))
        self.assertEqual(list(envios.context['zonas']), [self.zona_fitnes])

    def test_el_menu_trae_las_categorias_de_la_tienda(self):
        from catalogo.models import Categoria

        deportes = Categoria.objects.create(nombre='Deportes')
        crear_producto(nombre='Mat de yoga', sku='P2', categoria=deportes, tienda=self.fitnes)
        en_fitnes = self.client.get(self.fitnes.get_absolute_url())
        self.assertCountEqual([c.nombre for c in en_fitnes.context['categorias_menu']], ['General', 'Deportes'])
        en_multimix = self.client.get(self.multimix.get_absolute_url())
        self.assertEqual([c.nombre for c in en_multimix.context['categorias_menu']], ['General'])
        vacia = self.client.get(ruta('catalogo:categoria', deportes.slug, tienda=self.multimix))
        self.assertEqual(list(vacia.context['pagina']), [])


class CarritoPorTiendaTests(DosTiendas):
    def test_cada_tienda_tiene_su_carrito(self):
        self.agregar(self.lampara, self.multimix, 2)
        self.agregar(self.pesas, self.fitnes, 1)
        en_multimix = self.client.get(ruta('carrito:detalle', tienda=self.multimix))
        en_fitnes = self.client.get(ruta('carrito:detalle', tienda=self.fitnes))
        self.assertEqual([(l.producto, l.cantidad) for l in en_multimix.context['lineas']], [(self.lampara, 2)])
        self.assertEqual([(l.producto, l.cantidad) for l in en_fitnes.context['lineas']], [(self.pesas, 1)])
        self.assertEqual((en_multimix.context['carrito_cantidad'], en_fitnes.context['carrito_cantidad']), (2, 1))
        self.assertEqual(en_fitnes.context['resumen'].total, Decimal('2500.00'))

    def test_no_se_agrega_un_producto_de_otra_tienda(self):
        respuesta = self.agregar(self.pesas, self.multimix, **FETCH)
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['cantidad_total'], 0)
        self.assertEqual(self.client.session.get(settings.CARRITO_SESSION_ID), None)

    def test_el_cupon_solo_vale_en_su_tienda(self):
        self.agregar(self.pesas, self.fitnes)
        url = ruta('carrito:cupon_aplicar', tienda=self.fitnes)
        self.assertFalse(self.client.post(url, {'codigo': 'MULTI10'}, **FETCH).json()['ok'])
        datos = self.client.post(url, {'codigo': 'fit10'}, **FETCH).json()
        self.assertEqual((datos['ok'], datos['cupon'], datos['total']), (True, 'FIT10', 'RD$ 2,250.00'))

    def test_carrito_del_formato_anterior_se_descarta_sin_romper(self):
        sesion = self.client.session
        sesion[settings.CARRITO_SESSION_ID] = {'items': {str(self.lampara.pk): 3}, 'cupon': 'MULTI10'}
        sesion.save()
        self.assertEqual(self.client.get(ruta('carrito:detalle')).context['lineas'], [])
        self.agregar(self.lampara, self.multimix)
        self.assertEqual(
            self.client.session[settings.CARRITO_SESSION_ID],
            {str(self.multimix.pk): {'items': {str(self.lampara.pk): 1}, 'cupon': ''}},
        )


class PedidoPorTiendaTests(DosTiendas):
    def test_el_pedido_es_de_la_tienda_y_no_toca_el_otro_carrito(self):
        self.agregar(self.lampara, self.multimix, 2)
        self.agregar(self.pesas, self.fitnes, 1)
        respuesta = self.pedir(self.fitnes)
        pedido = Pedido.objects.get()
        self.assertRedirects(respuesta, pedido.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(pedido.tienda, self.fitnes)
        self.assertEqual(pedido.numero, f'FIT-{timezone.localdate().year}-00001')
        self.assertEqual([d.producto for d in pedido.detalles.all()], [self.pesas])
        self.assertEqual(pedido.total, Decimal('2500.00'))

        # El carrito de la otra tienda sigue como estaba.
        self.assertEqual(self.client.get(ruta('carrito:detalle', tienda=self.fitnes)).context['lineas'], [])
        self.assertEqual(len(self.client.get(ruta('carrito:detalle', tienda=self.multimix)).context['lineas']), 1)

    def test_la_confirmacion_lleva_los_datos_de_la_tienda_que_vendio(self):
        self.agregar(self.pesas, self.fitnes)
        pagina = self.client.get(self.pedir(self.fitnes).url)
        self.assertEqual(pagina.context['tienda'], self.fitnes)
        self.assertTrue(pagina.context['enlace_whatsapp'].startswith('https://wa.me/18295559999?text='))
        # Las cuentas son las de la tienda que vendio, no las de otra ni las del sitio.
        self.assertContains(pagina, f'000-{self.fitnes.pk}')
        self.assertNotContains(pagina, f'000-{self.multimix.pk}')
        self.assertNotContains(pagina, 'Banco Popular')
        self.assertContains(pagina, 'Compra en <strong>Fitnes RD</strong>')

    def test_cada_tienda_numera_sus_pedidos_por_separado(self):
        for tienda, producto in ((self.multimix, self.lampara), (self.fitnes, self.pesas), (self.fitnes, self.pesas)):
            self.agregar(producto, tienda)
            self.pedir(tienda)
        anio = timezone.localdate().year
        self.assertEqual(
            list(Pedido.objects.order_by('id').values_list('numero', flat=True)),
            [f'MMX-{anio}-00001', f'FIT-{anio}-00001', f'FIT-{anio}-00002'],
        )

    def test_zona_y_cupon_de_otra_tienda_no_se_aceptan(self):
        self.agregar(self.pesas, self.fitnes)
        envio = {'metodo_entrega': 'envio', 'sector': 'Naco', 'direccion': 'Calle 1 #5'}
        respuesta = self.pedir(self.fitnes, zona=self.zona_multimix.pk, **envio)
        self.assertIn('zona', respuesta.context['formulario'].errors)
        respuesta = self.pedir(self.fitnes, cupon='MULTI10')
        self.assertIn('cupon', respuesta.context['formulario'].errors)
        self.assertEqual(Pedido.objects.count(), 0)

        self.pedir(self.fitnes, zona=self.zona_fitnes.pk, cupon='FIT10', **envio)
        pedido = Pedido.objects.get()
        self.assertEqual((pedido.descuento, pedido.costo_envio, pedido.total),
                         (Decimal('250.00'), Decimal('150.00'), Decimal('2400.00')))

    def test_los_totales_en_vivo_usan_las_zonas_de_la_tienda(self):
        self.agregar(self.pesas, self.fitnes)
        url = ruta('pedidos:totales', tienda=self.fitnes)
        datos = self.client.post(url, {'metodo_entrega': 'envio', 'zona': self.zona_multimix.pk}).json()
        self.assertEqual(datos['envio'], 'Elige tu zona')
        datos = self.client.post(url, {'metodo_entrega': 'envio', 'zona': self.zona_fitnes.pk}).json()
        self.assertEqual((datos['envio'], datos['total']), ('RD$ 150.00', 'RD$ 2,650.00'))

    def test_contra_entrega_se_activa_por_tienda(self):
        Tienda.objects.filter(pk=self.fitnes.pk).update(permitir_contra_entrega=True)
        self.agregar(self.pesas, self.fitnes)
        self.agregar(self.lampara, self.multimix)
        self.assertContains(self.client.get(ruta('pedidos:checkout', tienda=self.fitnes)), 'pago-contra_entrega')
        self.assertNotContains(self.client.get(ruta('pedidos:checkout', tienda=self.multimix)), 'pago-contra_entrega')

    def test_la_factura_sale_a_nombre_de_la_tienda(self):
        self.agregar(self.pesas, self.fitnes)
        self.pedir(self.fitnes)
        pedido = Pedido.objects.get()
        with patch('pedidos.factura_views.generar_imagen_factura', return_value=b'png') as generar:
            self.client.get(reverse('pedidos:factura', args=[pedido.token]))
        self.assertEqual(generar.call_args.args[:2], (pedido, 'Fitnes RD'))
        from pedidos.factura import codigo_de_verificacion

        verificacion = self.client.get(reverse('pedidos:verificar_factura', args=[codigo_de_verificacion(pedido)]))
        self.assertContains(verificacion, 'registrado en Fitnes RD')
