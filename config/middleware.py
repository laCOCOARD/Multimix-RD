import logging

from django.conf import settings

from core.tareas import ejecutar_si_toca

logger = logging.getLogger('django.request')


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
        logger.error(
            'Unhandled exception while processing request.',
            exc_info=(type(exception), exception, exception.__traceback__),
        )
