"""La tarjeta de la tienda toma el color de su banner (pedido del dueño el 2026-11-05)."""
import tempfile
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from tiendas import services
from tiendas.models import Tienda

from .utiles import tienda_de_prueba


def banner(arriba, abajo):
    """Un banner con un color arriba y otro en el tercio de abajo."""
    imagen = Image.new('RGB', (900, 300), arriba)
    imagen.paste(abajo, (0, 200, 900, 300))
    salida = BytesIO()
    imagen.save(salida, 'PNG')
    return SimpleUploadedFile('banner.png', salida.getvalue(), content_type='image/png')


class ColorDeLaTarjetaTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        ajuste = self.settings(MEDIA_ROOT=self.media.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.tienda = tienda_de_prueba()

    def poner_banner(self, arriba, abajo):
        self.tienda.banner_imagen = banner(arriba, abajo)
        self.tienda.save()
        return Tienda.objects.get(pk=self.tienda.pk)

    def test_sale_del_pie_del_banner_y_se_guarda(self):
        tienda = self.poner_banner((240, 240, 240), (30, 20, 10))
        self.assertEqual(services.color_de_la_tarjeta(tienda), '#1e140a')
        tienda.refresh_from_db()
        self.assertEqual((tienda.color_banner, tienda.color_banner_de), ('#1e140a', tienda.banner_imagen.name))
        # Ya guardado no se vuelve a leer la imagen.
        with patch.object(services, 'color_principal') as calcular:
            services.color_de_la_tarjeta(tienda)
        calcular.assert_not_called()

    def test_si_cambia_el_banner_se_calcula_otra_vez(self):
        tienda = self.poner_banner((0, 0, 0), (30, 20, 10))
        services.color_de_la_tarjeta(tienda)
        self.tienda = tienda
        tienda = self.poner_banner((0, 0, 0), (200, 40, 40))
        self.assertEqual(services.color_de_la_tarjeta(tienda), '#c82828')

    def test_casi_blanco_se_oscurece(self):
        tienda = self.poner_banner((0, 0, 0), (255, 255, 255))
        color = services.color_de_la_tarjeta(tienda)
        self.assertNotEqual(color, '#ffffff')
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        self.assertLessEqual(services.luminancia(r, g, b), .9)

    def test_sin_banner_o_ilegible_queda_como_siempre(self):
        self.assertEqual(services.color_de_la_tarjeta(self.tienda), '')
        tienda = self.poner_banner((0, 0, 0), (30, 20, 10))
        with patch.object(services, 'color_principal', side_effect=OSError('no se pudo')):
            self.assertEqual(services.color_de_la_tarjeta(tienda), '')

    def test_la_tarjeta_lleva_el_color_y_el_texto_segun_el_fondo(self):
        self.poner_banner((0, 0, 0), (30, 20, 10))
        pagina = self.client.get('/tiendas/')
        self.assertContains(pagina, '--mm-tienda-color: #1e140a;')
        self.assertContains(pagina, 'mm-tienda con-color"')
        self.poner_banner((0, 0, 0), (220, 210, 190))
        self.assertContains(self.client.get('/tiendas/'), 'mm-tienda con-color color-claro"')
