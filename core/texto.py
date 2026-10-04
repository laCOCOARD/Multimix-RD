import unicodedata


def quitar_tildes(texto):
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar(texto):
    """Minusculas y sin tildes: 'Audífonos Pro' -> 'audifonos pro'. Sirve para buscar."""
    return quitar_tildes(texto).lower().strip()
