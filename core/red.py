import logging
from ipaddress import ip_address

from django.conf import settings

logger = logging.getLogger('multimix')
_aviso_dado = False


def _ip_valida(valor):
    try:
        return str(ip_address((valor or '').strip()))
    except ValueError:
        return None


def ip_del_cliente(request):
    """IP de quien visita, para los limites anti-abuso. None si no se puede saber con certeza.

    Detras de un proxy solo se lee la cabecera que el proxy escribe en cada visita (`settings.CABECERA_IP`), nunca
    la primera de `X-Forwarded-For`: Render le agrega al final la que recibe y deja lo que el visitante haya puesto
    delante, asi que cualquiera podia inventarse una IP nueva en cada intento.
    """
    if not settings.CONFIAR_IP_PROXY:
        return _ip_valida(request.META.get('REMOTE_ADDR'))
    ip = _ip_valida(request.META.get(settings.CABECERA_IP))
    if ip is None:
        # Sin la cabecera no se limita por IP (los limites por cuenta siguen); tiene que quedar a la vista.
        global _aviso_dado
        if not _aviso_dado:
            _aviso_dado = True
            logger.warning('La visita no trae la IP en %s: los limites por IP no se aplican', settings.CABECERA_IP)
    return ip
