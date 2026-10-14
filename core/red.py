import os
from ipaddress import ip_address

from django.conf import settings


def ip_del_cliente(request):
    """IP de quien visita, para los limites anti-abuso. None si no se puede saber con certeza."""
    if settings.CONFIAR_IP_PROXY:
        candidatos = [
            request.META.get('HTTP_X_REAL_IP', '').strip(),
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip(),
        ]
        for candidato in candidatos:
            try:
                return str(ip_address(candidato))
            except ValueError:
                continue

        # Render may expose the client IP only through its forwarded headers.
        # Never rate-limit every visitor together by the platform proxy address.
        if os.getenv('RENDER_EXTERNAL_HOSTNAME'):
            return None

    try:
        return str(ip_address(request.META.get('REMOTE_ADDR', '')))
    except ValueError:
        return None
