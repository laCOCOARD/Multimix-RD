import unicodedata

from django.utils.text import slugify


def quitar_tildes(texto):
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar(texto):
    """Minusculas y sin tildes: 'Audífonos Pro' -> 'audifonos pro'. Sirve para buscar."""
    return quitar_tildes(texto).lower().strip()


def generar_slug_unico(instancia, texto, largo=140, **ambito):
    """Slug a partir del texto; agrega -2, -3... si ya existe en el modelo.

    `ambito` limita donde se busca el repetido (por ejemplo `tienda=...`).
    """
    base = slugify(texto)[:largo] or 'item'
    slug = base
    existentes = type(instancia).objects.filter(**ambito).exclude(pk=instancia.pk)
    numero = 2
    while existentes.filter(slug=slug).exists():
        sufijo = f'-{numero}'
        slug = f'{base[:largo - len(sufijo)]}{sufijo}'
        numero += 1
    return slug
