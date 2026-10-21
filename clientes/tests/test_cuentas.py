import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.tests.test_modelos import crear_producto
from clientes import services
from clientes.models import Perfil
from pedidos.models import Pedido
from pedidos.tests.utiles import pedido_de_prueba, zona_de_prueba
from tiendas.tests.utiles import ruta, tienda_de_prueba

Usuario = get_user_model()
CLAVE = 'clave-segura-123'
CACHE_REAL = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'pruebas-de-cuentas'}}


def cliente(correo='ana@example.com', nombre='Ana Pérez', telefono='8095551234'):
    return services.registrar_cliente(nombre, correo, CLAVE, telefono)


class RegistroTests(TestCase):
    def datos(self, **cambios):
        datos = {
            'nombre': 'Ana Pérez', 'correo': 'Ana@Example.com', 'telefono': '(809) 555-1234',
            'clave': CLAVE, 'clave_repetida': CLAVE, 'sitio_web': '',
        }
        datos.update(cambios)
        return datos

    def test_crea_la_cuenta_e_inicia_sesion(self):
        respuesta = self.client.post(reverse('clientes:registro'), self.datos())
        self.assertRedirects(respuesta, reverse('clientes:cuenta'))
        usuario = Usuario.objects.get()
        self.assertEqual((usuario.username, usuario.email, usuario.first_name), ('ana@example.com', 'ana@example.com', 'Ana Pérez'))
        self.assertEqual(usuario.perfil.telefono, '8095551234')
        self.assertTrue(usuario.check_password(CLAVE))
        # Una cuenta de cliente nunca entra al panel.
        self.assertFalse(usuario.is_staff or usuario.is_superuser)
        self.assertEqual(self.client.get('/panel/').status_code, 302)
        self.assertContains(self.client.get(reverse('clientes:cuenta')), 'Hola, Ana Pérez')

    def test_vuelve_a_la_pagina_de_donde_venia_pero_no_a_otro_sitio(self):
        checkout = ruta('pedidos:checkout')
        respuesta = self.client.post(reverse('clientes:registro'), self.datos(next=checkout))
        self.assertRedirects(respuesta, checkout, fetch_redirect_response=False)
        self.client.post(reverse('clientes:salir'))
        respuesta = self.client.post(reverse('clientes:registro'), self.datos(correo='otra@example.com', next='https://malo.example/'))
        self.assertRedirects(respuesta, reverse('clientes:cuenta'), fetch_redirect_response=False)

    def test_validaciones(self):
        cliente('ana@example.com')
        casos = {
            'correo': self.datos(),  # ya existe, aunque cambien las mayusculas
            'telefono': self.datos(correo='b@example.com', telefono='555'),
            'clave_repetida': self.datos(correo='b@example.com', clave_repetida='otra-clave-999'),
            'clave': self.datos(correo='b@example.com', clave='12345678', clave_repetida='12345678'),
            'nombre': self.datos(correo='b@example.com', nombre='A'),
        }
        for campo, datos in casos.items():
            respuesta = self.client.post(reverse('clientes:registro'), datos)
            self.assertIn(campo, respuesta.context['formulario'].errors, campo)
        respuesta = self.client.post(reverse('clientes:registro'), self.datos(correo='b@example.com', sitio_web='http://spam'))
        self.assertTrue(respuesta.context['formulario'].non_field_errors())
        self.assertEqual(Usuario.objects.count(), 1)

    @override_settings(CACHES=CACHE_REAL)
    def test_limite_de_cuentas_por_conexion(self):
        for numero in range(services.INTENTOS_MAXIMOS):
            self.client.post(reverse('clientes:registro'), self.datos(correo=f'c{numero}@example.com'))
            self.client.post(reverse('clientes:salir'))
        respuesta = self.client.post(reverse('clientes:registro'), self.datos(correo='una-mas@example.com'))
        self.assertContains(respuesta, 'Se crearon varias cuentas desde tu conexión')
        self.assertEqual(Usuario.objects.count(), services.INTENTOS_MAXIMOS)


class EntrarTests(TestCase):
    def setUp(self):
        self.usuario = cliente()
        self.url = reverse('clientes:entrar')

    def test_entra_con_su_correo_y_sale(self):
        respuesta = self.client.post(self.url, {'username': ' ANA@example.com ', 'password': CLAVE})
        self.assertRedirects(respuesta, reverse('clientes:cuenta'))
        self.assertEqual(self.client.get(reverse('clientes:salir')).status_code, 405)
        self.client.post(reverse('clientes:salir'))
        self.assertRedirects(self.client.get(reverse('clientes:cuenta')), f'{self.url}?next=/cuenta/')

    def test_clave_incorrecta(self):
        respuesta = self.client.post(self.url, {'username': 'ana@example.com', 'password': 'mala'})
        self.assertContains(respuesta, 'El correo o la contraseña no son correctos.')

    def test_el_administrador_entra_con_su_correo_aunque_su_usuario_sea_otro(self):
        get_user_model().objects.create_superuser('MULTIMIX_ADMIN', 'Dueno@Example.com', CLAVE)
        respuesta = self.client.post(self.url, {'username': 'dueno@example.com', 'password': CLAVE})
        self.assertRedirects(respuesta, reverse('clientes:cuenta'), fetch_redirect_response=False)
        self.assertEqual(self.client.get('/panel/').status_code, 200)

    def test_un_correo_repetido_en_dos_cuentas_no_entra_por_correo(self):
        Usuario = get_user_model()
        Usuario.objects.create_user('vendedor1', 'compartido@example.com', CLAVE)
        Usuario.objects.create_user('vendedor2', 'compartido@example.com', CLAVE)
        respuesta = self.client.post(self.url, {'username': 'compartido@example.com', 'password': CLAVE})
        self.assertContains(respuesta, 'El correo o la contraseña no son correctos.')

    @override_settings(CACHES=CACHE_REAL)
    def test_bloquea_despues_de_varios_intentos_y_no_afecta_a_otro_correo(self):
        for _ in range(services.INTENTOS_MAXIMOS):
            self.client.post(self.url, {'username': 'ana@example.com', 'password': 'mala'})
        respuesta = self.client.post(self.url, {'username': 'ana@example.com', 'password': CLAVE})
        self.assertContains(respuesta, 'Demasiados intentos')
        self.assertNotIn('_auth_user_id', self.client.session)

        cliente('luis@example.com', 'Luis Gil')
        self.assertRedirects(
            self.client.post(self.url, {'username': 'luis@example.com', 'password': CLAVE}), reverse('clientes:cuenta'),
        )


class MiCuentaTests(TestCase):
    def setUp(self):
        self.ana = cliente()
        self.luis = cliente('luis@example.com', 'Luis Gil', '8295550000')
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'))
        self.client.force_login(self.ana)

    def comprar(self, **cambios):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        datos = {
            'nombre': 'Ana Pérez', 'telefono': '8095551234', 'metodo_entrega': 'recoger',
            'metodo_pago': 'transferencia', 'acepta_terminos': 'on',
        }
        datos.update(cambios)
        return self.client.post(ruta('pedidos:checkout'), datos)

    def test_solo_ve_sus_pedidos(self):
        self.comprar()
        mio = Pedido.objects.get()
        ajeno = pedido_de_prueba(self.producto, 1, nombre='Luis Gil')
        Pedido.objects.filter(pk=ajeno.pk).update(cliente=self.luis)
        invitado = pedido_de_prueba(self.producto, 1, correo='ana@example.com')

        self.assertEqual(mio.cliente, self.ana)
        pagina = self.client.get(reverse('clientes:cuenta'))
        self.assertEqual(list(pagina.context['pagina']), [mio])
        self.assertContains(pagina, mio.numero)
        self.assertNotContains(pagina, ajeno.numero)
        # Un pedido de invitado no se suma a la cuenta por tener el mismo correo.
        self.assertNotContains(pagina, invitado.numero)
        self.assertIsNone(invitado.cliente)

    def test_el_checkout_llega_lleno_y_recuerda_la_direccion(self):
        zona = zona_de_prueba()
        self.comprar(metodo_entrega='envio', zona=zona.pk, sector='Naco', direccion='Calle 1 #5', referencia='Portón azul',
                     telefono='8495557777')
        perfil = Perfil.objects.get(usuario=self.ana)
        self.assertEqual(perfil.telefono, '8495557777')
        direccion = services.direcciones_de(self.ana).get()
        self.assertEqual((direccion.sector, direccion.direccion, direccion.referencia, direccion.principal),
                         ('Naco', 'Calle 1 #5', 'Portón azul', True))

        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        pagina = self.client.get(ruta('pedidos:checkout'))
        inicial = pagina.context['formulario'].initial
        self.assertEqual((inicial['nombre'], inicial['telefono'], inicial['sector'], inicial['direccion']),
                         ('Ana Pérez', '8495557777', 'Naco', 'Calle 1 #5'))
        self.assertContains(pagina, 'value="Calle 1 #5"')
        self.assertContains(pagina, 'Compras con tu cuenta')

    def test_los_avisos_van_al_correo_de_la_cuenta(self):
        # Aunque el navegador mande otro correo, el pedido lleva el de la cuenta.
        self.comprar(correo='otro@example.com')
        pedido = Pedido.objects.get()
        self.assertEqual((pedido.cliente, pedido.correo), (self.ana, 'ana@example.com'))
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        pagina = self.client.get(ruta('pedidos:checkout'))
        self.assertContains(pagina, 'ana@example.com')
        self.assertNotContains(pagina, 'name="correo"')

    def test_sin_cuenta_no_se_compra(self):
        self.client.post(reverse('clientes:salir'))
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        respuesta = self.comprar()
        self.assertRedirects(respuesta, f"{reverse('clientes:entrar')}?next={ruta('pedidos:checkout')}",
                             fetch_redirect_response=False)
        self.assertFalse(Pedido.objects.exists())

    def test_edita_sus_datos(self):
        self.client.post(reverse('clientes:perfil'), {
            'nombre': 'Ana  María Pérez', 'telefono': '829-555-9999',
        })
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.first_name, self.ana.perfil.telefono, self.ana.perfil.recordatorios),
                         ('Ana María Pérez', '8295559999', False))
        self.luis.refresh_from_db()
        self.assertEqual(self.luis.first_name, 'Luis Gil')
        respuesta = self.client.post(reverse('clientes:perfil'), {'nombre': 'Ana', 'telefono': '123'})
        self.assertIn('telefono', respuesta.context['formulario'].errors)

    def test_cambia_su_clave(self):
        self.client.post(reverse('clientes:clave'), {
            'old_password': CLAVE, 'new_password1': 'otra-clave-456', 'new_password2': 'otra-clave-456',
        })
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password('otra-clave-456'))

    def test_las_paginas_de_la_cuenta_piden_sesion(self):
        self.client.post(reverse('clientes:salir'))
        for nombre in ('clientes:cuenta', 'clientes:perfil', 'clientes:clave'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 302, nombre)

    def test_la_cabecera_enlaza_a_la_cuenta(self):
        tienda = tienda_de_prueba()
        self.assertContains(self.client.get(tienda.get_absolute_url()), 'aria-label="Mi cuenta"')
        self.client.post(reverse('clientes:salir'))
        self.assertContains(self.client.get(tienda.get_absolute_url()), 'aria-label="Iniciar sesión"')


class RecuperarClaveTests(TestCase):
    def setUp(self):
        self.usuario = cliente()
        self.url = reverse('clientes:recuperar')

    def test_recupera_con_el_enlace_del_correo(self):
        respuesta = self.client.post(self.url, {'email': 'ana@example.com'})
        self.assertRedirects(respuesta, reverse('clientes:recuperar_enviado'))
        correo = mail.outbox[0]
        self.assertEqual((correo.to, correo.subject), (['ana@example.com'], 'Cambia tu contraseña de Multimix RD'))
        enlace = re.search(r'http://testserver(/cuenta/recuperar/\S+)', correo.body).group(1)

        formulario = self.client.get(enlace, follow=True)
        self.assertContains(formulario, 'Nueva contraseña')
        self.client.post(formulario.redirect_chain[-1][0], {'new_password1': 'nueva-clave-789', 'new_password2': 'nueva-clave-789'})
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('nueva-clave-789'))
        # El enlace sirve una sola vez.
        self.assertContains(self.client.get(enlace, follow=True), 'Este enlace ya se usó o venció')

    def test_no_revela_si_el_correo_tiene_cuenta(self):
        respuesta = self.client.post(self.url, {'email': 'nadie@example.com'})
        self.assertRedirects(respuesta, reverse('clientes:recuperar_enviado'))
        self.assertEqual(mail.outbox, [])

    def test_limite_de_enlaces_por_conexion_y_por_correo(self):
        for _ in range(services.INTENTOS_MAXIMOS):
            self.client.post(self.url, {'email': 'ana@example.com'})
        respuesta = self.client.post(self.url, {'email': 'ana@example.com'})
        self.assertContains(respuesta, 'Ya pediste varios enlaces')
        # Al mismo correo le llegan como mucho ENLACES_POR_CORREO por hora; los demas se responden igual, sin enviar.
        self.assertEqual(len(mail.outbox), services.ENLACES_POR_CORREO)
