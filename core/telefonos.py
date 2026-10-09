"""Telefonos de Republica Dominicana: validacion y formato."""
import re

PREFIJOS_RD = ('809', '829', '849')
CODIGO_PAIS = '1'


def normalizar_telefono_rd(valor):
    """Devuelve el telefono como 10 digitos (8095551234) o lanza ValueError."""
    digitos = re.sub(r'\D', '', valor or '')
    if len(digitos) == 11 and digitos.startswith(CODIGO_PAIS):
        digitos = digitos[1:]
    if len(digitos) != 10 or not digitos.startswith(PREFIJOS_RD):
        raise ValueError('Escribe un teléfono dominicano válido (809, 829 o 849).')
    return digitos


def normalizar_whatsapp(valor):
    """Numero de WhatsApp solo con digitos y con codigo de pais, como lo pide wa.me.

    A un numero dominicano escrito con 10 digitos (829-555-1234) le antepone el 1: sin el,
    WhatsApp lo toma por un numero de otro pais y el enlace no abre el chat correcto.
    """
    digitos = re.sub(r'\D', '', valor or '')
    if len(digitos) == 10 and digitos.startswith(PREFIJOS_RD):
        digitos = CODIGO_PAIS + digitos
    return digitos


def formatear_telefono(telefono):
    """8095551234 -> 809-555-1234. Si no tiene 10 digitos lo devuelve igual."""
    if len(telefono or '') != 10:
        return telefono or ''
    return f'{telefono[:3]}-{telefono[3:6]}-{telefono[6:]}'


def telefono_internacional(telefono):
    """Formato que usa wa.me: codigo de pais + numero, solo digitos."""
    return f'{CODIGO_PAIS}{telefono}'
