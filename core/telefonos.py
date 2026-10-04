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


def formatear_telefono(telefono):
    """8095551234 -> 809-555-1234. Si no tiene 10 digitos lo devuelve igual."""
    if len(telefono or '') != 10:
        return telefono or ''
    return f'{telefono[:3]}-{telefono[3:6]}-{telefono[6:]}'


def telefono_internacional(telefono):
    """Formato que usa wa.me: codigo de pais + numero, solo digitos."""
    return f'{CODIGO_PAIS}{telefono}'
