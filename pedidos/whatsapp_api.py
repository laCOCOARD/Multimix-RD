"""Avisos automaticos por WhatsApp con la API oficial de Meta (WhatsApp Cloud API). Ver docs/WHATSAPP.md.

Apagado mientras no esten `WHATSAPP_TOKEN` y `WHATSAPP_NUMERO_ID`. WhatsApp solo deja que una empresa escriba
primero con una plantilla aprobada por Meta, y solo a quien acepto recibir mensajes: el cliente lo marca en el
checkout (`Pedido.avisos_whatsapp`). Como los correos, un envio que falla nunca tumba la pagina: se registra.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

from core.correo import url_absoluta
from core.telefonos import telefono_internacional

logger = logging.getLogger('multimix.whatsapp')

VERSION_API = 'v21.0'


def configurado():
    return bool(settings.WHATSAPP_TOKEN and settings.WHATSAPP_NUMERO_ID)


def parametros_del_estado(pedido):
    """Las variables de la plantilla, en orden: {{1}} nombre, {{2}} numero de pedido, {{3}} estado, {{4}} enlace."""
    return [
        pedido.nombre.split()[0] if pedido.nombre.split() else 'Cliente',
        pedido.numero,
        pedido.get_estado_display().lower(),
        url_absoluta(pedido.get_absolute_url()),
    ]


def enviar_estado(pedido):
    """Envia la plantilla del estado del pedido al telefono del cliente. Devuelve True si Meta la acepto."""
    if not configurado() or not pedido.avisos_whatsapp or not pedido.telefono:
        return False
    cuerpo = {
        'messaging_product': 'whatsapp',
        'to': telefono_internacional(pedido.telefono),
        'type': 'template',
        'template': {
            'name': settings.WHATSAPP_PLANTILLA,
            'language': {'code': settings.WHATSAPP_IDIOMA},
            'components': [{
                'type': 'body',
                'parameters': [{'type': 'text', 'text': texto} for texto in parametros_del_estado(pedido)],
            }],
        },
    }
    peticion = urllib.request.Request(
        f'https://graph.facebook.com/{VERSION_API}/{settings.WHATSAPP_NUMERO_ID}/messages',
        data=json.dumps(cuerpo).encode('utf-8'), method='POST',
        headers={'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            respuesta.read()
    except urllib.error.HTTPError as error:
        # El cuerpo dice por que lo rechazo (plantilla sin aprobar, numero sin WhatsApp...). No trae el token.
        detalle = error.read().decode('utf-8', errors='replace')[:300]
        logger.error('WhatsApp rechazó el aviso del pedido %s (%s): %s', pedido.numero, error.code, detalle)
        return False
    except OSError:
        logger.exception('No se pudo enviar el aviso de WhatsApp del pedido %s', pedido.numero)
        return False
    logger.info('Aviso de WhatsApp enviado: pedido %s, %s', pedido.numero, pedido.estado)
    return True
