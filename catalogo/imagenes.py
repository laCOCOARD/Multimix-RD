from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def convertir_a_webp(archivo, lado_maximo=None):
    """Redimensiona la imagen (sin ampliarla) y la devuelve como WebP."""
    lado = lado_maximo or settings.IMAGEN_LADO_MAXIMO
    archivo.seek(0)
    with Image.open(archivo) as original:
        imagen = ImageOps.exif_transpose(original)
        if imagen.mode not in ('RGB', 'RGBA'):
            tiene_alfa = imagen.mode in ('LA', 'PA') or 'transparency' in imagen.info
            imagen = imagen.convert('RGBA' if tiene_alfa else 'RGB')
        imagen.thumbnail((lado, lado), Image.Resampling.LANCZOS)
        salida = BytesIO()
        imagen.save(salida, 'WEBP', quality=85, method=4)
    return ContentFile(salida.getvalue())
