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


class PreguntasDeClientesTests(PanelDeVendedores):
    def setUp(self):
        super().setUp()
        from clientes.services import registrar_cliente
        from opiniones.models import Pregunta

        ana = registrar_cliente('Ana Pérez', 'ana@example.com', 'clave-segura-123')
        self.pregunta = Pregunta.objects.create(
            tienda=self.propia, producto=self.lampara, usuario=ana, texto='¿Trae bombillo?',
        )
        self.pregunta_ajena = Pregunta.objects.create(
            tienda=self.ajena, producto=self.pesas, usuario=ana, texto='¿Cuánto pesan?',
        )

    def test_el_vendedor_responde_solo_las_de_su_tienda(self):
        from opiniones.models import Pregunta

        self.assertEqual(self.lista('opiniones_pregunta'), [self.pregunta])
        ajena = reverse('admin:opiniones_pregunta_change', args=[self.pregunta_ajena.pk])
        self.assertNotEqual(self.client.get(ajena).status_code, 200)
        self.client.post(ajena, {'respuesta': 'Intento ajeno'})
        self.assertEqual(Pregunta.objects.get(pk=self.pregunta_ajena.pk).respuesta, '')

        propia = reverse('admin:opiniones_pregunta_change', args=[self.pregunta.pk])
        self.client.post(propia, {'respuesta': 'Sí, incluye un bombillo LED.'})
        self.pregunta.refresh_from_db()
        self.assertEqual((self.pregunta.estado, self.pregunta.respondida_por), (Pregunta.Estado.PUBLICADA, self.vendedor))
