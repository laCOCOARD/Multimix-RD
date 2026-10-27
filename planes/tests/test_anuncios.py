"""Anuncios de las tiendas en la portada segun su plan: banners que aprueba el administrador y productos
"Patrocinado". La portada siempre dice que son anuncios."""
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Producto
from catalogo.tests.test_modelos import crear_producto, imagen_de_prueba
from core.models import ConfiguracionTienda
from planes import services
from planes.models import Anuncio, Plan
from tiendas.models import Tienda
from tiendas.services import dar_acceso_al_panel
from tiendas.tests.utiles import tienda_de_prueba

CLAVE = 'clave-segura-123'


class ConAnuncios(TestCase):
    def setUp(self):
        # En Windows un archivo abierto no se deja borrar: la carpeta temporal se limpia como se pueda.
        self.media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.media.cleanup)
        ajuste = self.settings(MEDIA_ROOT=self.media.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_superuser('admin', 'dueno@example.com', CLAVE)
        self.estandar = Plan.objects.get(nombre='Estándar')   # 1 anuncio y 4 productos
        self.tienda = tienda_de_prueba(correo='tienda@example.com')
        self.ajena = tienda_de_prueba('Fitnes RD')
        self.vendedor = Usuario.objects.create_user('vendedor', 'vendedor@example.com', CLAVE)
        self.tienda.usuarios.add(self.vendedor)
        dar_acceso_al_panel([self.vendedor])
        self.lampara = crear_producto(nombre='Lámpara', sku='L1', precio=Decimal('1000'))
        self.pesas = crear_producto(nombre='Pesas', sku='P1', precio=Decimal('900'), tienda=self.ajena)
        config = ConfiguracionTienda.obtener()
        config.correo = 'sitio@example.com'
        config.save()

    def con_plan(self, tienda, plan=None):
        Tienda.objects.filter(pk=tienda.pk).update(plan=plan or self.estandar)
        tienda.refresh_from_db()
        return tienda

    def anuncio(self, tienda=None, **datos):
        valores = {'tienda': tienda or self.tienda, 'titulo': 'Gran oferta', 'imagen': imagen_de_prueba(),
                   'aprobado': True}
        valores.update(datos)
        return Anuncio.objects.create(**valores)


class LimitesDelPlanTests(ConAnuncios):
    def test_sin_plan_no_hay_anuncios_y_el_plan_pone_el_limite(self):
        borrador = Anuncio(tienda=self.tienda, titulo='Nuevo', imagen=imagen_de_prueba())
        with self.assertRaises(ValidationError):
            borrador.full_clean()
        self.con_plan(self.tienda)
        borrador.full_clean()
        borrador.save()
        segundo = Anuncio(tienda=self.tienda, titulo='Otro', imagen=imagen_de_prueba())
        with self.assertRaisesMessage(ValidationError, 'Tu plan permite 1 anuncio activo'):
            segundo.full_clean()
        segundo.activo = False
        segundo.full_clean()

    def test_el_anuncio_lleva_a_un_producto_de_la_misma_tienda(self):
        self.con_plan(self.tienda)
        anuncio = Anuncio(tienda=self.tienda, titulo='Ajeno', imagen=imagen_de_prueba(), producto=self.pesas)
        with self.assertRaises(ValidationError):
            anuncio.full_clean()

    def test_productos_anunciados_segun_el_plan(self):
        self.lampara.patrocinado = True
        with self.assertRaisesMessage(ValidationError, 'no incluye productos anunciados'):
            self.lampara.full_clean()
        self.con_plan(self.tienda)
        self.lampara = Producto.objects.get(pk=self.lampara.pk)
        self.lampara.patrocinado = True
        self.lampara.full_clean()
        self.lampara.save()
        for numero in range(3):
            crear_producto(nombre=f'Extra {numero}', sku=f'E{numero}', patrocinado=True)
        quinto = crear_producto(nombre='Quinto', sku='Q1')
        quinto.patrocinado = True
        with self.assertRaisesMessage(ValidationError, 'permite anunciar 4 productos'):
            quinto.full_clean()


class PortadaTests(ConAnuncios):
    def test_la_portada_muestra_los_anuncios_aprobados_como_anuncios(self):
        self.con_plan(self.tienda)
        self.anuncio(titulo='Lámparas al 2x1', producto=self.lampara)
        self.anuncio(titulo='Sin aprobar', aprobado=False, activo=False)
        portada = self.client.get('/')
        self.assertEqual([a.titulo for a in portada.context['anuncios']], ['Lámparas al 2x1'])
        self.assertContains(portada, 'Anuncio · Multimix RD')
        self.assertContains(portada, f'href="{self.lampara.get_absolute_url()}"')
        self.assertNotContains(portada, 'Sin aprobar')

    def test_respeta_el_limite_del_plan_y_las_tiendas_activas(self):
        self.con_plan(self.tienda)
        primero = self.anuncio(titulo='Primero', orden=1)
        Anuncio.objects.create(tienda=self.tienda, titulo='Segundo', imagen=imagen_de_prueba(), aprobado=True, orden=2)
        # Sin plan (o con un plan sin anuncios) no sale aunque este aprobado.
        Anuncio.objects.create(tienda=self.ajena, titulo='De Fitnes', imagen=imagen_de_prueba(), aprobado=True)
        self.assertEqual(services.anuncios_para_la_portada(), [primero])
        Tienda.objects.filter(pk=self.tienda.pk).update(activa=False)
        self.assertEqual(services.anuncios_para_la_portada(), [])

    def test_los_productos_anunciados_van_primero_con_su_etiqueta(self):
        self.con_plan(self.tienda)
        Producto.objects.filter(pk=self.lampara.pk).update(patrocinado=True)
        # La tienda sin plan marco un producto, pero no sale como patrocinado.
        Producto.objects.filter(pk=self.pesas.pk).update(patrocinado=True)
        crear_producto(nombre='Mesa nueva', sku='M1')
        portada = self.client.get('/')
        productos = portada.context['productos']
        self.assertEqual(productos[0], self.lampara)
        self.assertTrue(productos[0].es_patrocinado)
        self.assertEqual([p for p in productos if getattr(p, 'es_patrocinado', False)], [self.lampara])
        self.assertContains(portada, 'Patrocinado', count=1)


class PanelDeAnunciosTests(ConAnuncios):
    def setUp(self):
        super().setUp()
        self.con_plan(self.tienda)
        self.client.force_login(self.vendedor)

    def datos(self, **cambios):
        datos = {'tienda': self.tienda.pk, 'titulo': 'Mi anuncio', 'texto': '', 'imagen': imagen_de_prueba(),
                 'producto': '', 'activo': 'on', 'orden': '0', 'vigente_desde_0': '', 'vigente_desde_1': '',
                 'vigente_hasta_0': '', 'vigente_hasta_1': ''}
        datos.update(cambios)
        return datos

    def test_la_tienda_crea_su_anuncio_y_el_administrador_lo_aprueba(self):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('admin:planes_anuncio_add'), self.datos())
        self.assertEqual(respuesta.status_code, 302)
        anuncio = Anuncio.objects.get()
        self.assertFalse(anuncio.aprobado)
        self.assertEqual(mail.outbox[-1].to, ['sitio@example.com'])
        # El vendedor no se lo aprueba a si mismo.
        self.client.post(reverse('admin:planes_anuncio_changelist'), {
            'action': 'aprobar', '_selected_action': [anuncio.pk],
        })
        anuncio.refresh_from_db()
        self.assertFalse(anuncio.aprobado)
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin:planes_anuncio_changelist'), {
                'action': 'aprobar', '_selected_action': [anuncio.pk],
            })
        anuncio.refresh_from_db()
        self.assertTrue(anuncio.aprobado)
        self.assertEqual(sorted(mail.outbox[-1].to), ['tienda@example.com', 'vendedor@example.com'])

    def test_cambiar_el_contenido_lo_devuelve_a_revision(self):
        anuncio = self.anuncio()
        url = reverse('admin:planes_anuncio_change', args=[anuncio.pk])
        self.client.post(url, self.datos(titulo='Otro título', imagen=''))
        anuncio.refresh_from_db()
        self.assertEqual((anuncio.titulo, anuncio.aprobado), ('Otro título', False))

    def test_cada_tienda_ve_y_cambia_solo_sus_anuncios(self):
        propio = self.anuncio()
        ajeno = self.anuncio(tienda=self.con_plan(self.ajena), titulo='De Fitnes')
        lista = self.client.get(reverse('admin:planes_anuncio_changelist'))
        self.assertEqual(list(lista.context['cl'].result_list), [propio])
        self.assertNotEqual(self.client.get(reverse('admin:planes_anuncio_change', args=[ajeno.pk])).status_code, 200)
        # Tampoco puede elegir un producto de otra tienda.
        respuesta = self.client.post(reverse('admin:planes_anuncio_add'), self.datos(producto=self.pesas.pk, activo=''))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Anuncio.objects.filter(tienda=self.tienda).count(), 1)
