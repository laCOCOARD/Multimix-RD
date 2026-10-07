"""Fuentes para las imagenes que genera el sitio (facturas e imagenes de demostracion)."""
from PIL import ImageFont


def cargar_fuente(tamano, nombres):
    """Devuelve (fuente, tiene_tildes): la primera fuente instalada de `nombres` o, si no hay ninguna, la de Pillow.

    La fuente incluida en Pillow no trae letras acentuadas; con ella hay que escribir sin tildes
    para que no salgan recuadros en su lugar.
    """
    for nombre in nombres:
        try:
            return ImageFont.truetype(nombre, tamano), True
        except OSError:
            continue
    return ImageFont.load_default(size=tamano), False
