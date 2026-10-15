import re

from django import template
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Una linea corta al comienzo de un bloque, sin punto final, es su titulo ("3. Para que los usamos").
LARGO_MAXIMO_TITULO = 80


def _es_titulo(linea, hay_mas):
    return hay_mas and len(linea) <= LARGO_MAXIMO_TITULO and not linea.endswith(('.', ':', ';', ','))


@register.filter
def texto_legal(texto):
    """Texto simple de una pagina informativa con titulos, listas y parrafos.

    Bloques separados por una linea en blanco. Dentro de un bloque: la primera linea corta y sin punto es el
    titulo, las lineas que empiezan con "- " son una lista y las demas, parrafos. Todo se escapa: el texto
    nunca se interpreta como HTML.
    """
    partes = []
    for bloque in re.split(r'\n\s*\n', (texto or '').replace('\r\n', '\n').strip()):
        lineas = [linea.strip() for linea in bloque.split('\n') if linea.strip()]
        if lineas and _es_titulo(lineas[0], len(lineas) > 1):
            partes.append(format_html('<h2>{}</h2>', lineas.pop(0)))
        lista = []
        for linea in lineas + [None]:
            if linea is not None and linea.startswith('- '):
                lista.append(format_html('<li>{}</li>', linea[2:].strip()))
                continue
            if lista:
                partes.append(mark_safe('<ul>' + ''.join(lista) + '</ul>'))
                lista = []
            if linea is not None:
                partes.append(format_html('<p>{}</p>', linea))
    return mark_safe('\n'.join(conditional_escape(parte) for parte in partes))
