"""Aislamiento de las pantallas nuevas: cada vendedor ve solo lo de su tienda."""
from decimal import Decimal

from django.urls import reverse

from catalogo.models import AvisoDisponible, Disponibilidad
from catalogo.tests.test_modelos import crear_producto

from .test_panel import PanelDeVendedores


class AvisosDeDisponibilidadTests(PanelDeVendedores):
    def setUp(self):
        super().setUp()
        self.agotado = crear_producto(nombre='Agotado', sku='A1', disponibilidad=Disponibilidad.AGOTADO)
        self.ajeno = crear_producto(
            nombre='Ajeno', sku='A2', tienda=self.ajena, precio=Decimal('10'), disponibilidad=Disponibilidad.AGOTADO,
        )
        self.aviso = AvisoDisponible.objects.create(
            tienda=self.propia, producto=self.agotado, correo='ana@example.com',
        )
        self.aviso_ajeno = AvisoDisponible.objects.create(
            tienda=self.ajena, producto=self.ajeno, correo='carlos@example.com',
        )

    def test_el_vendedor_ve_solo_quien_espera_sus_productos(self):
        self.assertEqual(self.lista('catalogo_avisodisponible'), [self.aviso])
        url = reverse('admin:catalogo_avisodisponible_change', args=[self.aviso_ajeno.pk])
        self.assertNotEqual(self.client.get(url).status_code, 200)

    def test_el_administrador_ve_todos(self):
        self.client.force_login(self.admin)
        self.assertCountEqual(self.lista('catalogo_avisodisponible'), [self.aviso, self.aviso_ajeno])
