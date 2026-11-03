from django.contrib.auth.decorators import login_not_required
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from catalogo.forms import ORDENES, FiltroCatalogoForm
from catalogo.models import Categoria
from catalogo.services import (
    categorias_del_sitio, en_oferta, estantes_del_sitio, filtrar_catalogo, nuevos, nuevos_del_sitio, ofertas_del_sitio,
    recordar_busqueda, sugerencias as sugerencias_de_productos, vistos as vistos_recientes, vitrina_del_sitio,
)
from catalogo.views import sugerencias_de_productos as datos_de_sugerencias
from clientes.gustos import de as gustos_del_cliente
from core import metricas
from core.models import ConfiguracionTienda
from core.seo import sitio_json_ld

from . import services

RESULTADOS_POR_PAGINA = 12
TIENDAS_EN_PORTADA = 8
TIENDAS_POR_PAGINA = 24


def _preferidas_primero(categorias, usuario):
    """Las categorias que el cliente dijo que le gustan van primero (orden estable para las demas)."""
    from clientes.gustos import de

    preferidas = set(de(usuario).get('categorias', []))
    return sorted(categorias, key=lambda categoria: categoria.pk not in preferidas) if preferidas else categorias


PRODUCTOS_POR_ESTANTE = 10
ESTANTES_EN_PORTADA = 6


def _tarjetas_de_la_portada(categorias, ofertas, tiendas):
    """Los cuadros de arriba de la portada, al estilo de las grandes tiendas: la cuenta, cada categoria con cuatro
    fotos de sus productos, la mejor oferta y las tiendas. Se recortan categorias para completar filas de cuatro
    (esas siguen abajo en su fila de productos)."""
    de_categorias = []
    for categoria in categorias:
        con_foto = [producto for producto in categoria.estante if producto.foto_principal]
        if con_foto:
            de_categorias.append({'tipo': 'categoria', 'categoria': categoria, 'productos': con_foto[:4]})
    oferta = next((producto for producto in ofertas if producto.foto_principal), None)
    fijas = [
        {'tipo': 'cuenta'},
        *([{'tipo': 'oferta', 'producto': oferta}] if oferta else []),
        *([{'tipo': 'tiendas', 'tiendas': tiendas[:4]}] if tiendas else []),
    ]
    total = len(fijas) + len(de_categorias)
    if total > 4 and total % 4:
        de_categorias = de_categorias[:max(0, len(de_categorias) - total % 4)]
    # La cuenta primero, la oferta y las tiendas entre las categorias.
    tarjetas = [fijas[0], *de_categorias[:2], *fijas[1:2], *de_categorias[2:4], *fijas[2:], *de_categorias[4:]]
    return tarjetas


@require_GET
def portada(request):
    """Portada del sitio al estilo de las grandes tiendas (pedido del dueño el 2026-11-02, "full Amazon"): promociones
    arriba, cuadros de categorias con fotos y filas de productos de todas las tiendas. Cada producto dice de que
    tienda es y se sigue comprando dentro de ella."""
    from core.models import PreguntaFrecuente
    from planes.services import historias_para_la_portada, promociones_para

    tiendas = list(services.directorio()[:TIENDAS_EN_PORTADA + 1])
    destacadas_qs = list(services.tiendas_destacadas()[:6])
    # Promociones (anuncios, patrocinados y ofertas), primero lo que se parece a lo que el visitante busco o miro.
    promociones, personalizadas = promociones_para(request.session, usuario=request.user)
    categorias = _preferidas_primero(categorias_del_sitio(), request.user)
    estantes = estantes_del_sitio(categorias, PRODUCTOS_POR_ESTANTE)
    for categoria in categorias:
        categoria.estante = estantes.get(categoria.pk, [])
    ofertas = ofertas_del_sitio(PRODUCTOS_POR_ESTANTE)
    tiendas_del_directorio = services.para_el_directorio(tiendas[:TIENDAS_EN_PORTADA])
    plataforma = ConfiguracionTienda.obtener()
    return render(request, 'tiendas/portada.html', {
        'tiendas': tiendas_del_directorio,
        'hay_mas_tiendas': len(tiendas) > TIENDAS_EN_PORTADA,
        'tiendas_destacadas': services.para_el_directorio(destacadas_qs),
        'categorias': categorias,
        'tarjetas': _tarjetas_de_la_portada(categorias, ofertas, tiendas_del_directorio),
        'estantes': [categoria for categoria in categorias if len(categoria.estante) >= 3][:ESTANTES_EN_PORTADA],
        'promociones': promociones,
        'promociones_personalizadas': personalizadas,
        # Videos de las tiendas (plan Premium): un circulo por tienda, en otro orden en cada visita.
        'historias': historias_para_la_portada(),
        'ofertas': ofertas,
        'nuevos': nuevos_del_sitio(PRODUCTOS_POR_ESTANTE),
        'vistos': vistos_recientes(request.session),
        'preguntas': PreguntaFrecuente.objects.filter(activa=True)[:6],
        'sitio_json_ld': sitio_json_ld(
            plataforma.nombre, request.build_absolute_uri('/'),
            request.build_absolute_uri(reverse('tiendas:buscar')),
            logo=request.build_absolute_uri(static('img/icono-512.png')),
        ),
    })


@require_GET
def directorio(request):
    """Todas las tiendas activas, por paginas. Soporta filtro ?categoria=slug."""
    slug_cat = request.GET.get('categoria', '')[:100]
    categoria = Categoria.objects.filter(slug=slug_cat, activa=True).first() if slug_cat else None
    qs = services.directorio()
    if categoria is not None:
        qs = qs.filter(
            Q(productos__categoria=categoria) | Q(productos__categoria__padre=categoria),
            productos__activo=True,
        ).distinct()
    pagina = Paginator(qs, TIENDAS_POR_PAGINA).get_page(request.GET.get('pagina'))
    destacadas_qs = list(services.tiendas_destacadas()[:6]) if not categoria else []
    return render(request, 'tiendas/directorio.html', {
        'pagina': pagina,
        'tiendas': services.para_el_directorio(pagina.object_list),
        'tiendas_destacadas': services.para_el_directorio(destacadas_qs),
        'categoria': categoria,
        'categorias_filtro': categorias_del_sitio(),
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
    preferidas = set(gustos_del_cliente(request.user).get('categorias', []))
    if preferidas and not filtros.get('orden'):
        # Sin un orden elegido, lo de las categorias que le gustan va primero; dentro, lo mas nuevo.
        productos = productos.annotate(preferido=Case(
            When(Q(categoria_id__in=preferidas) | Q(categoria__padre_id__in=preferidas), then=Value(1)),
            default=Value(0), output_field=IntegerField(),
        )).order_by('-preferido', '-creado', '-id')
    if tienda is not None:
        productos = productos.filter(tienda=tienda)
    pagina = Paginator(productos, RESULTADOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    if filtros.get('q') and pagina.number == 1:
        recordar_busqueda(request.session, filtros['q'])
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
             'detalle': 'Tienda'}
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

    from referidos.services import COOKIE_REF

    inicial = {}
    if request.user.is_authenticated:
        inicial = {'nombre_responsable': request.user.get_full_name(), 'correo': request.user.email}
    # Programa de referidos: si llego por el enlace de otra tienda (/ref/<codigo>/), el codigo ya va puesto.
    codigo = request.COOKIES.get(COOKIE_REF, '').strip().upper()[:12]
    if codigo:
        inicial['codigo_referido'] = codigo
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
