from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from .models import DESCRIPCION_DEL_SITIO, ConfiguracionTienda
from .telefonos import formatear_telefono, normalizar_telefono_rd, normalizar_whatsapp, telefono_internacional
from .templatetags.moneda import formatear_monto
from .validators import validar_imagen, validar_whatsapp


class MonedaTests(SimpleTestCase):
    def test_formato(self):
        self.assertEqual(formatear_monto(Decimal('1250')), 'RD$ 1,250.00')
        self.assertEqual(formatear_monto(0), 'RD$ 0.00')
        self.assertEqual(formatear_monto('1234567.5'), 'RD$ 1,234,567.50')

    def test_valor_invalido(self):
        self.assertEqual(formatear_monto(None), '')
        self.assertEqual(formatear_monto('abc'), '')


class TelefonoTests(SimpleTestCase):
    def test_normaliza_formatos_comunes(self):
        for valor in ('809-555-1234', '(809) 555 1234', '+1 809 555 1234', '18095551234'):
            self.assertEqual(normalizar_telefono_rd(valor), '8095551234')
        self.assertEqual(normalizar_telefono_rd('829 555 1234'), '8295551234')
        self.assertEqual(normalizar_telefono_rd('8495551234'), '8495551234')

    def test_rechaza_invalidos(self):
        for valor in ('', '555-1234', '305-555-1234', '80955512345', '2809555123'):
            with self.assertRaises(ValueError):
                normalizar_telefono_rd(valor)

    def test_formatos_de_salida(self):
        self.assertEqual(formatear_telefono('8095551234'), '809-555-1234')
        self.assertEqual(telefono_internacional('8095551234'), '18095551234')

    def test_whatsapp_siempre_con_codigo_de_pais(self):
        # wa.me necesita el codigo de pais: a los numeros dominicanos de 10 digitos se les antepone el 1.
        for valor in ('8295551234', '829-555-1234', '(829) 555 1234', '+1 829 555 1234', '18295551234'):
            self.assertEqual(normalizar_whatsapp(valor), '18295551234')
        self.assertEqual(normalizar_whatsapp('+34 612 345 678'), '34612345678')
        self.assertEqual(normalizar_whatsapp('3055551234'), '3055551234')
        self.assertEqual(normalizar_whatsapp(''), '')


class ValidadoresTests(SimpleTestCase):
    def test_whatsapp_solo_digitos(self):
        validar_whatsapp('18095551234')
        with self.assertRaises(ValidationError):
            validar_whatsapp('+1 809 555 1234')

    def test_imagen_extension_y_peso(self):
        validar_imagen(SimpleUploadedFile('foto.webp', b'x' * 10))
        with self.assertRaises(ValidationError):
            validar_imagen(SimpleUploadedFile('foto.gif', b'x' * 10))
        with self.settings(IMAGEN_MAX_BYTES=5):
            with self.assertRaises(ValidationError):
                validar_imagen(SimpleUploadedFile('foto.jpg', b'x' * 10))


class ConfiguracionTests(TestCase):
    def test_una_sola_fila(self):
        config = ConfiguracionTienda.obtener()
        self.assertEqual(config.pk, 1)
        ConfiguracionTienda(nombre='Otra').save()
        self.assertEqual(ConfiguracionTienda.objects.count(), 1)
        self.assertEqual(ConfiguracionTienda.obtener().nombre, 'Otra')

    def test_no_se_puede_borrar(self):
        ConfiguracionTienda.obtener().delete()
        self.assertEqual(ConfiguracionTienda.objects.count(), 1)

    def test_el_whatsapp_se_guarda_con_codigo_de_pais(self):
        config = ConfiguracionTienda.obtener()
        config.whatsapp = '829-555-1234'
        config.full_clean()
        config.save()
        self.assertEqual(ConfiguracionTienda.objects.get().whatsapp, '18295551234')
        config.whatsapp = '555-1234'
        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_valores_por_defecto(self):
        config = ConfiguracionTienda.obtener()
        self.assertEqual(config.descripcion, DESCRIPCION_DEL_SITIO)
        self.assertEqual(config.dias_producto_nuevo, 30)
        self.assertEqual(config.umbral_stock_bajo, 5)
        self.assertEqual(config.horas_vencimiento_pedido, 48)
