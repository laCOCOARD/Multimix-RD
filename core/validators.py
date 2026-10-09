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
