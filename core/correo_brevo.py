"""Envio de correos por la API de Brevo (HTTPS).

El plan gratis de Render corta las conexiones SMTP salientes: el correo por SMTP se queda esperando hasta
agotar el tiempo. La API va por el puerto 443, que no se bloquea. Se activa con `BREVO_API_KEY`.
"""
import json
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

URL_DE_ENVIO = 'https://api.brevo.com/v3/smtp/email'


class BrevoBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        enviados = 0
        for mensaje in email_messages or []:
            if self._enviar(mensaje):
                enviados += 1
        return enviados

    def _enviar(self, mensaje):
        nombre, correo = parseaddr(mensaje.from_email)
        remitente = {'email': correo}
        if nombre:
            remitente['name'] = nombre
        cuerpo = {
            'sender': remitente,
            'to': [{'email': destino} for destino in mensaje.to],
            'subject': mensaje.subject,
            'textContent': mensaje.body,
        }
        peticion = urllib.request.Request(
            URL_DE_ENVIO, data=json.dumps(cuerpo).encode('utf-8'), method='POST',
            headers={
                'api-key': settings.BREVO_API_KEY, 'content-type': 'application/json', 'accept': 'application/json',
            },
        )
        try:
            with urllib.request.urlopen(peticion, timeout=settings.EMAIL_TIMEOUT) as respuesta:
                respuesta.read()
        except urllib.error.HTTPError as error:
            if self.fail_silently:
                return False
            # El cuerpo dice por que lo rechazo (clave invalida, remitente sin verificar...). No trae la clave.
            detalle = error.read().decode('utf-8', errors='replace')[:300]
            raise OSError(f'Brevo respondió {error.code}: {detalle}') from error
        except OSError:
            if self.fail_silently:
                return False
            raise
        return True
