from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from pedidos.services import zonas_activas
from tiendas.decoradores import de_tienda

from .models import CuentaBancaria, PaginaInformativa, PreguntaFrecuente


@require_GET
@de_tienda
def como_comprar(request):
    return render(request, 'paginas/como_comprar.html', {
        'cuentas': CuentaBancaria.objects.filter(tienda=request.tienda, activa=True),
    })


@require_GET
@de_tienda
def envios(request):
    return render(request, 'paginas/envios.html', {'zonas': zonas_activas(request.tienda)})


@require_GET
def terminos(request):
    return render(request, 'paginas/terminos.html')


@require_GET
def salud(request):
    """Para el monitor de Render: responde 200 solo si la aplicacion y la base de datos funcionan."""
    from django.db import connection
    from django.http import HttpResponse

    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return HttpResponse('ok', content_type='text/plain')


@require_GET
def pagina(request, slug):
    """Pagina informativa. Sin publicar solo la ve el administrador principal, como vista previa."""
    item = get_object_or_404(PaginaInformativa, slug=slug)
    if not item.publicada and not request.user.is_superuser:
        raise Http404
    return render(request, 'paginas/pagina.html', {'pagina': item})


@require_GET
def preguntas(request):
    activas = PreguntaFrecuente.objects.filter(activa=True)
    if not activas.exists():
        raise Http404
    return render(request, 'paginas/preguntas.html', {'preguntas': activas})


@require_GET
@cache_control(max_age=3600, public=True)
def robots_txt(request):
    return render(request, 'robots.txt', {
        'sitemap': request.build_absolute_uri(reverse('sitemap')),
    }, content_type='text/plain; charset=utf-8')
