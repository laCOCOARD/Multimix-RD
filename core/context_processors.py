from carrito.carrito import cantidad_en_sesion
from catalogo.models import Categoria
from pedidos.whatsapp import construir_enlace

from .models import ConfiguracionTienda


def tienda(request):
    config = ConfiguracionTienda.obtener()
    saludo = f'Hola, les escribo desde la tienda en línea de {config.nombre}.'
    return {
        'tienda': config,
        # QuerySet perezoso: solo consulta si la plantilla lo recorre (el panel no lo usa).
        'categorias_menu': Categoria.objects.filter(activa=True),
        'carrito_cantidad': cantidad_en_sesion(request.session) if hasattr(request, 'session') else 0,
        'enlace_whatsapp_tienda': construir_enlace(config.whatsapp, saludo) if config.whatsapp else '',
    }
