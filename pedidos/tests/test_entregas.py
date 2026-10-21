"""Envio gratis desde un monto y fecha estimada de entrega."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import translation

from catalogo.models import Disponibilidad
from catalogo.tests.test_modelos import crear_producto
from pedidos import entregas, services
from pedidos.models import Pedido
from promociones.models import Cupon
from tiendas.tests.utiles import entrar_como_cliente, ruta

from .utiles import carrito_con, cupon_de_prueba, datos_pedido, zona_de_prueba

Entrega = Pedido.Entrega
JUEVES = date(2026, 10, 22)
SABADO = date(2026, 10, 24)


class DiasHabilesTests(TestCase):
    def test_el_domingo_no_cuenta(self):
        self.assertEqual(entregas.sumar_dias_habiles(SABADO, 1), date(2026, 10, 26))
        self.assertEqual(entregas.sumar_dias_habiles(JUEVES, 2), SABADO)
        # Pedido hecho un domingo con 0 dias: el lunes.
        self.assertEqual(entregas.sumar_dias_habiles(date(2026, 10, 25), 0), date(2026, 10, 26))

    def test_textos(self):
        with translation.override('es'):
            self.assertEqual(entregas.Estimado(JUEVES, JUEVES, JUEVES).texto, 'hoy')
            self.assertEqual(entregas.Estimado(date(2026, 10, 23), date(2026, 10, 23), JUEVES).texto, 'mañana')
            self.assertEqual(
                entregas.Estimado(SABADO, date(2026, 10, 27), JUEVES).texto,
                'entre el sábado 24 y el martes 27 de octubre',
            )
            self.assertEqual(
                entregas.Estimado(date(2026, 10, 30), date(2026, 11, 2), JUEVES).texto,
                'entre el viernes 30 de octubre y el lunes 2 de noviembre',
            )


class PlazosTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(precio=Decimal('1000'), controla_stock=False)
        self.tienda = self.producto.tienda
        self.zona = zona_de_prueba()
        self.zona.dias_entrega_min, self.zona.dias_entrega_max = 1, 3
        self.zona.save()

    def test_plazo_por_zona_y_para_recoger(self):
        plazo = entregas.estimar(self.tienda, False, self.zona, hoy=JUEVES)
        self.assertEqual((plazo.desde, plazo.hasta), (date(2026, 10, 23), date(2026, 10, 26)))
        self.assertIsNone(entregas.estimar(self.tienda, False, None, hoy=JUEVES))
        recoger = entregas.estimar(self.tienda, True, hoy=JUEVES)
        self.assertEqual(recoger.desde, date(2026, 10, 23))

    def test_bajo_pedido_suma_los_dias_de_la_tienda(self):
        self.tienda.dias_bajo_pedido = 5
        plazo = entregas.estimar(self.tienda, True, bajo_pedido=True, hoy=JUEVES)
        self.assertEqual(plazo.desde, entregas.sumar_dias_habiles(JUEVES, 6))

    def test_sin_zona_se_estima_de_la_mas_rapida_a_la_mas_lenta(self):
        lejos = zona_de_prueba('Santiago')
        lejos.dias_entrega_min, lejos.dias_entrega_max = 3, 5
        plazo = entregas.estimar_envio(self.tienda, [self.zona, lejos], hoy=JUEVES)
        self.assertEqual((plazo.desde, plazo.hasta), (date(2026, 10, 23), entregas.sumar_dias_habiles(JUEVES, 5)))

    def test_la_zona_no_admite_maximo_menor_que_el_minimo(self):
        self.zona.dias_entrega_min, self.zona.dias_entrega_max = 4, 2
        with self.assertRaises(ValidationError):
            self.zona.full_clean()

    def test_el_pedido_guarda_lo_prometido(self):
        self.producto.disponibilidad = Disponibilidad.BAJO_PEDIDO
        self.producto.save()
        pedido = services.crear_pedido(
            carrito_con((self.producto, 1)),
            datos_pedido(metodo_entrega=Entrega.ENVIO, zona=self.zona, direccion='Calle 1'),
        )
        esperado = entregas.estimar(self.tienda, False, self.zona, bajo_pedido=True)
        self.assertEqual((pedido.entrega_desde, pedido.entrega_hasta), (esperado.desde, esperado.hasta))


class EnvioGratisTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(precio=Decimal('1000'), controla_stock=False)
        self.tienda = self.producto.tienda
        self.tienda.envio_gratis_desde = Decimal('2000')
        self.zona = zona_de_prueba()

    def test_desde_el_monto_no_se_cobra_el_envio(self):
        uno = services.calcular_totales(carrito_con((self.producto, 1)), Entrega.ENVIO, self.zona)
        dos = services.calcular_totales(carrito_con((self.producto, 2)), Entrega.ENVIO, self.zona)
        self.assertEqual(uno.costo_envio, Decimal('250.00'))
        self.assertEqual(dos.costo_envio, Decimal('0'))
        self.assertEqual(dos.total, Decimal('2000.00'))

    def test_cuenta_despues_del_cupon(self):
        cupon_de_prueba('CIEN', tipo=Cupon.Tipo.MONTO_FIJO, valor=Decimal('100'))
        totales = services.calcular_totales(carrito_con((self.producto, 2), cupon='CIEN'), Entrega.ENVIO, self.zona)
        self.assertEqual(totales.costo_envio, Decimal('250.00'))

    def test_el_pedido_se_crea_sin_envio(self):
        pedido = services.crear_pedido(
            carrito_con((self.producto, 2)),
            datos_pedido(metodo_entrega=Entrega.ENVIO, zona=self.zona, direccion='Calle 1'),
        )
        self.assertEqual(pedido.costo_envio, Decimal('0'))
        self.assertEqual(pedido.total, Decimal('2000.00'))

    def test_progreso(self):
        progreso = services.progreso_envio_gratis(self.tienda, Decimal('500'))
        self.assertEqual((progreso.falta, progreso.porcentaje, progreso.logrado), (Decimal('1500'), 25, False))
        self.assertTrue(services.progreso_envio_gratis(self.tienda, Decimal('2500')).logrado)
        self.tienda.envio_gratis_desde = None
        self.assertIsNone(services.progreso_envio_gratis(self.tienda, Decimal('500')))


class PaginasTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(nombre='Lámpara', precio=Decimal('1000'), controla_stock=False)
        self.tienda = self.producto.tienda
        self.tienda.envio_gratis_desde = Decimal('3000')
        self.tienda.save()
        self.zona = zona_de_prueba()

    def test_el_carrito_dice_cuanto_falta(self):
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 1})
        respuesta = self.client.get(ruta('carrito:detalle'))
        self.assertContains(respuesta, 'Te faltan <strong>RD$ 2,000.00</strong> para el envío gratis')
        datos = self.client.post(
            ruta('carrito:actualizar'), {'producto_id': self.producto.pk, 'cantidad': 3},
            headers={'X-Requested-With': 'fetch'},
        ).json()
        self.assertTrue(datos['envio_gratis']['logrado'])

    def test_la_ficha_muestra_cuando_llega(self):
        respuesta = self.client.get(self.producto.get_absolute_url())
        self.assertContains(respuesta, 'A domicilio: llega')
        self.assertContains(respuesta, 'Para recoger: listo')
        self.assertContains(respuesta, 'Envío gratis en pedidos desde RD$ 3,000.00')

    def test_el_checkout_da_el_plazo_y_el_envio_gratis(self):
        entrar_como_cliente(self.client)
        self.client.post(ruta('carrito:agregar'), {'producto_id': self.producto.pk, 'cantidad': 3})
        self.assertContains(self.client.get(ruta('pedidos:checkout')), 'id="plazo-entrega"')
        datos = self.client.post(ruta('pedidos:totales'), {'metodo_entrega': 'envio', 'zona': self.zona.pk}).json()
        self.assertEqual(datos['envio'], 'Gratis')
        self.assertTrue(datos['plazo'].startswith('Llega '))
        sin_zona = self.client.post(ruta('pedidos:totales'), {'metodo_entrega': 'envio'}).json()
        self.assertEqual(sin_zona['plazo'], 'Elige tu zona para ver cuándo llega.')

    def test_la_pagina_de_envios_da_los_dias(self):
        self.assertContains(self.client.get(ruta('core:envios')), '1 a 2 días hábiles')
