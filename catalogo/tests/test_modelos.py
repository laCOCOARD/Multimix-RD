import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from catalogo.models import Categoria, FotoProducto, Producto
from core.models import ConfiguracionTienda


def crear_producto(**datos):
    categoria = datos.pop('categoria', None) or Categoria.objects.get_or_create(nombre='General')[0]
    valores = {
        'nombre': 'Producto de prueba',
        'sku': f'SKU-{Producto.objects.count() + 1}',
        'precio': Decimal('1000.00'),
        'stock_almacen': 10,
    }
    valores.update(datos)
    return Producto.objects.create(categoria=categoria, **valores)


def imagen_de_prueba(nombre='foto.png', formato='PNG', tamano=(2000, 1000)):
    salida = BytesIO()
    Image.new('RGB', tamano, (200, 30, 30)).save(salida, formato)
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type=f'image/{formato.lower()}')


class ProductoPropiedadesTests(TestCase):
    def test_stock_disponible_nunca_negativo(self):
        producto = crear_producto(stock_almacen=5)
        producto.stock_reservado = 2
        self.assertEqual(producto.stock_disponible, 3)
        producto.stock_reservado = 9
        self.assertEqual(producto.stock_disponible, 0)
        self.assertTrue(producto.agotado)

    def test_oferta_sin_fechas(self):
        producto = crear_producto(precio_oferta=Decimal('750.00'))
        self.assertTrue(producto.en_oferta)
        self.assertEqual(producto.precio_final, Decimal('750.00'))
        self.assertEqual(producto.porcentaje_descuento, 25)

    def test_oferta_respeta_vigencia(self):
        ahora = timezone.now()
        futura = crear_producto(precio_oferta=Decimal('500'), oferta_inicio=ahora + timedelta(days=1))
        vencida = crear_producto(precio_oferta=Decimal('500'), oferta_fin=ahora - timedelta(days=1))
        vigente = crear_producto(
            precio_oferta=Decimal('500'),
            oferta_inicio=ahora - timedelta(days=1), oferta_fin=ahora + timedelta(days=1),
        )
        self.assertFalse(futura.en_oferta)
        self.assertEqual(futura.precio_final, Decimal('1000.00'))
        self.assertEqual(futura.porcentaje_descuento, 0)
        self.assertFalse(vencida.en_oferta)
        self.assertTrue(vigente.en_oferta)

    def test_anotaciones_coinciden_con_propiedades(self):
        ahora = timezone.now()
        crear_producto(sku='A', precio_oferta=Decimal('500'))
        crear_producto(sku='B', precio_oferta=Decimal('500'), oferta_fin=ahora - timedelta(days=1))
        for producto in Producto.objects.con_datos_venta():
            self.assertEqual(producto.oferta_vigente, producto.en_oferta)
            self.assertEqual(producto.precio_actual, producto.precio_final)
            self.assertEqual(producto.disponible, producto.stock_disponible)

    def test_nuevo_por_fecha_o_marcado(self):
        ConfiguracionTienda.obtener()
        reciente = crear_producto()
        self.assertTrue(reciente.es_nuevo)
        Producto.objects.filter(pk=reciente.pk).update(creado=timezone.now() - timedelta(days=31))
        reciente.refresh_from_db()
        self.assertFalse(reciente.es_nuevo)
        reciente.nuevo = True
        self.assertTrue(reciente.es_nuevo)

    def test_stock_bajo_usa_el_umbral(self):
        producto = crear_producto(stock_almacen=5)
        self.assertTrue(producto.stock_bajo)
        producto.stock_almacen = 6
        self.assertFalse(producto.stock_bajo)

    def test_slug_unico_y_sku_en_mayusculas(self):
        uno = crear_producto(nombre='Audífonos Pro', sku='aud-1')
        dos = crear_producto(nombre='Audífonos Pro', sku='aud-2')
        self.assertEqual(uno.slug, 'audifonos-pro')
        self.assertEqual(dos.slug, 'audifonos-pro-2')
        self.assertEqual(uno.sku, 'AUD-1')


class ProductoRestriccionesTests(TestCase):
    def test_oferta_debe_ser_menor_que_precio(self):
        producto = crear_producto()
        producto.precio_oferta = Decimal('1000.00')
        with self.assertRaises(ValidationError):
            producto.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            producto.save()

    def test_reservado_no_supera_almacen(self):
        producto = crear_producto(stock_almacen=3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Producto.objects.filter(pk=producto.pk).update(stock_reservado=4)
        producto.stock_reservado = 4
        with self.assertRaises(ValidationError):
            producto.full_clean()

    def test_fin_de_oferta_posterior_al_inicio(self):
        ahora = timezone.now()
        producto = crear_producto(precio_oferta=Decimal('500'))
        producto.oferta_inicio = ahora
        producto.oferta_fin = ahora - timedelta(hours=1)
        with self.assertRaises(ValidationError):
            producto.full_clean()


class FotoProductoTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.mkdtemp()
        cls.override = override_settings(MEDIA_ROOT=cls.media)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media, ignore_errors=True)
        super().tearDownClass()

    def test_se_redimensiona_y_guarda_en_webp(self):
        foto = FotoProducto.objects.create(producto=crear_producto(), imagen=imagen_de_prueba())
        self.assertTrue(foto.imagen.name.endswith('.webp'))
        with Image.open(foto.imagen.path) as imagen:
            self.assertEqual(imagen.format, 'WEBP')
            self.assertEqual(imagen.size, (1200, 600))

    def test_no_amplia_imagenes_pequenas(self):
        foto = FotoProducto.objects.create(
            producto=crear_producto(), imagen=imagen_de_prueba('chica.jpg', 'JPEG', (300, 200)),
        )
        with Image.open(foto.imagen.path) as imagen:
            self.assertEqual(imagen.size, (300, 200))

    def test_una_sola_principal(self):
        producto = crear_producto()
        primera = FotoProducto.objects.create(producto=producto, imagen=imagen_de_prueba())
        self.assertTrue(primera.principal)
        segunda = FotoProducto.objects.create(producto=producto, imagen=imagen_de_prueba(), principal=True)
        primera.refresh_from_db()
        self.assertFalse(primera.principal)
        self.assertEqual(producto.foto_principal, segunda)

    def test_rechaza_formato_y_peso(self):
        producto = crear_producto()
        gif = FotoProducto(producto=producto, imagen=SimpleUploadedFile('a.gif', b'GIF89a'))
        with self.assertRaises(ValidationError):
            gif.full_clean()
        with self.settings(IMAGEN_MAX_BYTES=100):
            pesada = FotoProducto(producto=producto, imagen=imagen_de_prueba())
            with self.assertRaises(ValidationError):
                pesada.full_clean()
