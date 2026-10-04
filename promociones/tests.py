from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Cupon
from .services import CuponInvalido, calcular_descuento, devolver_uso, registrar_uso, validar_cupon


class CuponTests(TestCase):
    def crear(self, **datos):
        valores = {'codigo': 'PROMO', 'tipo': Cupon.Tipo.PORCENTAJE, 'valor': Decimal('10')}
        valores.update(datos)
        return Cupon.objects.create(**valores)

    def test_codigo_en_mayusculas_y_busqueda_sin_distinguir(self):
        cupon = self.crear(codigo=' bienvenido10 ')
        self.assertEqual(cupon.codigo, 'BIENVENIDO10')
        self.assertEqual(validar_cupon('bienvenido10', Decimal('500')), cupon)

    def test_descuento_porcentaje(self):
        cupon = self.crear(valor=Decimal('10'))
        self.assertEqual(calcular_descuento(cupon, Decimal('1250.00')), Decimal('125.00'))
        self.assertEqual(calcular_descuento(cupon, Decimal('99.99')), Decimal('10.00'))

    def test_descuento_fijo_nunca_supera_el_subtotal(self):
        cupon = self.crear(tipo=Cupon.Tipo.MONTO_FIJO, valor=Decimal('500'))
        self.assertEqual(calcular_descuento(cupon, Decimal('1200')), Decimal('500.00'))
        self.assertEqual(calcular_descuento(cupon, Decimal('300')), Decimal('300'))

    def test_sin_cupon_no_hay_descuento(self):
        self.assertEqual(calcular_descuento(None, Decimal('300')), Decimal('0.00'))

    def test_porcentaje_mayor_a_100_es_invalido(self):
        with self.assertRaises(ValidationError):
            Cupon(codigo='X', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('150')).full_clean()

    def test_rechazos(self):
        ahora = timezone.now()
        self.crear(codigo='INACTIVO', activo=False)
        self.crear(codigo='FUTURO', vigente_desde=ahora + timedelta(days=1))
        self.crear(codigo='VENCIDO', vigente_hasta=ahora - timedelta(days=1))
        self.crear(codigo='AGOTADO', usos_maximos=1, usos_actuales=1)
        self.crear(codigo='MINIMO', compra_minima=Decimal('1000'))
        for codigo in ('', 'NOEXISTE', 'INACTIVO', 'FUTURO', 'VENCIDO', 'AGOTADO', 'MINIMO'):
            with self.assertRaises(CuponInvalido, msg=codigo):
                validar_cupon(codigo, Decimal('500'))
        self.assertEqual(validar_cupon('MINIMO', Decimal('1000')).codigo, 'MINIMO')

    def test_registrar_y_devolver_uso(self):
        cupon = self.crear(usos_maximos=2)
        registrar_uso(cupon)
        cupon.refresh_from_db()
        self.assertEqual(cupon.usos_actuales, 1)
        self.assertEqual(cupon.usos_restantes, 1)
        devolver_uso(cupon)
        devolver_uso(cupon)
        cupon.refresh_from_db()
        self.assertEqual(cupon.usos_actuales, 0)
