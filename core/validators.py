from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

EXTENSIONES_IMAGEN = ('.jpg', '.jpeg', '.png', '.webp')

validar_whatsapp = RegexValidator(
    r'^\d{10,15}$',
    'Escribe solo dígitos, con el código de país. Ejemplo: 18095551234',
)


def validar_imagen(archivo):
    """Acepta JPG, PNG o WebP de hasta IMAGEN_MAX_BYTES."""
    if Path(archivo.name).suffix.lower() not in EXTENSIONES_IMAGEN:
        raise ValidationError('La imagen debe ser JPG, PNG o WebP.')
    if archivo.size > settings.IMAGEN_MAX_BYTES:
        megas = settings.IMAGEN_MAX_BYTES // (1024 * 1024)
        raise ValidationError(f'La imagen no puede pesar más de {megas} MB.')
