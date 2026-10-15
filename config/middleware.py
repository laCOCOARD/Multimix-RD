import logging

from django.conf import settings
from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.core.exceptions import PermissionDenied
from django.http import Http404

from core.tareas import ejecutar_si_toca

logger = logging.getLogger('django.request')


class CuentaObligatoriaMiddleware(LoginRequiredMiddleware):
    """Para entrar al sitio hay que iniciar sesion. Las vistas abiertas llevan `@login_not_required`: entrar,
    crear cuenta, recuperar la contraseña, las politicas, las paginas por token del pedido y lo tecnico."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not settings.CUENTA_OBLIGATORIA:
            return None
        return super().process_view(request, view_func, view_args, view_kwargs)


class TareasPeriodicasMiddleware:
    """Como mucho una vez por hora, una visita dispara el mantenimiento (ver core/tareas.py)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        ejecutar_si_toca()
        return respuesta


class PoliticaDeContenidoMiddleware:
    """Cabecera Content-Security-Policy: de donde puede cargar el sitio scripts, estilos, fuentes e imagenes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        respuesta.headers.setdefault('Content-Security-Policy', settings.POLITICA_DE_CONTENIDO)
        return respuesta


class ExcepcionRequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Una pagina que no existe o un acceso denegado no son fallos del sitio.
        if isinstance(exception, (Http404, PermissionDenied)):
            return
        logger.error(
            'Unhandled exception while processing request.',
            exc_info=(type(exception), exception, exception.__traceback__),
        )
