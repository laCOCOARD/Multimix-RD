"""Personas de la tienda (2026-11-06): el dueño agrega dueños o ayudantes; el ayudante solo atiende pedidos."""
from django.contrib.auth import get_user_model
from django.urls import reverse

from pedidos.models import Pedido
from pedidos.services import cambiar_estado
from tiendas import services

from .test_panel import PanelDeVendedores

CLAVE = 'una-clave-larga-9'


class PersonasTests(PanelDeVendedores):
    def setUp(self):
        super().setUp()
        self.url = reverse('admin:tiendas_tienda_personas', args=[self.propia.pk])

    def agregar(self, usuario='maria', rol=services.AYUDANTE, clave=CLAVE):
        return self.client.post(self.url, {
            'accion': 'agregar', 'nombre': 'María', 'usuario': usuario, 'clave': clave, 'rol': rol,
        })

    def test_el_dueno_agrega_un_ayudante_que_solo_ve_pedidos(self):
        self.assertContains(self.client.get(self.url), 'Personas que entran al panel')
        self.assertRedirects(self.agregar(), self.url, fetch_redirect_response=False)
        maria = get_user_model().objects.get(username='maria')
        self.assertTrue(maria.is_staff and maria.check_password(CLAVE))
        self.assertTrue(services.es_ayudante(maria))
        self.assertEqual(list(maria.tiendas.all()), [self.propia])

        self.client.force_login(maria)
        # Su inicio es el tablero de pedidos, con los de su tienda.
        self.assertRedirects(self.client.get(reverse('admin:index')), reverse('admin:pedidos_pedido_changelist'),
                             fetch_redirect_response=False)
        tablero = self.client.get(reverse('admin:pedidos_pedido_changelist'), {'bandeja': 'todos'})
        self.assertEqual([t['pedido'] for t in tablero.context['tarjetas']], [self.pedido_propio])
        # No entra a productos, cuentas, cupones, datos de la tienda ni a manejar personas.
        for nombre in ('catalogo_producto_changelist', 'tiendas_cuentabancaria_changelist', 'promociones_cupon_changelist'):
            self.assertEqual(self.client.get(reverse(f'admin:{nombre}')).status_code, 403, nombre)
        self.assertEqual(self.client.get(reverse('admin:tiendas_tienda_change', args=[self.propia.pk])).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_el_ayudante_atiende_el_pedido(self):
        self.agregar()
        self.client.force_login(get_user_model().objects.get(username='maria'))
        cambiar_estado(self.pedido_propio, Pedido.Estado.PAGADO)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin:pedidos_pedido_estado', args=[self.pedido_propio.pk]),
                             {'estado': Pedido.Estado.PREPARANDO})
        self.pedido_propio.refresh_from_db()
        self.assertEqual(self.pedido_propio.estado, Pedido.Estado.PREPARANDO)

    def test_no_toma_una_cuenta_que_ya_existe(self):
        get_user_model().objects.create_user('cliente1', password=CLAVE)
        self.agregar(usuario='Cliente1')
        self.assertFalse(get_user_model().objects.get(username='cliente1').is_staff)
        self.assertFalse(self.propia.usuarios.filter(username='cliente1').exists())
        # Tampoco la de otro vendedor.
        self.agregar(usuario='otro')
        self.assertFalse(self.propia.usuarios.filter(username='otro').exists())

    def test_la_contrasena_debe_ser_segura(self):
        respuesta = self.agregar(usuario='pedro', clave='123')
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='pedro').exists())
        self.assertContains(respuesta, 'value="pedro"')  # lo escrito no se pierde

    def test_cambiar_rol_y_quitar(self):
        self.agregar()
        maria = get_user_model().objects.get(username='maria')
        self.client.post(self.url, {'accion': 'rol', 'persona': maria.pk, 'rol': services.DUENO})
        self.assertFalse(services.es_ayudante(maria))
        self.client.post(self.url, {'accion': 'rol', 'persona': maria.pk, 'rol': services.AYUDANTE})
        self.assertTrue(services.es_ayudante(maria))
        self.client.post(self.url, {'accion': 'quitar', 'persona': maria.pk})
        maria.refresh_from_db()
        self.assertFalse(maria.is_staff)
        self.assertFalse(maria.tiendas.exists())
        self.assertFalse(maria.groups.exists())

    def test_no_se_quita_a_si_mismo_ni_toca_otra_tienda(self):
        self.client.post(self.url, {'accion': 'quitar', 'persona': self.vendedor.pk})
        self.assertTrue(self.propia.usuarios.filter(pk=self.vendedor.pk).exists())
        # La pagina de personas de otra tienda no se abre, ni se cambia por POST.
        ajena = reverse('admin:tiendas_tienda_personas', args=[self.ajena.pk])
        self.assertEqual(self.client.get(ajena).status_code, 404)
        self.client.post(ajena, {'accion': 'quitar', 'persona': self.otro_vendedor.pk})
        self.assertTrue(self.ajena.usuarios.filter(pk=self.otro_vendedor.pk).exists())
        # Ni a alguien de otra tienda desde la suya.
        self.client.post(self.url, {'accion': 'rol', 'persona': self.otro_vendedor.pk, 'rol': services.AYUDANTE})
        self.assertFalse(services.es_ayudante(self.otro_vendedor))

    def test_no_cambia_el_rol_de_quien_tambien_esta_en_otra_tienda(self):
        compartido = get_user_model().objects.create_user('compartido', password=CLAVE)
        self.propia.usuarios.add(compartido)
        self.ajena.usuarios.add(compartido)
        services.dar_acceso_al_panel([compartido])
        self.client.post(self.url, {'accion': 'rol', 'persona': compartido.pk, 'rol': services.AYUDANTE})
        self.assertFalse(services.es_ayudante(compartido))
        # El administrador principal si puede.
        self.client.force_login(self.admin)
        self.client.post(self.url, {'accion': 'rol', 'persona': compartido.pk, 'rol': services.AYUDANTE})
        self.assertTrue(services.es_ayudante(compartido))

    def test_guardar_la_tienda_no_vuelve_dueno_al_ayudante(self):
        self.agregar()
        maria = get_user_model().objects.get(username='maria')
        services.dar_acceso_al_panel([maria])
        self.assertTrue(services.es_ayudante(maria))

    def test_el_inicio_del_dueno_lleva_a_personas(self):
        self.assertContains(self.client.get(reverse('admin:index')), reverse('admin:tiendas_tienda_mis_personas'))
        self.assertRedirects(self.client.get(reverse('admin:tiendas_tienda_mis_personas')), self.url,
                             fetch_redirect_response=False)
