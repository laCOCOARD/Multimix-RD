"""Carga datos de demostracion para ver el sitio funcionando con dos tiendas. Se puede ejecutar varias veces."""
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
from PIL import Image, ImageDraw

from carrito.carrito import Carrito
from catalogo.imagenes import convertir_a_webp
from catalogo.models import Categoria, FotoProducto, Producto
from catalogo.services import clave_mas_vendidos
from core.fuentes import cargar_fuente
from core.models import ConfiguracionTienda, CuentaBancaria
from core.texto import quitar_tildes
from pedidos.models import Pedido, ZonaEnvio
from pedidos.services import cambiar_estado, crear_pedido
from promociones.models import Cupon
from tiendas.models import Tienda

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

# Segunda tienda, para ver como conviven varias: su catalogo, sus zonas, su cuenta y sus pedidos son aparte.
PRODUCTOS_FITNESS = [
    ('FIT-001', 'Deportes', 'Bandas de resistencia (set de 5)', '1290', '990', 30, True,
     'Cinco niveles de resistencia con agarres, anclaje para puerta y bolsa de transporte.'),
    ('FIT-002', 'Deportes', 'Cuerda para saltar con contador', '650', None, 40, False,
     'Cable de acero ajustable y contador de saltos en el mango.'),
    ('FIT-003', 'Deportes', 'Rodillo de espuma para masaje', '1450', None, 12, True,
     'Alivia la tensión muscular después de entrenar. 45 cm de largo.'),
    ('FIT-004', 'Belleza', 'Proteína vegetal sabor vainilla 1 lb', '2350', None, 18, False,
     'Mezcla de proteína de arveja y arroz, sin azúcar añadida.'),
]

ZONAS_FITNESS = [('Santiago', '150'), ('Resto del país', '400')]

# Datos de cada tienda de demostracion. `productos` y `zonas` se cargan solo en esa tienda.
TIENDAS = [
    {
        'nombre': 'Multimix RD', 'prefijo': 'MMX', 'productos': PRODUCTOS, 'zonas': ZONAS, 'cupon': 'BIENVENIDO10',
        'cuenta': ('Banco Popular Dominicano', '812-345678-9', 'Multimix RD, SRL', '1-31-12345-6'),
        'datos': {
            'banner_titulo': 'Tu tienda de bienestar',
            'banner_subtitulo': 'Salud, belleza y equilibrio: vitaminas, cuidado personal y más, con entrega en todo el país.',
            'whatsapp': '18095550123', 'telefono': '809-555-0123', 'correo': 'ventas@multimixrd.com',
            'horario': 'Lunes a sábado, 9:00 a.m. a 6:00 p.m.',
            'direccion_tienda': 'Av. Winston Churchill #100, Plaza Central, local 12, Santo Domingo',
            'instagram': 'https://www.instagram.com/multimixrd',
            'facebook': 'https://www.facebook.com/multimixrd',
        },
        'pedidos': [
            ('María Rodríguez', '8095550101', [('TEC-001', 2), ('HOG-001', 1)], True, 'transferencia',
             ['pagado', 'enviado', 'entregado']),
            ('José Martínez', '8295550102', [('DEP-002', 3), ('TEC-001', 1)], False, 'efectivo_recoger',
             ['listo', 'entregado']),
            ('Carla Jiménez', '8495550103', [('MOD-001', 1), ('HOG-001', 2)], False, 'transferencia', ['pagado']),
            ('Luis Peña', '8095550104', [('JUG-002', 1), ('BEL-002', 2)], True, 'transferencia', []),
        ],
    },
    {
        'nombre': 'Rincón Fitness', 'prefijo': 'FIT', 'productos': PRODUCTOS_FITNESS, 'zonas': ZONAS_FITNESS,
        'cupon': 'FIT10', 'cuenta': ('Banreservas', '960-112233-4', 'Rincón Fitness', '402-1234567-8'),
        'datos': {
            'banner_subtitulo': 'Accesorios para entrenar en casa, con entrega desde Santiago.',
            'whatsapp': '18295550456', 'telefono': '829-555-0456', 'correo': 'hola@rinconfitness.example',
            'horario': 'Lunes a viernes, 10:00 a.m. a 7:00 p.m.',
            'direccion_tienda': 'Calle del Sol #45, Santiago de los Caballeros',
            'instagram': 'https://www.instagram.com/rinconfitness',
        },
        'pedidos': [
            ('Ana Gómez', '8095550201', [('FIT-001', 1), ('FIT-002', 2)], True, 'transferencia', ['pagado']),
        ],
    },
]


FUENTES = ['segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf', 'Arial Bold.ttf']


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

    fuente, con_tildes = cargar_fuente(lado // 13, FUENTES)
    renglones = textwrap.wrap(texto if con_tildes else quitar_tildes(texto), width=16)
    alto = fuente.size * 1.25
    y = (lado - alto * len(renglones)) / 2
    for renglon in renglones:
        ancho = dibujo.textlength(renglon, font=fuente)
        dibujo.text(((lado - ancho) / 2 + 3, y + 3), renglon, font=fuente, fill=(0, 0, 0, 70))
        dibujo.text(((lado - ancho) / 2, y), renglon, font=fuente, fill=(255, 255, 255, 255))
        y += alto
    if texto:
        marca, _ = cargar_fuente(lado // 30, FUENTES)
        dibujo.text((lado * 0.12, lado * 0.85), 'MULTIMIX RD - DEMO', font=marca, fill=(255, 255, 255, 190))

    salida = BytesIO()
    imagen.save(salida, 'PNG')
    salida.seek(0)
    return salida


class Command(BaseCommand):
    help = 'Crea dos tiendas de demostración con categorías, productos con imágenes, cupón, zonas, cuenta y pedidos.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.configuracion()
        categorias = self.categorias()
        creados = pedidos = 0
        # La primera tienda que exista (la que ya tenia el sitio) recibe el catalogo principal.
        existentes = [Tienda.objects.order_by('pk').first(), Tienda.objects.filter(prefijo='FIT').first()]
        for existente, demo in zip(existentes, TIENDAS):
            tienda = self.tienda(existente, demo)
            self.cuenta_y_zonas(tienda, demo)
            creados += self.productos(tienda, demo['productos'], categorias)
            Cupon.objects.get_or_create(tienda=tienda, codigo=demo['cupon'], defaults={
                'tipo': Cupon.Tipo.PORCENTAJE, 'valor': Decimal('10'), 'compra_minima': Decimal('1000'),
            })
            pedidos += self.pedidos(tienda, demo['pedidos'])
            cache.delete(clave_mas_vendidos(tienda))
        self.stdout.write(self.style.SUCCESS(
            f'Demo lista: {Tienda.objects.count()} tiendas, {len(categorias)} categorías, '
            f'{Producto.objects.count()} productos ({creados} nuevos), {pedidos} pedidos de ejemplo.'
        ))

    def configuracion(self):
        """Contactos del sitio. Completa solo lo que este vacio, para no pisar lo que ya ajusto el dueño."""
        config = ConfiguracionTienda.obtener()
        demo = {
            'whatsapp': '18095550123',
            'telefono': '809-555-0123',
            'correo': 'ventas@multimixrd.com',
            'horario': 'Lunes a sábado, 9:00 a.m. a 6:00 p.m.',
            'instagram': 'https://www.instagram.com/multimixrd',
            'facebook': 'https://www.facebook.com/multimixrd',
        }
        for campo, valor in demo.items():
            if not getattr(config, campo):
                setattr(config, campo, valor)
        config.save()

    def tienda(self, tienda, demo):
        """Crea la tienda de demostracion o completa los datos vacios de la que ya existe."""
        if tienda is None:
            return Tienda.objects.create(nombre=demo['nombre'], prefijo=demo['prefijo'], **demo['datos'])
        for campo, valor in demo['datos'].items():
            if not getattr(tienda, campo):
                setattr(tienda, campo, valor)
        tienda.save()
        return tienda

    def cuenta_y_zonas(self, tienda, demo):
        banco, numero, titular, documento = demo['cuenta']
        CuentaBancaria.objects.get_or_create(tienda=tienda, banco=banco, numero=numero, defaults={
            'tipo_cuenta': CuentaBancaria.Tipo.CORRIENTE, 'titular': titular, 'cedula_rnc': documento,
        })
        for orden, (nombre, tarifa) in enumerate(demo['zonas']):
            ZonaEnvio.objects.get_or_create(
                tienda=tienda, nombre=nombre, defaults={'tarifa': Decimal(tarifa), 'orden': orden},
            )

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

    def productos(self, tienda, productos, categorias):
        creados = 0
        ahora = timezone.now()
        for indice, (sku, cat, nombre, precio, oferta, stock, destacado, descripcion) in enumerate(productos):
            categoria, color_a, color_b = categorias[cat]
            producto, nuevo = Producto.objects.get_or_create(tienda=tienda, sku=sku, defaults={
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

    def pedidos(self, tienda, ejemplos):
        """Unos pedidos de ejemplo para que el panel y "Más vendidos" de la tienda tengan datos."""
        if Pedido.objects.filter(tienda=tienda).exists():
            return 0
        zona = ZonaEnvio.objects.filter(tienda=tienda).first()
        Entrega, Pago = Pedido.Entrega, Pedido.Pago
        for nombre, telefono, lineas, a_domicilio, pago, estados in ejemplos:
            carrito = Carrito(SimpleNamespace(session=SessionStore()), tienda)
            for sku, cantidad in lineas:
                carrito.agregar(Producto.objects.select_related('categoria').get(tienda=tienda, sku=sku), cantidad)
            pedido = crear_pedido(carrito, {
                'nombre': nombre, 'telefono': telefono, 'correo': '',
                'metodo_entrega': Entrega.ENVIO if a_domicilio else Entrega.RECOGER,
                'zona': zona if a_domicilio else None,
                'direccion': 'Calle Principal #25, Ensanche Naco' if a_domicilio else '',
                'referencia': 'Edificio azul, apto. 3B' if a_domicilio else '',
                'metodo_pago': pago, 'transferencia_realizada': not estados and pago == Pago.TRANSFERENCIA,
                'referencia_transferencia': '', 'notas': 'Pedido de demostración',
            })
            for estado in estados:
                pedido = cambiar_estado(pedido, estado)
        return len(ejemplos)
