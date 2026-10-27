from django.conf import settings
from django.utils.functional import SimpleLazyObject

from carrito.carrito import cantidad_en_sesion
from catalogo.services import categorias_de, categorias_del_menu
from pedidos.whatsapp import construir_enlace
from tiendas.services import como_vender

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
    usuario = getattr(request, 'user', None)
    contexto = {
        # Los productos que el cliente guardo, para el corazon de las tarjetas. Solo consulta si la pagina las muestra.
        'favoritos_ids': SimpleLazyObject(lambda: _favoritos_de(usuario)),
        'plataforma': plataforma,
        'tienda': actual,
        'marca': marca,
        'categorias_menu': (),
        'carrito_cantidad': 0,
        'enlace_whatsapp_tienda': '',
        'vender': None,
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
    else:
        # En las paginas del sitio: las categorias de todas las tiendas (llevan al buscador del sitio) y a donde
        # escribe quien quiere vender aqui.
        contexto['categorias_menu'] = categorias_del_menu()
        contexto['vender'] = como_vender(plataforma, contexto['paginas_publicadas'])
    return contexto


def _favoritos_de(usuario):
    if not getattr(usuario, 'is_authenticated', False):
        return frozenset()
    from clientes.models import Favorito

    return frozenset(Favorito.objects.filter(usuario=usuario).values_list('producto_id', flat=True))
