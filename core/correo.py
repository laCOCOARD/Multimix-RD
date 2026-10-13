"""Envio de correos. Un correo que falla nunca tumba una compra: se registra y la pagina sigue."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger('multimix.correo')


def url_absoluta(ruta):
    """Enlace completo para un correo, que no tiene una peticion de donde sacar el dominio."""
    return f'{settings.SITIO_URL}{ruta}'


def enviar(asunto, plantilla, contexto, destinatarios):
    """Envia un correo de texto con la plantilla `correos/<plantilla>.txt`. Devuelve True si salio."""
    destinatarios = [correo for correo in dict.fromkeys(destinatarios) if correo]
    if not destinatarios:
        return False
    cuerpo = render_to_string(f'correos/{plantilla}.txt', contexto)
    try:
        send_mail(asunto, cuerpo, None, destinatarios)
    except Exception:
        # El proveedor puede fallar de muchas formas (red, credenciales, limite diario).
        logger.exception('No se pudo enviar el correo "%s"', asunto)
        return False
    return True
