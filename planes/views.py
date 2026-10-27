from django.http import HttpResponse
from django.views.decorators.http import require_POST

from . import services


@require_POST
def vista_de_video(request, pk):
    """El visor de videos avisa cuando uno empieza a reproducirse: suma una vista (una por persona)."""
    services.contar_vista(pk, request.session)
    return HttpResponse(status=204)
