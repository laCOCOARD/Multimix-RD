import logging

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from clientes.services import es_favorito
from core.archivos import ERRORES_DE_ALMACENAMIENTO
from core.red import quien_es
from core.seo import producto_json_ld, ruta_json_ld
from core.templatetags.moneda import formatear_monto
from opiniones import services as opiniones

from pedidos import entregas
from pedidos.services import zonas_activas
from pedidos.whatsapp import construir_enlace
from tiendas.decoradores import de_tienda
from tiendas.services import banners_de

from . import avisos, services
from .forms import ORDENES, FiltroCatalogoForm
from .models import Categoria, Producto

logger = logging.getLogger('multimix.catalogo')
PRODUCTOS_POR_PAGINA = 12
# Productos de los que el visitante pidio aviso en esta sesion (para no volver a ofrecerselo).
CLAVE_AVISOS = 'avisos_pedidos'
OPCIONES_ESTRELLAS = [
    (5, '5 estrellas · Excelente'), (4, '4 estrellas · Muy bueno'), (3, '3 estrellas · Bueno'),
    (2, '2 estrellas · Regular'), (1, '1 estrella · Malo'),
]


@de_tienda
def inicio(request):
    from planes.services import historias_de_la_tienda

    tienda = request.tienda
    secciones = [
        {'titulo': 'Ofertas', 'icono': 'bi-tag-fill', 'productos': services.en_oferta(tienda), 'enlace': '?oferta=on'},
        {'titulo': 'Destacados', 'icono': 'bi-star-fill', 'productos': services.destacados(tienda), 'enlace': ''},
        {'titulo': 'Nuevos', 'icono': 'bi-stars', 'productos': services.nuevos(tienda), 'enlace': '?orden=nuevos'},
        {'titulo': 'Más vendidos', 'icono': 'bi-fire', 'productos': services.mas_vendidos(tienda), 'enlace': '?orden=vendidos'},
    ]
    return render(request, 'catalogo/inicio.html', {
        'secciones': [s for s in secciones if s['productos']],
        'categorias': services.categorias_de_portada(tienda),
        'banners': banners_de(tienda),
        'vistos': services.vistos(request.session, tienda),
        # Su video (plan Premium), arriba de la pagina.
        'historias': historias_de_la_tienda(tienda),
    })


@de_tienda
def lista(request, slug=None):
    categoria = get_object_or_404(Categoria, slug=slug, activa=True) if slug else None
    formulario = FiltroCatalogoForm(request.GET)
    filtros = formulario.filtros()
    productos = services.filtrar_catalogo(filtros, categoria, request.tienda)
    pagina = Paginator(productos, PRODUCTOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'catalogo/lista.html', {
        'categoria': categoria,
        'categorias': services.categorias_de(request.tienda),
        'marcas': services.marcas_de(request.tienda, categoria),
        'filtros': filtros,
        'ordenes': ORDENES,
        'orden_actual': filtros.get('orden') or 'nuevos',
        'pagina': pagina,
        'hay_filtros': any(filtros.get(c) for c in ('q', 'marca', 'precio_min', 'precio_max', 'oferta', 'disponibles')),
        'sugeridos': (services.destacados(request.tienda, 10) or services.nuevos(request.tienda, 10))
        if not pagina.object_list else [],
    })


def respuesta_de_sugerencias(productos, con_tienda=False):
    """JSON del desplegable del buscador. `con_tienda` agrega de que tienda es cada producto."""
    resultados = []
    for item in productos:
        foto = item.foto_principal
        resultados.append({
            'nombre': item.nombre,
            'url': item.get_absolute_url(),
            'precio': formatear_monto(item.precio_final),
            'foto': foto.imagen.url if foto else '',
            'tienda': item.tienda.nombre if con_tienda else '',
        })
    return JsonResponse({'resultados': resultados})


@require_GET
@de_tienda
def sugerencias(request):
    return respuesta_de_sugerencias(services.sugerencias(request.GET.get('q', '')[:80], request.tienda))


@de_tienda
def producto(request, slug):
    tienda = request.tienda
    item = get_object_or_404(Producto.objects.activos().para_listado(), tienda=tienda, slug=slug)
    url_absoluta = request.build_absolute_uri(item.get_absolute_url())
    foto = item.foto_principal
    resumen_resenas = opiniones.resumen(item)
    imagenes = [request.build_absolute_uri(f.imagen.url) for f in item.fotos_ordenadas]
    consulta = f'Hola, me interesa este producto: {item.nombre} (SKU {item.sku})\n{url_absoluta}'
    vistos_antes = services.vistos(request.session, tienda, excluir=item.pk)
    services.recordar_visto(request.session, item)
    return render(request, 'catalogo/producto.html', {
        'producto': item,
        'fotos': item.fotos_ordenadas,
        'relacionados': services.relacionados(item),
        'opciones': services.opciones_de(item),
        'vistos': vistos_antes,
        'oferta_termina': services.oferta_por_terminar(item),
        'es_favorito': es_favorito(request.user, item),
        'resenas': opiniones.publicadas(item),
        'resumen_resenas': resumen_resenas,
        'json_ld': producto_json_ld(item, url_absoluta, imagenes, resumen_resenas),
        'ruta_json_ld': ruta_json_ld([
            (tienda.nombre, request.build_absolute_uri(tienda.get_absolute_url())),
            (item.categoria.nombre, request.build_absolute_uri(
                reverse('catalogo:categoria', args=[tienda.slug, item.categoria.slug]))),
            (item.nombre, url_absoluta),
        ]),
        'mi_resena': opiniones.resena_de(request.user, item),
        'preguntas': opiniones.preguntas_publicadas(item),
        'mis_preguntas': opiniones.preguntas_sin_responder(request.user, item),
        'esperando_aviso': item.agotado and (
            item.pk in request.session.get(CLAVE_AVISOS, [])
            or (request.user.is_authenticated and avisos.esperando(item, request.user.email))
        ),
        'opciones_estrellas': OPCIONES_ESTRELLAS,
        'cantidad_maxima': item.limite_compra,
        'plazo_recoger': entregas.estimar(tienda, True, bajo_pedido=item.bajo_pedido),
        'plazo_envio': entregas.estimar_envio(tienda, zonas_activas(tienda), item.bajo_pedido),
        'url_absoluta': url_absoluta,
        'og_imagen': request.build_absolute_uri(foto.imagen.url) if foto else '',
        'enlace_consulta': construir_enlace(tienda.whatsapp, consulta) if tienda.whatsapp else '',
    })


@require_POST
@login_required
@de_tienda
def opinar(request, slug):
    """Reseña de un cliente con cuenta. Queda por revisar: no se publica sola."""
    item = get_object_or_404(Producto.objects.activos(), tienda=request.tienda, slug=slug)
    try:
        fotos = opiniones.limpiar_fotos(request.FILES.getlist('fotos'))
        opiniones.guardar_resena(
            request.user, item, request.POST.get('estrellas'), request.POST.get('comentario'), fotos,
        )
    except opiniones.ResenaError as error:
        messages.error(request, error.mensaje)
    except ERRORES_DE_ALMACENAMIENTO:
        logger.exception('No se pudieron guardar las fotos de una reseña')
        messages.error(request, 'No pudimos guardar tus fotos. Inténtalo otra vez en un momento.')
    else:
        messages.success(request, 'Gracias por tu opinión. La publicamos en cuanto la revisemos.')
    return redirect(item.get_absolute_url() + '#opiniones')


@require_POST
@login_required
@de_tienda
def preguntar(request, slug):
    """Pregunta de un cliente con cuenta. Se publica cuando la tienda la responde."""
    item = get_object_or_404(Producto.objects.activos(), tienda=request.tienda, slug=slug)
    try:
        opiniones.preguntar(request.user, item, request.POST.get('pregunta'))
    except opiniones.ResenaError as error:
        messages.error(request, error.mensaje)
    else:
        messages.success(request, 'Enviamos tu pregunta a la tienda. Te avisamos por correo cuando la responda.')
    return redirect(item.get_absolute_url() + '#preguntas')


@require_POST
@de_tienda
def avisame(request, slug):
    """"Avisame cuando este disponible". Con sesion iniciada va al correo de la cuenta."""
    item = get_object_or_404(Producto.objects.activos(), tienda=request.tienda, slug=slug)
    if request.POST.get('sitio_web'):
        return redirect(item.get_absolute_url())
    correo = request.user.email if request.user.is_authenticated else request.POST.get('correo', '')
    try:
        validate_email(correo)
    except ValidationError:
        messages.error(request, 'Escribe un correo válido para avisarte.')
        return redirect(item.get_absolute_url())
    usuario = request.user if request.user.is_authenticated else None
    try:
        avisos.pedir_aviso(item, correo, quien_es(request), usuario)
    except avisos.AvisoError as error:
        messages.error(request, error.mensaje)
    else:
        request.session[CLAVE_AVISOS] = [item.pk, *request.session.get(CLAVE_AVISOS, [])][:30]
        messages.success(request, f'Listo: te escribimos a {correo} cuando "{item.nombre}" vuelva a estar disponible.')
    return redirect(item.get_absolute_url())
