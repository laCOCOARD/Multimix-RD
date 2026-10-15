from django.contrib.auth.decorators import login_not_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from pedidos.services import zonas_activas
from tiendas.decoradores import de_tienda

from .models import PaginaInformativa, PreguntaFrecuente


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
