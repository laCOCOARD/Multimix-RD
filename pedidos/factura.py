"""Generación de la imagen de comprobante del pedido."""
from io import BytesIO
from textwrap import wrap

import qrcode
from PIL import Image, ImageDraw
from django.utils import timezone

from core.fuentes import cargar_fuente
from core.templatetags.moneda import formatear_monto
from core.texto import quitar_tildes


# Fuentes del sistema que si traen tildes; si no hay ninguna se usa la de Pillow y se escribe sin ellas.
FUENTES = ['segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf', 'LiberationSans-Regular.ttf', 'Arial.ttf']

ANCHO = 900
MARGEN = 56
COLOR_TINTA = '#0b2239'
COLOR_AZUL = '#0f4c81'
COLOR_SUAVE = '#5b6b7c'
COLOR_BORDE = '#e3e8ee'


def sin_tildes(texto):
    return quitar_tildes(str(texto)).replace('×', 'x')


class _DibujoSinTildes:
    """Envuelve a ImageDraw para escribir sin tildes cuando la fuente no las trae."""

    def __init__(self, dibujo):
        self._dibujo = dibujo

    def __getattr__(self, nombre):
        return getattr(self._dibujo, nombre)

    def text(self, xy, texto, **opciones):
        return self._dibujo.text(xy, sin_tildes(texto), **opciones)

    def textlength(self, texto, **opciones):
        return self._dibujo.textlength(sin_tildes(texto), **opciones)


def _texto_envuelto(dibujo, texto, xy, fuente, ancho_maximo, color, interlineado=8):
    lineas = []
    linea = ''
    for palabra in str(texto).split():
        candidata = f'{linea} {palabra}'.strip()
        if linea and dibujo.textlength(candidata, font=fuente) > ancho_maximo:
            lineas.append(linea)
            linea = palabra
        else:
            linea = candidata
    if linea:
        lineas.append(linea)

    x, y = xy
    alto_linea = fuente.getbbox('Ag')[3] + interlineado
    for linea in lineas:
        dibujo.text((x, y), linea, font=fuente, fill=color)
        y += alto_linea
    return y


def generar_imagen_factura(pedido, nombre_tienda, url_verificacion):
    fuente_normal, con_tildes = cargar_fuente(23, FUENTES)
    fuente_pequena, fuente_seccion, fuente_titulo, fuente_total = (
        cargar_fuente(tamano, FUENTES)[0] for tamano in (18, 28, 48, 34)
    )

    renglones = []
    for detalle in pedido.detalles.all():
        nombre = f'{detalle.cantidad} × {detalle.nombre_producto}'
        renglones.append((detalle, wrap(nombre, width=44, break_long_words=True)))

    alto_fila = fuente_normal.getbbox('Ag')[3] + 10
    alto_tabla = sum(max(1, len(palabras)) * alto_fila + 20 for _, palabras in renglones)
    alto = 1120 + alto_tabla
    imagen = Image.new('RGB', (ANCHO, alto), '#f5f7fa')
    dibujo = ImageDraw.Draw(imagen)
    if not con_tildes:
        dibujo = _DibujoSinTildes(dibujo)

    dibujo.rectangle((0, 0, ANCHO, 185), fill=COLOR_TINTA)
    dibujo.text((MARGEN, 28), nombre_tienda, font=fuente_seccion, fill='#ffffff')
    dibujo.text((MARGEN, 76), 'FACTURA', font=fuente_titulo, fill='#ffffff')
    dibujo.text((MARGEN, 140), 'COMPROBANTE DE PEDIDO · NO ES COMPROBANTE FISCAL',
                font=fuente_pequena, fill='#dce7f1')

    dibujo.text((MARGEN, 218), f'Pedido {pedido.numero}', font=fuente_seccion, fill=COLOR_TINTA)
    estado = pedido.get_estado_display()
    dibujo.text((MARGEN, 262), f'Estado: {estado}', font=fuente_normal, fill=COLOR_AZUL)
    fecha = timezone.localtime(pedido.creado).strftime('%d/%m/%Y %H:%M')
    dibujo.text((ANCHO - MARGEN, 225), fecha, font=fuente_pequena, fill=COLOR_SUAVE, anchor='ra')

    dibujo.rounded_rectangle((MARGEN, 310, ANCHO - MARGEN, 405), radius=14,
                             fill='#ffffff', outline=COLOR_BORDE, width=2)
    dibujo.text((MARGEN + 22, 328), 'Cliente', font=fuente_pequena, fill=COLOR_SUAVE)
    _texto_envuelto(dibujo, pedido.nombre, (MARGEN + 22, 358), fuente_normal,
                    ANCHO - 2 * MARGEN - 44, COLOR_TINTA)

    y = 445
    dibujo.text((MARGEN, y), 'Detalle del pedido', font=fuente_seccion, fill=COLOR_TINTA)
    y += 48
    dibujo.text((MARGEN, y), 'Producto', font=fuente_pequena, fill=COLOR_SUAVE)
    dibujo.text((ANCHO - MARGEN, y), 'Importe', font=fuente_pequena, fill=COLOR_SUAVE, anchor='ra')
    y += 32
    dibujo.line((MARGEN, y, ANCHO - MARGEN, y), fill=COLOR_BORDE, width=2)
    y += 16

    for detalle, palabras in renglones:
        inicio_y = y
        y = _texto_envuelto(
            dibujo, ' '.join(palabras), (MARGEN, y), fuente_normal, 610, COLOR_TINTA,
        )
        dibujo.text((ANCHO - MARGEN, inicio_y), formatear_monto(detalle.subtotal),
                    font=fuente_normal, fill=COLOR_TINTA, anchor='ra')
        y += 20

    y += 10
    dibujo.line((MARGEN, y, ANCHO - MARGEN, y), fill=COLOR_BORDE, width=2)
    y += 24
    envio_texto = 'Gratis' if pedido.recoge_en_tienda else formatear_monto(pedido.costo_envio)
    totales = [
        ('Subtotal', formatear_monto(pedido.subtotal)),
    ]
    if pedido.descuento:
        totales.append((f'Cupón {pedido.codigo_cupon}'.strip(), f'-{formatear_monto(pedido.descuento)}'))
    totales.extend([
        ('Envío' if not pedido.recoge_en_tienda else 'Recogida en tienda', envio_texto),
        ('Total', formatear_monto(pedido.total)),
    ])
    for etiqueta, valor in totales:
        fuente = fuente_total if etiqueta == 'Total' else fuente_normal
        color = COLOR_AZUL if etiqueta == 'Total' else COLOR_TINTA
        dibujo.text((MARGEN, y), etiqueta, font=fuente, fill=color)
        dibujo.text((ANCHO - MARGEN, y), valor, font=fuente, fill=color, anchor='ra')
        y += fuente.getbbox('Ag')[3] + 16

    y += 10
    dibujo.line((MARGEN, y, ANCHO - MARGEN, y), fill=COLOR_BORDE, width=2)
    y += 26
    entrega = pedido.get_metodo_entrega_display()
    if not pedido.recoge_en_tienda and pedido.zona:
        entrega = f'{entrega} · {pedido.zona.nombre}'
    dibujo.text((MARGEN, y), f'Entrega: {entrega}', font=fuente_pequena, fill=COLOR_SUAVE)
    y += 30
    dibujo.text((MARGEN, y), f'Pago: {pedido.get_metodo_pago_display()}',
                font=fuente_pequena, fill=COLOR_SUAVE)
    y += 44

    codigo = qrcode.QRCode(box_size=6, border=2)
    codigo.add_data(url_verificacion)
    codigo.make(fit=True)
    imagen_qr = codigo.make_image(fill_color=COLOR_TINTA, back_color='#ffffff').convert('RGB')
    imagen_qr.thumbnail((190, 190))
    dibujo.rounded_rectangle((MARGEN, y, ANCHO - MARGEN, y + 226), radius=14,
                             fill='#ffffff', outline=COLOR_BORDE, width=2)
    imagen.paste(imagen_qr, (MARGEN + 18, y + 18))
    dibujo.text((MARGEN + 230, y + 30), 'Verifica este pedido', font=fuente_seccion, fill=COLOR_TINTA)
    _texto_envuelto(
        dibujo,
        'Escanea el código para confirmar el número, el total y el estado actual del pedido. '
        'El QR no confirma que el pago fue recibido.',
        (MARGEN + 230, y + 76),
        fuente_pequena,
        ANCHO - 2 * MARGEN - 250,
        COLOR_SUAVE,
        interlineado=7,
    )
    dibujo.text((MARGEN, y + 246), 'Gracias por comprar en nuestra tienda.',
                font=fuente_pequena, fill=COLOR_SUAVE)

    salida = BytesIO()
    imagen.save(salida, format='PNG', optimize=True)
    return salida.getvalue()
