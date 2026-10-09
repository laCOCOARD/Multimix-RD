from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from tiendas import services
from tiendas.models import Tienda

from .utiles import tienda_de_prueba


class TiendaTests(TestCase):
    def test_direccion_web_y_prefijo_se_generan_del_nombre(self):
        fitnes = Tienda.objects.create(nombre='Fitnes RD')
        self.assertEqual((fitnes.slug, fitnes.prefijo), ('fitnes-rd', 'FIT'))
        self.assertEqual(fitnes.get_absolute_url(), '/tienda/fitnes-rd/')
        # Si otra tienda ya usa las mismas letras, se le agrega un numero.
        self.assertEqual(Tienda.objects.create(nombre='Fitness Pro').prefijo, 'FIT2')
        self.assertEqual(Tienda.objects.create(nombre='Árbol & Ñandú').prefijo, 'ARB')
        self.assertEqual(Tienda.objects.create(nombre='¡¡!!').prefijo, 'TDA')

    def test_prefijo_escrito_a_mano(self):
        self.assertEqual(Tienda.objects.create(nombre='Comida Juan', prefijo=' cju ').prefijo, 'CJU')
        with self.assertRaises(ValidationError):
            Tienda(nombre='Calzado Alfonso', prefijo='C-A').full_clean()
        with self.assertRaises(ValidationError):
            Tienda(nombre='Otra', prefijo='CJU').full_clean()

    def test_acepta_el_prefijo_en_minusculas_y_el_whatsapp_como_se_escribe(self):
        tienda = Tienda(nombre='MaxFit Proteínas', prefijo=' max ', whatsapp='(829) 555-1234')
        tienda.full_clean()
        tienda.save()
        self.assertEqual((tienda.prefijo, tienda.whatsapp), ('MAX', '18295551234'))
        with self.assertRaises(ValidationError):
            Tienda(nombre='Otra', whatsapp='555-1234').full_clean()
        self.assertEqual(tienda.descripcion, tienda.banner_subtitulo)

    def test_guardar_de_nuevo_no_cambia_la_direccion_ni_el_prefijo(self):
        tienda = Tienda.objects.create(nombre='Fitnes RD')
        tienda.nombre = 'Fitness República'
        tienda.save()
        self.assertEqual((tienda.slug, tienda.prefijo), ('fitnes-rd', 'FIT'))


class AccesoAlPanelTests(TestCase):
    def test_el_grupo_de_vendedores_trae_solo_sus_permisos(self):
        permisos = set(Group.objects.get(name=services.GRUPO_VENDEDORES).permissions.values_list('codename', flat=True))
        esperados = {codigo for codigos in services.PERMISOS_VENDEDOR.values() for codigo in codigos}
        self.assertEqual(permisos, esperados)
        # Crear o borrar tiendas, las categorias, la configuracion y los usuarios son del administrador principal.
        for ajeno in ('add_tienda', 'delete_tienda', 'change_categoria', 'change_configuraciontienda', 'view_user'):
            self.assertNotIn(ajeno, permisos)

    def test_quien_administra_cada_tienda(self):
        Usuario = get_user_model()
        propia, ajena = tienda_de_prueba(), tienda_de_prueba('Otra tienda')
        vendedor = Usuario.objects.create_user('vendedor', password='clave-segura-123')
        propia.usuarios.add(vendedor)
        admin = Usuario.objects.create_superuser('admin', 'admin@example.com', 'clave-segura-123')
        inactivo = Usuario.objects.create_superuser('viejo', 'viejo@example.com', 'clave-segura-123', is_active=False)

        self.assertEqual(list(services.tiendas_de(vendedor)), [propia])
        self.assertCountEqual(services.tiendas_de(admin), [propia, ajena])
        self.assertEqual(list(services.tiendas_de(inactivo)), [])
        self.assertEqual(list(services.tiendas_de(AnonymousUser())), [])

    def test_dar_acceso_deja_al_vendedor_listo_para_el_panel(self):
        vendedor = get_user_model().objects.create_user('vendedor', password='clave-segura-123')
        self.assertFalse(vendedor.is_staff)
        services.dar_acceso_al_panel([vendedor])
        vendedor = get_user_model().objects.get(pk=vendedor.pk)
        self.assertTrue(vendedor.is_staff)
        self.assertTrue(vendedor.has_perm('pedidos.change_pedido'))
        self.assertFalse(vendedor.has_perm('tiendas.add_tienda'))
        self.assertFalse(vendedor.is_superuser)


class DirectorioTests(TestCase):
    def test_solo_tiendas_activas_con_sus_productos_a_la_venta(self):
        from catalogo.tests.test_modelos import crear_producto

        activa = tienda_de_prueba()
        apagada = tienda_de_prueba('Apagada', activa=False)
        crear_producto(sku='A1')
        crear_producto(sku='A2', activo=False)
        crear_producto(sku='B1', tienda=apagada)
        (tienda,) = services.directorio()
        self.assertEqual((tienda, tienda.total_productos), (activa, 1))
        self.assertEqual(services.tienda_principal(), activa)
