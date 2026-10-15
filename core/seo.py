"""Datos estructurados (JSON-LD) para buscadores. Solo se publica lo que es verdad en la base."""
import json

from django.utils.safestring import mark_safe

from catalogo.models import Disponibilidad

# Los mismos escapes que usa Django en `json_script`: el JSON no puede cerrar la etiqueta <script>.
_ESCAPES = {ord('>'): '\\u003E', ord('<'): '\\u003C', ord('&'): '\\u0026'}

DISPONIBILIDAD = {
    Disponibilidad.DISPONIBLE: 'https://schema.org/InStock',
    Disponibilidad.BAJO_PEDIDO: 'https://schema.org/BackOrder',
    Disponibilidad.AGOTADO: 'https://schema.org/OutOfStock',
    Disponibilidad.NO_DISPONIBLE: 'https://schema.org/OutOfStock',
}


def json_ld(datos):
    return mark_safe(json.dumps(datos, ensure_ascii=False).translate(_ESCAPES))


def producto_json_ld(producto, url, imagenes, resumen_resenas):
    """Producto con su oferta real. La valoracion solo va si hay reseñas publicadas."""
    datos = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': producto.nombre,
        'sku': producto.sku,
        'url': url,
        'category': producto.categoria.nombre,
        'offers': {
            '@type': 'Offer',
            'url': url,
            'priceCurrency': 'DOP',
            'price': f'{producto.precio_final:.2f}',
            'availability': DISPONIBILIDAD[producto.estado_venta],
            'seller': {'@type': 'Organization', 'name': producto.tienda.nombre},
        },
    }
    if producto.descripcion:
        datos['description'] = producto.descripcion[:5000]
    if producto.marca:
        datos['brand'] = {'@type': 'Brand', 'name': producto.marca}
    if imagenes:
        datos['image'] = imagenes
    if resumen_resenas.get('total'):
        datos['aggregateRating'] = {
            '@type': 'AggregateRating',
            'ratingValue': str(resumen_resenas['promedio']),
            'reviewCount': resumen_resenas['total'],
        }
    return json_ld(datos)


def sitio_json_ld(nombre, url_inicio, url_busqueda, logo=''):
    """El sitio y su buscador: Google puede mostrar una caja de busqueda bajo el resultado."""
    organizacion = {'@type': 'Organization', 'name': nombre, 'url': url_inicio}
    if logo:
        organizacion['logo'] = logo
    return json_ld({
        '@context': 'https://schema.org',
        '@graph': [
            organizacion,
            {
                '@type': 'WebSite',
                'name': nombre,
                'url': url_inicio,
                'potentialAction': {
                    '@type': 'SearchAction',
                    'target': {'@type': 'EntryPoint', 'urlTemplate': f'{url_busqueda}?q={{search_term_string}}'},
                    'query-input': 'required name=search_term_string',
                },
            },
        ],
    })


def ruta_json_ld(pasos):
    """Ruta de navegacion (BreadcrumbList) a partir de pares (nombre, url absoluta)."""
    return json_ld({
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': posicion, 'name': nombre, 'item': url}
            for posicion, (nombre, url) in enumerate(pasos, start=1)
        ],
    })
