from django.urls import reverse

from tiendas.models import Tienda

TIENDA_POR_DEFECTO = 'Multimix RD'


def tienda_de_prueba(nombre=TIENDA_POR_DEFECTO, **datos):
    """Tienda con ese nombre; se crea la primera vez. Sin nombre es la tienda en la que corren casi todas las pruebas."""
    valores = {'prefijo': 'MMX', 'banner_titulo': 'Tu tienda de bienestar'} if nombre == TIENDA_POR_DEFECTO else {}
    valores.update(datos)
    return Tienda.objects.get_or_create(nombre=nombre, defaults=valores)[0]


def ruta(nombre, *args, tienda=None):
    """`reverse` de una ruta que vive dentro de una tienda; por defecto, la tienda de prueba."""
    return reverse(nombre, args=[(tienda or tienda_de_prueba()).slug, *args])
