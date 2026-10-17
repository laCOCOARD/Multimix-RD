from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

EXTENSIONES_IMAGEN = ('.jpg', '.jpeg', '.png', '.webp')

# Se valida ya normalizado (core.telefonos.normalizar_whatsapp): solo digitos, con codigo de pais.
validar_whatsapp = RegexValidator(
    r'^\d{10,15}$',
    'Escribe el número completo, con su código de área. Ejemplo: 829-555-1234',
)


def validar_imagen(archivo):
    """Acepta JPG, PNG o WebP de hasta IMAGEN_MAX_BYTES."""
    if Path(archivo.name).suffix.lower() not in EXTENSIONES_IMAGEN:
        raise ValidationError('La imagen debe ser JPG, PNG o WebP.')
    if archivo.size > settings.IMAGEN_MAX_BYTES:
        megas = settings.IMAGEN_MAX_BYTES // (1024 * 1024)
        raise ValidationError(f'La imagen no puede pesar más de {megas} MB.')
    validar_pixeles(archivo)


def maximo_de_pixeles(formato):
    return settings.IMAGEN_MAX_PIXELES_JPEG if formato == 'JPEG' else settings.IMAGEN_MAX_PIXELES


def validar_pixeles(archivo):
    """Rechaza las imagenes con demasiados pixeles. Lee solo la cabecera, sin abrir la imagen entera.

    Un PNG de pocos MB puede tener cientos de millones de pixeles: al convertirlo ocuparia mas memoria de la que
    tiene el servidor (512 MB en Render free) y lo tumbaria.
    """
    from PIL import Image

    try:
        archivo.seek(0)
        with Image.open(archivo) as imagen:
            ancho, alto = imagen.size
            formato = imagen.format
    except Exception:
        # Que no sea una imagen lo dice ImageField; este validador solo mide.
        return
    finally:
        archivo.seek(0)
    limite = maximo_de_pixeles(formato)
    if ancho * alto > limite:
        maximo = limite // 1_000_000
        raise ValidationError(
            f'La imagen es demasiado grande ({ancho} × {alto} píxeles). Usa una de hasta {maximo} megapíxeles.'
        )
