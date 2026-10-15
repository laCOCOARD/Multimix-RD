from django.conf import settings

from carrito.carrito import cantidad_en_sesion
from catalogo.services import categorias_de
from pedidos.whatsapp import construir_enlace

from .models import ConfiguracionTienda, contenido_del_pie


PAGINAS_LEGALES = {'privacidad', 'garantias', 'contacto'}


def tienda(request):
    """Datos comunes de las plantillas.

    `tienda` es la subtienda en la que esta el visitante (la pone @de_tienda en `request.tienda`) o
    None en las paginas del sitio. `marca` es de quien se muestran el nombre, el logo y los contactos.
    """
    plataforma = ConfiguracionTienda.obtener()
    pie = contenido_del_pie()
    actual = getattr(request, 'tienda', None)
    marca = actual or plataforma
    contexto = {
        'plataforma': plataforma,
        'tienda': actual,
        'marca': marca,
        'categorias_menu': (),
        'carrito_cantidad': 0,
        'enlace_whatsapp_tienda': '',
        'contenido_pie': pie,
        # El pie separa la ayuda de los textos legales; la portada enlaza solo las politicas publicadas.
        'paginas_ayuda': [p for p in pie['paginas'] if p['slug'] not in PAGINAS_LEGALES],
        'paginas_legales': [p for p in pie['paginas'] if p['slug'] in PAGINAS_LEGALES],
        'paginas_publicadas': {p['slug'] for p in pie['paginas']},
        # Sin sesion (pagina de entrar, enlace de un pedido) el menu, el buscador y el carrito llevarian a entrar.
        'puede_navegar': not settings.CUENTA_OBLIGATORIA or getattr(getattr(request, 'user', None), 'is_authenticated', False),
    }
    if marca.whatsapp:
        saludo = f'Hola, les escribo desde la tienda en línea de {marca.nombre}.'
        contexto['enlace_whatsapp_tienda'] = construir_enlace(marca.whatsapp, saludo)
    if actual is not None:
        # QuerySet perezoso: solo consulta si la plantilla lo recorre.
        contexto['categorias_menu'] = categorias_de(actual)
        if hasattr(request, 'session'):
            contexto['carrito_cantidad'] = cantidad_en_sesion(request.session, actual)
    return contexto
