"""Correccion de datos del 2026-11-02 (tiendas/0024): correo, provincia y horario de glow-power, horario del pie y el
video "prueba". Solo cambia lo que sigue exactamente como estaba."""
from importlib import import_module

from django.apps import apps
from django.test import TestCase

from catalogo.tests.test_modelos import crear_producto
from core.models import ConfiguracionTienda
from planes.models import Plan, Video
from tiendas.models import Tienda
from tiendas.tests.utiles import tienda_de_prueba

migracion = import_module('tiendas.migrations.0024_datos_glow_power')


class CorreccionDeDatosTests(TestCase):
    def test_corrige_lo_que_estaba_mal_y_respeta_lo_demas(self):
        tienda = tienda_de_prueba('Glow & Power', correo='eliesermena85@gmial.com')
        Tienda.objects.filter(pk=tienda.pk).update(
            slug='glow-power', direccion_tienda='Sosúa, puerto plata', horario=migracion.HORARIO_VIEJO,
            plan=Plan.objects.get(nombre='Premium'),
        )
        configuracion = ConfiguracionTienda.obtener()
        configuracion.horario = migracion.HORARIO_VIEJO
        configuracion.save()
        producto = crear_producto(nombre='Tubitos XS', sku='XS1', tienda=tienda)
        video = Video(tienda=tienda, titulo='prueba', producto=producto, archivo='videos/x.mp4')
        Video.objects.bulk_create([video])

        migracion.corregir(apps, None)

        tienda.refresh_from_db()
        self.assertEqual(
            (tienda.correo, tienda.direccion_tienda, tienda.horario),
            ('eliesermena85@gmail.com', 'Sosúa, Puerto Plata', migracion.HORARIO),
        )
        self.assertEqual(ConfiguracionTienda.objects.get().horario, migracion.HORARIO)
        self.assertEqual(Video.objects.get().titulo, 'Tubitos XS')
        # Lo que ya se corrigio a mano no se toca.
        Tienda.objects.filter(pk=tienda.pk).update(horario='Todos los días')
        migracion.corregir(apps, None)
        self.assertEqual(Tienda.objects.get(pk=tienda.pk).horario, 'Todos los días')
