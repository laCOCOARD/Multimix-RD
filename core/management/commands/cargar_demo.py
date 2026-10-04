"""Carga datos de demostracion para ver la tienda funcionando. Se puede ejecutar varias veces."""
import textwrap
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from carrito.carrito import Carrito
from catalogo.imagenes import convertir_a_webp
from catalogo.models import Categoria, FotoProducto, Producto
from catalogo.services import CACHE_MAS_VENDIDOS
from core.models import ConfiguracionTienda, CuentaBancaria
from core.texto import quitar_tildes
from pedidos.models import Pedido, ZonaEnvio
from pedidos.services import cambiar_estado, crear_pedido
from promociones.models import Cupon

# (nombre, descripcion, color principal, color secundario)
CATEGORIAS = [
    ('Tecnología', 'Audio, accesorios y gadgets para el día a día.', (15, 76, 129), (56, 163, 235)),
    ('Hogar', 'Todo para que tu casa se sienta mejor.', (26, 143, 90), (132, 204, 122)),
    ('Belleza', 'Cuidado personal y bienestar.', (190, 60, 120), (245, 150, 170)),
    ('Deportes', 'Equipos para moverte más.', (229, 99, 0), (255, 180, 70)),
    ('Juguetes', 'Diversión para grandes y pequeños.', (122, 79, 214), (190, 160, 255)),
    ('Moda', 'Accesorios y básicos que combinan con todo.', (11, 34, 57), (90, 110, 140)),
]

# (sku, categoria, nombre, precio, oferta, stock, destacado, descripcion)
PRODUCTOS = [
    ('TEC-001', 'Tecnología', 'Audífonos inalámbricos Pro', '3450', '2890', 25, True,
     'Sonido envolvente, cancelación de ruido y hasta 30 horas de batería con su estuche de carga.'),
    ('TEC-002', 'Tecnología', 'Bocina Bluetooth portátil', '2200', None, 14, False,
     'Resistente al agua, con graves potentes y 12 horas de reproducción continua.'),
    ('TEC-003', 'Tecnología', 'Cargador rápido USB-C 30W', '950', None, 60, False,
     'Carga tu teléfono al 50 % en media hora. Incluye cable USB-C de 1 metro.'),
    ('TEC-004', 'Tecnología', 'Reloj inteligente Fit', '4990', '3990', 4, True,
     'Monitorea pasos, sueño y ritmo cardíaco. Notificaciones del teléfono en tu muñeca.'),
    ('HOG-001', 'Hogar', 'Lámpara de mesa LED', '1250', None, 30, True,
     'Luz cálida regulable en tres intensidades. Ideal para la mesita de noche o el escritorio.'),
    ('HOG-002', 'Hogar', 'Juego de sábanas Queen', '2800', '2240', 18, False,
     'Microfibra suave de 4 piezas: sábana, sábana ajustable y dos fundas.'),
    ('HOG-003', 'Hogar', 'Set de 6 vasos de vidrio', '890', None, 3, False,
     'Vidrio templado de 350 ml, aptos para lavavajillas.'),
    ('HOG-004', 'Hogar', 'Organizador de cocina 3 niveles', '1650', None, 0, False,
     'Estante de acero para especias, frascos y utensilios. Se arma sin herramientas.'),
    ('BEL-001', 'Belleza', 'Secadora de cabello iónica', '2950', None, 12, True,
     'Motor de 2000 W con tres temperaturas y difusor incluido.'),
    ('BEL-002', 'Belleza', 'Set de brochas de maquillaje', '1150', '920', 22, False,
     'Doce brochas de cerdas sintéticas con estuche de viaje.'),
    ('BEL-003', 'Belleza', 'Crema hidratante facial', '780', None, 40, False,
     'Con ácido hialurónico y vitamina E. Para todo tipo de piel.'),
    ('DEP-001', 'Deportes', 'Mancuernas ajustables 20 lb', '3600', None, 9, False,
     'Par de mancuernas con discos intercambiables y agarre antideslizante.'),
    ('DEP-002', 'Deportes', 'Mat de yoga antideslizante', '1350', '1080', 27, True,
     'Seis milímetros de grosor, con correa para transportarlo.'),
    ('DEP-003', 'Deportes', 'Botella térmica 1 litro', '990', None, 5, False,
     'Acero inoxidable de doble pared: frío 24 horas, caliente 12.'),
    ('JUG-001', 'Juguetes', 'Bloques de construcción 500 piezas', '2100', None, 16, False,
     'Compatibles con las marcas más conocidas. Para mayores de 4 años.'),
    ('JUG-002', 'Juguetes', 'Carro a control remoto', '2750', '2190', 11, True,
     'Tracción 4x4, batería recargable y control de 2.4 GHz.'),
    ('JUG-003', 'Juguetes', 'Rompecabezas 1000 piezas', '850', None, 20, False,
     'Paisaje caribeño de 70 x 50 cm. Incluye póster de guía.'),
    ('MOD-001', 'Moda', 'Mochila urbana impermeable', '2400', None, 19, True,
     'Compartimento acolchado para laptop de 15.6" y puerto USB externo.'),
    ('MOD-002', 'Moda', 'Gafas de sol polarizadas', '1450', '1160', 2, False,
     'Protección UV400 con montura liviana. Incluye estuche.'),
    ('MOD-003', 'Moda', 'Gorra clásica ajustable', '650', None, 35, False,
     'Algodón 100 % con cierre metálico. Talla única.'),
]

ZONAS = [
    ('Distrito Nacional', '200'), ('Santo Domingo Este', '250'), ('Santo Domingo Norte', '250'),
    ('Santo Domingo Oeste', '250'), ('Santiago', '350'), ('Interior del país', '450'),
]


FUENTES = ['segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf', 'Arial Bold.ttf']


def cargar_fuente(tamano):
    """Devuelve (fuente, tiene_tildes). La fuente incluida en Pillow no trae letras acentuadas."""
    for nombre in FUENTES:
        try:
            return ImageFont.truetype(nombre, tamano), True
        except OSError:
            continue
    return ImageFont.load_default(size=tamano), False


def crear_imagen(texto, color_a, color_b, lado=1000, variante=0):
    """Imagen cuadrada con degradado y, si hay texto, el nombre centrado. Devuelve un PNG."""
    degradado = Image.linear_gradient('L').resize((lado, lado))
    if variante % 2:
        degradado = degradado.rotate(90)
    imagen = Image.composite(Image.new('RGB', (lado, lado), color_b), Image.new('RGB', (lado, lado), color_a), degradado)
    dibujo = ImageDraw.Draw(imagen, 'RGBA')
    dibujo.ellipse((lado * 0.55, -lado * 0.2, lado * 1.25, lado * 0.5), fill=(255, 255, 255, 38))
    dibujo.ellipse((-lado * 0.25, lado * 0.6, lado * 0.4, lado * 1.25), fill=(255, 255, 255, 26))
    dibujo.rounded_rectangle((lado * 0.08, lado * 0.08, lado * 0.92, lado * 0.92), radius=40, outline=(255, 255, 255, 90), width=4)

    fuente, con_tildes = cargar_fuente(lado // 13)
    renglones = textwrap.wrap(texto if con_tildes else quitar_tildes(texto), width=16)
    alto = fuente.size * 1.25
    y = (lado - alto * len(renglones)) / 2
    for renglon in renglones:
        ancho = dibujo.textlength(renglon, font=fuente)
        dibujo.text(((lado - ancho) / 2 + 3, y + 3), renglon, font=fuente, fill=(0, 0, 0, 70))
        dibujo.text(((lado - ancho) / 2, y), renglon, font=fuente, fill=(255, 255, 255, 255))
        y += alto
    if texto:
        marca, _ = cargar_fuente(lado // 30)
        dibujo.text((lado * 0.12, lado * 0.85), 'MULTIMIX RD - DEMO', font=marca, fill=(255, 255, 255, 190))

    salida = BytesIO()
    imagen.save(salida, 'PNG')
    salida.seek(0)
    return salida


class Command(BaseCommand):
    help = 'Crea categorías, productos con imágenes, cupón, zonas, cuenta bancaria y configuración de demostración.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.configuracion()
        self.cuenta_y_zonas()
        categorias = self.categorias()
        creados = self.productos(categorias)
        Cupon.objects.get_or_create(codigo='BIENVENIDO10', defaults={
            'tipo': Cupon.Tipo.PORCENTAJE, 'valor': Decimal('10'), 'compra_minima': Decimal('1000'),
        })
        pedidos = self.pedidos()
        cache.delete(CACHE_MAS_VENDIDOS)
        self.stdout.write(self.style.SUCCESS(
            f'Demo lista: {len(categorias)} categorías, {Producto.objects.count()} productos '
            f'({creados} nuevos), {pedidos} pedidos de ejemplo, cupón BIENVENIDO10.'
        ))

    def configuracion(self):
        """Completa solo los datos que esten vacios, para no pisar lo que ya ajusto el dueño."""
        config = ConfiguracionTienda.obtener()
        demo = {
            'whatsapp': '18095550123',
            'telefono': '809-555-0123',
            'correo': 'ventas@multimixrd.com',
            'horario': 'Lunes a sábado, 9:00 a.m. a 6:00 p.m.',
            'direccion_tienda': 'Av. Winston Churchill #100, Plaza Central, local 12, Santo Domingo',
            'instagram': 'https://www.instagram.com/multimixrd',
            'facebook': 'https://www.facebook.com/multimixrd',
        }
        for campo, valor in demo.items():
            if not getattr(config, campo):
                setattr(config, campo, valor)
        config.save()

    def cuenta_y_zonas(self):
        CuentaBancaria.objects.get_or_create(banco='Banco Popular Dominicano', numero='812-345678-9', defaults={
            'tipo_cuenta': CuentaBancaria.Tipo.CORRIENTE, 'titular': 'Multimix RD, SRL', 'cedula_rnc': '1-31-12345-6',
        })
        for orden, (nombre, tarifa) in enumerate(ZONAS):
            ZonaEnvio.objects.get_or_create(nombre=nombre, defaults={'tarifa': Decimal(tarifa), 'orden': orden})

    def categorias(self):
        categorias = {}
        for orden, (nombre, descripcion, color_a, color_b) in enumerate(CATEGORIAS):
            categoria, _ = Categoria.objects.get_or_create(nombre=nombre, defaults={
                'descripcion': descripcion, 'orden': orden,
            })
            if not categoria.imagen:
                # Sin texto: la tienda ya muestra el nombre encima de la imagen.
                contenido = convertir_a_webp(crear_imagen('', color_a, color_b, lado=800))
                categoria.imagen.save(f'{categoria.slug}.webp', contenido, save=True)
            categorias[nombre] = (categoria, color_a, color_b)
        return categorias

    def productos(self, categorias):
        creados = 0
        ahora = timezone.now()
        for indice, (sku, cat, nombre, precio, oferta, stock, destacado, descripcion) in enumerate(PRODUCTOS):
            categoria, color_a, color_b = categorias[cat]
            producto, nuevo = Producto.objects.get_or_create(sku=sku, defaults={
                'categoria': categoria, 'nombre': nombre, 'descripcion': descripcion,
                'precio': Decimal(precio), 'precio_oferta': Decimal(oferta) if oferta else None,
                'oferta_fin': ahora + timedelta(days=30) if oferta else None,
                'stock_almacen': stock, 'destacado': destacado,
            })
            if nuevo:
                creados += 1
                # La mitad del catalogo queda como "antiguo" para que la seccion Nuevos no lo muestre todo.
                if indice % 2:
                    Producto.objects.filter(pk=producto.pk).update(creado=ahora - timedelta(days=60))
            if not producto.fotos.exists():
                for variante in range(2 if destacado else 1):
                    colores = (color_a, color_b) if variante == 0 else (color_b, color_a)
                    archivo = ContentFile(crear_imagen(nombre, *colores, variante=variante).read(), name='demo.png')
                    FotoProducto.objects.create(producto=producto, imagen=archivo, orden=variante)
        return creados

    def pedidos(self):
        """Unos pedidos de ejemplo para que el panel y "Más vendidos" tengan datos."""
        if Pedido.objects.exists():
            return 0
        zona = ZonaEnvio.objects.get(nombre='Distrito Nacional')
        Entrega, Pago, Estado = Pedido.Entrega, Pedido.Pago, Pedido.Estado
        ejemplos = [
            ('María Rodríguez', '8095550101', [('TEC-001', 2), ('HOG-001', 1)], Entrega.ENVIO, Pago.TRANSFERENCIA,
             [Estado.PAGADO, Estado.ENVIADO, Estado.ENTREGADO]),
            ('José Martínez', '8295550102', [('DEP-002', 3), ('TEC-001', 1)], Entrega.RECOGER, Pago.EFECTIVO_RECOGER,
             [Estado.LISTO, Estado.ENTREGADO]),
            ('Carla Jiménez', '8495550103', [('MOD-001', 1), ('HOG-001', 2)], Entrega.RECOGER, Pago.TRANSFERENCIA,
             [Estado.PAGADO]),
            ('Luis Peña', '8095550104', [('JUG-002', 1), ('BEL-002', 2)], Entrega.ENVIO, Pago.TRANSFERENCIA, []),
        ]
        for nombre, telefono, lineas, entrega, pago, estados in ejemplos:
            carrito = Carrito(SimpleNamespace(session=SessionStore()))
            for sku, cantidad in lineas:
                carrito.agregar(Producto.objects.select_related('categoria').get(sku=sku), cantidad)
            a_domicilio = entrega == Entrega.ENVIO
            pedido = crear_pedido(carrito, {
                'nombre': nombre, 'telefono': telefono, 'correo': '',
                'metodo_entrega': entrega, 'zona': zona if a_domicilio else None,
                'direccion': 'Calle Principal #25, Ensanche Naco' if a_domicilio else '',
                'referencia': 'Edificio azul, apto. 3B' if a_domicilio else '',
                'metodo_pago': pago, 'transferencia_realizada': not estados and pago == Pago.TRANSFERENCIA,
                'referencia_transferencia': '', 'notas': 'Pedido de demostración',
            })
            for estado in estados:
                pedido = cambiar_estado(pedido, estado)
        return len(ejemplos)
