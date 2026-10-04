from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from pedidos.services import zonas_activas

from .models import CuentaBancaria


@require_GET
def como_comprar(request):
    return render(request, 'paginas/como_comprar.html', {
        'cuentas': CuentaBancaria.objects.filter(activa=True),
    })


@require_GET
def envios(request):
    return render(request, 'paginas/envios.html', {'zonas': zonas_activas()})


@require_GET
@cache_control(max_age=3600, public=True)
def robots_txt(request):
    return render(request, 'robots.txt', {
        'sitemap': request.build_absolute_uri(reverse('sitemap')),
    }, content_type='text/plain; charset=utf-8')
