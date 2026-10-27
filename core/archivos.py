from pathlib import Path
from uuid import uuid4

from django.utils.deconstruct import deconstructible

from .validators import EXTENSIONES_IMAGEN

try:  # botocore solo esta instalado donde las fotos van a Supabase (requirements-prod.txt).
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    ERRORES_DE_ALMACENAMIENTO = (OSError,)
else:
    ERRORES_DE_ALMACENAMIENTO = (OSError, BotoCoreError, ClientError)


@deconstructible
class NombreUnico:
    """`upload_to` que guarda la imagen como `<carpeta>/<32 letras y numeros>.<extension>`.

    El nombre original no se usa: Supabase rechaza los que traen tildes o ñ, y con uno que no se
    repite el almacenamiento no tiene que preguntar antes si el archivo ya existe.

    Con `extension` todos llevan esa: los videos se guardan como .mp4 aunque lleguen como .mov, para que el
    almacenamiento los sirva como video/mp4 (los MOV con H.264 se reproducen igual).
    """

    def __init__(self, carpeta, extension=None):
        self.carpeta = carpeta.strip('/')
        self.extension = extension

    def __call__(self, instancia, nombre):
        if self.extension is not None:
            extension = self.extension
        else:
            extension = Path(nombre).suffix.lower()
            if extension not in EXTENSIONES_IMAGEN:
                extension = ''
        return f'{self.carpeta}/{uuid4().hex}{extension}'


def almacenamiento_privado():
    """Donde van los archivos que no deben ser publicos (comprobantes de pago). Ver STORAGES['privado']."""
    from django.core.files.storage import storages

    return storages['privado']


def almacenamiento_de_videos():
    """Donde van los videos de las tiendas: un bucket publico que acepte videos. Ver STORAGES['videos']."""
    from django.core.files.storage import storages

    return storages['videos']


def hay_almacenamiento_privado():
    """False si 'privado' es el mismo almacenamiento publico (falta configurar el bucket privado)."""
    from django.conf import settings

    return settings.STORAGES['privado'] is not settings.STORAGES['default']
