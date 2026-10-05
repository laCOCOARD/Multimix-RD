import logging

logger = logging.getLogger('django.request')


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
