from carrito.carrito import cantidad_en_sesion
from catalogo.services import categorias_de
from pedidos.whatsapp import construir_enlace

from .models import ConfiguracionTienda


def tienda(request):
    """Datos comunes de las plantillas.

    `tienda` es la subtienda en la que esta el visitante (la pone @de_tienda en `request.tienda`) o
    None en las paginas del sitio. `marca` es de quien se muestran el nombre, el logo y los contactos.
    """
    plataforma = ConfiguracionTienda.obtener()
    actual = getattr(request, 'tienda', None)
    marca = actual or plataforma
    contexto = {
        'plataforma': plataforma,
        'tienda': actual,
        'marca': marca,
        'categorias_menu': (),
        'carrito_cantidad': 0,
        'enlace_whatsapp_tienda': '',
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
