from functools import wraps

from django.shortcuts import get_object_or_404

from .models import Tienda

# Prefijo de todas las rutas que viven dentro de una tienda. Sus vistas llevan @de_tienda.
RUTA_DE_TIENDA = 'tienda/<slug:tienda_slug>/'


def de_tienda(vista):
    """Para las vistas que viven dentro de una tienda (RUTA_DE_TIENDA).

    Deja la tienda en `request.tienda` y responde 404 si no existe o esta apagada.
    La vista ya no recibe `tienda_slug`.
    """
    @wraps(vista)
    def envoltura(request, tienda_slug, *args, **kwargs):
        request.tienda = get_object_or_404(Tienda.objects.activas(), slug=tienda_slug)
        return vista(request, *args, **kwargs)
    return envoltura
