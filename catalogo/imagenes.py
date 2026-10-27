from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image

from core.validators import maximo_de_pixeles

# Miniatura de las fotos de producto (Fase 4, 2026-10-27): las tarjetas miden unos 250 px; 480 px se ven nitidas en
# pantallas de doble densidad y pesan una fraccion de la foto de 1200 px.
LADO_MINIATURA = 480

# Giro que pide la etiqueta Orientation (0x0112) del EXIF; lo mismo que hace ImageOps.exif_transpose.
_GIROS = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def convertir_a_webp(archivo, lado_maximo=None):
    """Redimensiona la imagen (sin ampliarla) y la devuelve como WebP.

    Se achica antes de girarla, para tener en memoria una sola copia grande. Un JPG se lee ya reducido (`draft`):
    asi una foto de 50 megapixeles no pasa de unos pocos MB de memoria. Las demasiado grandes las rechaza antes
    `core.validators.validar_pixeles`; por si llega una por otro camino, aqui se comprueba otra vez.
    """
    lado = lado_maximo or settings.IMAGEN_LADO_MAXIMO
    archivo.seek(0)
    with Image.open(archivo) as original:
        ancho, alto = original.size
        if ancho * alto > maximo_de_pixeles(original.format):
            raise ValueError(f'Imagen demasiado grande: {ancho} x {alto} pixeles')
        orientacion = original.getexif().get(0x0112)
        original.draft('RGB', (lado, lado))
        imagen = original
        if imagen.mode not in ('RGB', 'RGBA'):
            tiene_alfa = imagen.mode in ('LA', 'PA') or 'transparency' in imagen.info
            imagen = imagen.convert('RGBA' if tiene_alfa else 'RGB')
        imagen.thumbnail((lado, lado), Image.Resampling.LANCZOS)
        if orientacion in _GIROS:
            imagen = imagen.transpose(_GIROS[orientacion])
        salida = BytesIO()
        imagen.save(salida, 'WEBP', quality=85, method=4)
    return ContentFile(salida.getvalue())
