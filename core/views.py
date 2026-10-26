import hashlib

from django.contrib.auth.decorators import login_not_required
from django.http import Http404, JsonResponse
from django.templatetags.static import static
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from pedidos.services import zonas_activas
from tiendas.decoradores import de_tienda

from .models import ConfiguracionTienda, PaginaInformativa, PreguntaFrecuente


@require_GET
@de_tienda
def envios(request):
    return render(request, 'paginas/envios.html', {'zonas': zonas_activas(request.tienda)})


@login_not_required
@require_GET
def terminos(request):
    return render(request, 'paginas/terminos.html')


@login_not_required
@require_GET
def salud(request):
    """Para el monitor de Render: responde 200 solo si la aplicacion y la base de datos funcionan."""
    from django.db import connection
    from django.http import HttpResponse

    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return HttpResponse('ok', content_type='text/plain')


@login_not_required
@require_GET
def pagina(request, slug):
    """Pagina informativa. Sin publicar solo la ve el administrador principal, como vista previa."""
    item = get_object_or_404(PaginaInformativa, slug=slug)
    if not item.publicada and not request.user.is_superuser:
        raise Http404
    return render(request, 'paginas/pagina.html', {'pagina': item})


@login_not_required
@require_GET
def preguntas(request):
    activas = PreguntaFrecuente.objects.filter(activa=True)
    if not activas.exists():
        raise Http404
    return render(request, 'paginas/preguntas.html', {'preguntas': activas})


@login_not_required
@require_GET
@cache_control(max_age=3600, public=True)
def robots_txt(request):
    return render(request, 'robots.txt', {
        'sitemap': request.build_absolute_uri(reverse('sitemap')),
    }, content_type='text/plain; charset=utf-8')


# --- App instalable (PWA) ----------------------------------------------------------------
# El manifiesto y el service worker van en la raiz del sitio: el service worker solo controla las paginas que
# estan dentro de la carpeta desde la que se sirve, y /static/ no alcanzaria a la tienda.

@login_not_required
@require_GET
@cache_control(max_age=3600, public=True)
def manifiesto(request):
    plataforma = ConfiguracionTienda.obtener()
    icono = lambda nombre, tamano, uso='any': {  # noqa: E731
        'src': static(f'img/{nombre}'), 'sizes': tamano, 'type': 'image/png', 'purpose': uso,
    }
    datos = {
        'name': plataforma.nombre,
        'short_name': plataforma.nombre[:12],
        'description': plataforma.descripcion,
        'lang': 'es-DO',
        'dir': 'ltr',
        'id': '/',
        'start_url': '/?origen=app',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#ffffff',
        'categories': ['shopping'],
        'icons': [
            icono('icono-192.png', '192x192'), icono('icono-512.png', '512x512'),
            icono('icono-maskable-512.png', '512x512', 'maskable'),
        ],
        'shortcuts': [
            {'name': 'Mis pedidos', 'url': reverse('clientes:cuenta')},
            {'name': 'Mis favoritos', 'url': reverse('clientes:favoritos')},
            {'name': 'Buscar productos', 'url': reverse('tiendas:buscar')},
        ],
    }
    return JsonResponse(datos, content_type='application/manifest+json', json_dumps_params={'ensure_ascii': False})


def version_de_los_estaticos():
    """Cambia cuando cambia un estatico (sus nombres llevan el hash en produccion): asi la app renueva su cache."""
    nombres = ('css/tienda.css', 'js/tienda.js', 'js/js-activo.js', 'img/icono-192.png')
    return hashlib.sha256('|'.join(static(nombre) for nombre in nombres).encode()).hexdigest()[:12]


@login_not_required
@require_GET
def service_worker(request):
    respuesta = render(
        request, 'pwa/sw.js', {'version': version_de_los_estaticos()},
        content_type='application/javascript; charset=utf-8',
    )
    # El navegador lo vuelve a pedir en cada visita: una version nueva se instala enseguida.
    respuesta['Cache-Control'] = 'no-cache'
    return respuesta


@login_not_required
@require_GET
def sin_conexion(request):
    return render(request, 'pwa/sin_conexion.html')
