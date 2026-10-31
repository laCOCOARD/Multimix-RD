from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from tiendas.tests.utiles import tienda_de_prueba

from .models import Cupon
from .services import CuponInvalido, calcular_descuento, cupon_meta_aplicable, devolver_uso, registrar_uso, validar_cupon


class CuponTests(TestCase):
    def setUp(self):
        self.tienda = tienda_de_prueba()

    def crear(self, **datos):
        valores = {'tienda': self.tienda, 'codigo': 'PROMO', 'tipo': Cupon.Tipo.PORCENTAJE, 'valor': Decimal('10')}
        valores.update(datos)
        return Cupon.objects.create(**valores)

    def test_codigo_en_mayusculas_y_busqueda_sin_distinguir(self):
        cupon = self.crear(codigo=' bienvenido10 ')
        self.assertEqual(cupon.codigo, 'BIENVENIDO10')
        self.assertEqual(validar_cupon('bienvenido10', Decimal('500'), self.tienda), cupon)

    def test_cada_tienda_tiene_sus_cupones(self):
        otra = tienda_de_prueba('Otra tienda')
        propio = self.crear(codigo='VERANO')
        ajeno = self.crear(codigo='VERANO', tienda=otra, valor=Decimal('50'))
        self.crear(codigo='SOLO-AQUI')
        self.assertEqual(validar_cupon('VERANO', Decimal('500'), self.tienda), propio)
        self.assertEqual(validar_cupon('VERANO', Decimal('500'), otra), ajeno)
        with self.assertRaises(CuponInvalido):
            validar_cupon('SOLO-AQUI', Decimal('500'), otra)
        repetido = Cupon(tienda=otra, codigo='VERANO', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('5'))
        with self.assertRaisesMessage(ValidationError, 'Ya tienes un cupón con ese código.'):
            repetido.full_clean()

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
            Cupon(tienda=self.tienda, codigo='X', tipo=Cupon.Tipo.PORCENTAJE, valor=Decimal('150')).full_clean()

    def test_rechazos(self):
        ahora = timezone.now()
        self.crear(codigo='INACTIVO', activo=False)
        self.crear(codigo='FUTURO', vigente_desde=ahora + timedelta(days=1))
        self.crear(codigo='VENCIDO', vigente_hasta=ahora - timedelta(days=1))
        self.crear(codigo='AGOTADO', usos_maximos=1, usos_actuales=1)
        self.crear(codigo='MINIMO', compra_minima=Decimal('1000'))
        for codigo in ('', 'NOEXISTE', 'INACTIVO', 'FUTURO', 'VENCIDO', 'AGOTADO', 'MINIMO'):
            with self.assertRaises(CuponInvalido, msg=codigo):
                validar_cupon(codigo, Decimal('500'), self.tienda)
        self.assertEqual(validar_cupon('MINIMO', Decimal('1000'), self.tienda).codigo, 'MINIMO')

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

    # --- Cupón meta ---

    def test_meta_requiere_compra_minima(self):
        with self.assertRaises(ValidationError):
            Cupon(tienda=self.tienda, codigo='M1', tipo=Cupon.Tipo.MONTO_FIJO,
                  valor=Decimal('200'), es_meta=True).full_clean()
        with self.assertRaises(ValidationError):
            Cupon(tienda=self.tienda, codigo='M2', tipo=Cupon.Tipo.MONTO_FIJO,
                  valor=Decimal('200'), es_meta=True, compra_minima=Decimal('0')).full_clean()

    def test_meta_aplica_cuando_se_alcanza_el_umbral(self):
        meta = self.crear(codigo='META200', tipo=Cupon.Tipo.MONTO_FIJO,
                          valor=Decimal('200'), es_meta=True, compra_minima=Decimal('3000'))
        self.assertEqual(cupon_meta_aplicable(Decimal('3000'), self.tienda), meta)
        self.assertEqual(cupon_meta_aplicable(Decimal('5000'), self.tienda), meta)

    def test_meta_no_aplica_por_debajo_del_umbral(self):
        self.crear(codigo='META200', tipo=Cupon.Tipo.MONTO_FIJO,
                   valor=Decimal('200'), es_meta=True, compra_minima=Decimal('3000'))
        self.assertIsNone(cupon_meta_aplicable(Decimal('2999.99'), self.tienda))

    def test_meta_no_aplica_si_esta_inactivo(self):
        self.crear(codigo='META200', tipo=Cupon.Tipo.MONTO_FIJO,
                   valor=Decimal('200'), es_meta=True, compra_minima=Decimal('1000'), activo=False)
        self.assertIsNone(cupon_meta_aplicable(Decimal('2000'), self.tienda))

    def test_meta_selecciona_el_mayor_umbral_alcanzado(self):
        self.crear(codigo='META100', tipo=Cupon.Tipo.MONTO_FIJO,
                   valor=Decimal('100'), es_meta=True, compra_minima=Decimal('1000'))
        meta_alta = self.crear(codigo='META500', tipo=Cupon.Tipo.MONTO_FIJO,
                               valor=Decimal('500'), es_meta=True, compra_minima=Decimal('5000'))
        resultado = cupon_meta_aplicable(Decimal('6000'), self.tienda)
        self.assertEqual(resultado, meta_alta)

    def test_meta_no_aplica_a_otra_tienda(self):
        otra = tienda_de_prueba('Otra tienda')
        self.crear(codigo='META200', tipo=Cupon.Tipo.MONTO_FIJO,
                   valor=Decimal('200'), es_meta=True, compra_minima=Decimal('1000'))
        self.assertIsNone(cupon_meta_aplicable(Decimal('2000'), otra))
