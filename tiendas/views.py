from django.contrib.auth.decorators import login_not_required
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from catalogo.forms import ORDENES, FiltroCatalogoForm
from catalogo.models import Categoria
from catalogo.services import (
    categorias_del_sitio, en_oferta, filtrar_catalogo, nuevos, ofertas_del_sitio, patrocinados_del_sitio,
    sugerencias as sugerencias_de_productos, vitrina_del_sitio,
)
from catalogo.views import sugerencias_de_productos as datos_de_sugerencias
from core import metricas
from core.models import ConfiguracionTienda
from core.seo import sitio_json_ld

from . import services

RESULTADOS_POR_PAGINA = 12
TIENDAS_EN_PORTADA = 8
PRODUCTOS_EN_PORTADA = 12
PATROCINADOS_EN_PORTADA = 4
TIENDAS_POR_PAGINA = 24


@require_GET
def portada(request):
    """Portada del sitio: productos de todas las tiendas y las tiendas mismas, para comprar sin conocer al vendedor
    o para entrar a la tienda de un emprendedor. Cada producto se sigue comprando dentro de su tienda."""
    from core.models import PreguntaFrecuente
    from planes.services import anuncios_para_la_portada, historias_para_la_portada

    tiendas = list(services.directorio()[:TIENDAS_EN_PORTADA + 1])
    # Los productos que las tiendas anuncian segun su plan van primero, marcados como "Patrocinado".
    patrocinados = patrocinados_del_sitio(PATROCINADOS_EN_PORTADA)
    ofertas = ofertas_del_sitio(excluir=[producto.pk for producto in patrocinados])
    # Lo que ya sale en ofertas no se repite en la seleccion.
    productos = patrocinados + vitrina_del_sitio(
        PRODUCTOS_EN_PORTADA - len(patrocinados), excluir=[producto.pk for producto in (*ofertas, *patrocinados)],
    )
    plataforma = ConfiguracionTienda.obtener()
    return render(request, 'tiendas/portada.html', {
        'tiendas': services.para_el_directorio(tiendas[:TIENDAS_EN_PORTADA]),
        'hay_mas_tiendas': len(tiendas) > TIENDAS_EN_PORTADA,
        'categorias': categorias_del_sitio(),
        'anuncios': anuncios_para_la_portada(),
        # Videos de las tiendas (plan Premium): un circulo por tienda, en otro orden en cada visita.
        'historias': historias_para_la_portada(),
        'productos': productos,
        'ofertas': ofertas,
        # Fotos reales para el bloque de bienvenida (en pantallas anchas): los ultimos de la seleccion con foto.
        'vitrina': [producto for producto in productos if producto.foto_principal][-4:],
        'preguntas': PreguntaFrecuente.objects.filter(activa=True)[:6],
        'sitio_json_ld': sitio_json_ld(
            plataforma.nombre, request.build_absolute_uri('/'),
            request.build_absolute_uri(reverse('tiendas:buscar')),
            logo=request.build_absolute_uri(static('img/icono-512.png')),
        ),
    })


@require_GET
def directorio(request):
    """Todas las tiendas activas, por paginas: la portada muestra solo las primeras."""
    pagina = Paginator(services.directorio(), TIENDAS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'tiendas/directorio.html', {
        'pagina': pagina,
        'tiendas': services.para_el_directorio(pagina.object_list),
    })


@require_GET
def buscar(request):
    """Buscador del sitio: productos de todas las tiendas (y las tiendas que coinciden con lo escrito). Cada resultado
    se compra dentro de su tienda.

    `?categoria=<slug>` limita a una categoria (con sus subcategorias): es a donde llevan las categorias de la portada.
    `?tienda=<slug>` limita a una tienda activa. Un filtro que no existe o no vale se ignora.
    """
    filtros = FiltroCatalogoForm(request.GET).filtros()
    slug = request.GET.get('categoria', '')[:100]
    categoria = Categoria.objects.filter(slug=slug, activa=True).first() if slug else None
    tiendas_activas = list(services.directorio())
    slug_tienda = request.GET.get('tienda', '')[:100]
    tienda = next((item for item in tiendas_activas if item.slug == slug_tienda), None) if slug_tienda else None
    productos = filtrar_catalogo(filtros, categoria)
    if tienda is not None:
        productos = productos.filter(tienda=tienda)
    pagina = Paginator(productos, RESULTADOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    if filtros.get('q') and pagina.number == 1:
        metricas.anotar(request, metricas.Evento.BUSQUEDA)
        if not pagina.object_list:
            metricas.anotar(request, metricas.Evento.BUSQUEDA_SIN_RESULTADOS)
    campos = ('precio_min', 'precio_max', 'oferta', 'disponibles')
    hay_filtros = bool(
        tienda or any(filtros.get(campo) not in (None, '', False) for campo in campos)
        or filtros.get('orden') not in (None, '', 'nuevos')
    )
    return render(request, 'tiendas/buscar.html', {
        # Sin resultados no se deja la pagina vacia: se sugieren ofertas o lo nuevo.
        'sugeridos': (en_oferta(None, limite=10) or nuevos(None, limite=10)) if not pagina.object_list else [],
        # Las tiendas que coinciden con lo escrito, arriba de los productos (solo en la primera pagina).
        'tiendas_encontradas': (
            services.buscar_tiendas(filtros.get('q')) if filtros.get('q') and pagina.number == 1 and not tienda else []
        ),
        'categoria': categoria,
        'tienda_filtro': tienda,
        'tiendas_filtro': tiendas_activas if len(tiendas_activas) > 1 else [],
        'filtros': filtros,
        'hay_filtros': hay_filtros,
        'ordenes': ORDENES,
        'orden_actual': filtros.get('orden') or 'nuevos',
        'pagina': pagina,
    })


@require_GET
def sugerencias(request):
    """Sugerencias del buscador del sitio: tiendas y productos de todas las tiendas activas."""
    texto = request.GET.get('q', '')[:80]
    return JsonResponse({
        'resultados': datos_de_sugerencias(sugerencias_de_productos(texto), con_tienda=True),
        'tiendas': [
            {'nombre': item.nombre, 'url': item.get_absolute_url(), 'foto': item.logo.url if item.logo else '',
             'detalle': f'Tienda · {item.total_productos} producto{"s" if item.total_productos != 1 else ""}'}
            for item in services.buscar_tiendas(texto, limite=3)
        ],
    })


@require_GET
def enlace_anterior(request, **kwargs):
    """Rutas de cuando habia una sola tienda (/catalogo/, /producto/x/): llevan a la tienda principal."""
    principal = services.tienda_principal()
    if principal is None:
        raise Http404
    destino = principal.get_absolute_url().rstrip('/') + request.path
    consulta = request.META.get('QUERY_STRING')
    return redirect(f'{destino}?{consulta}' if consulta else destino)


# --- Vender en el sitio (Fase 2 del rediseño, 2026-10-27) ----------------------------------
# Abiertas sin sesion: quien quiere vender no tiene por que tener una cuenta de cliente. La solicitud no crea cuentas
# ni da acceso al panel: queda pendiente para el administrador principal.

@login_not_required
@require_GET
def vender(request):
    return render(request, 'tiendas/vender.html')


@login_not_required
@never_cache
def solicitar_tienda(request):
    from core.red import ip_del_cliente

    from .forms import SolicitudTiendaForm

    inicial = {}
    if request.user.is_authenticated:
        inicial = {'nombre_responsable': request.user.get_full_name(), 'correo': request.user.email}
    formulario = SolicitudTiendaForm(request.POST or None, initial=inicial)
    if request.method == 'POST' and formulario.is_valid():
        ip = ip_del_cliente(request)
        if services.solicitud_bloqueada(ip, formulario.cleaned_data['correo']):
            formulario.add_error(None, 'Ya recibimos varias solicitudes desde aquí. Espera un rato o escríbenos.')
        else:
            services.registrar_solicitud(formulario.datos_de_la_solicitud(), ip=ip)
            return redirect('tiendas:solicitud_enviada')
    return render(request, 'tiendas/solicitar_tienda.html', {'formulario': formulario})


@login_not_required
@require_GET
def solicitud_enviada(request):
    return render(request, 'tiendas/solicitud_enviada.html')
