"""Medicion del negocio sin servicios externos (Fase 4 del rediseño, 2026-10-27).

Cada evento suma 1 en `ConteoDiario` (dia, evento, tienda). No se guarda quien fue, su IP, su cuenta ni lo que
escribio en el buscador: solo cuantas veces paso. Pedidos y solicitudes de tiendas no se cuentan aqui: se leen de
sus propias tablas, que son el registro real.

Son cifras aproximadas de uso, no de personas: una misma persona que ve dos veces un producto suma dos. No cuentan los
robots que se identifican, las peticiones sin navegador ni el personal del panel (un vendedor que revisa su propia
tienda no infla sus visitas).
"""
import logging
import re
from datetime import timedelta

from django.db import DatabaseError, transaction
from django.db.models import F, Min, Sum
from django.utils import timezone

from .models import ConteoDiario

logger = logging.getLogger('multimix.metricas')

Evento = ConteoDiario.Evento
DIAS = 30
ROBOTS = re.compile(
    r'bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|curl|wget|python|httpclient|headless|'
    r'lighthouse|monitor|uptime', re.IGNORECASE,
)
# Para calcular la conversion de solicitudes hacen falta al menos estas revisadas: con menos, el porcentaje engaña.
MINIMO_PARA_CONVERSION = 5


def se_cuenta(request):
    agente = request.META.get('HTTP_USER_AGENT', '')
    if request.method not in ('GET', 'POST') or not agente or ROBOTS.search(agente):
        return False
    usuario = getattr(request, 'user', None)
    return not getattr(usuario, 'is_staff', False)


def anotar(request, evento, tienda=None):
    """Suma 1 al evento de hoy (de la tienda, si la hay). Nunca lanza: medir no puede romper la compra."""
    if not se_cuenta(request):
        return
    hoy = timezone.localdate()
    try:
        with transaction.atomic():
            filas = ConteoDiario.objects.filter(fecha=hoy, evento=evento, tienda=tienda)
            # Si dos visitas crean la fila a la vez quedan dos filas del mismo dia: los totales se suman igual.
            if not filas.update(total=F('total') + 1):
                ConteoDiario.objects.create(fecha=hoy, evento=evento, tienda=tienda, total=1)
    except DatabaseError:
        logger.exception('No se pudo anotar el evento %s', evento)


def resumen(tiendas=None, dias=DIAS):
    """Lo de los ultimos `dias` dias: eventos contados y pedidos reales. `tiendas` lo limita a esas (un vendedor)."""
    from pedidos.models import Pedido

    hoy = timezone.localdate()
    desde = hoy - timedelta(days=dias - 1)
    conteos = ConteoDiario.objects.filter(fecha__gte=desde)
    pedidos = Pedido.objects.filter(creado__date__gte=desde)
    if tiendas is not None:
        conteos = conteos.filter(tienda__in=tiendas)
        pedidos = pedidos.filter(tienda__in=tiendas)
    eventos = dict(conteos.values('evento').order_by().annotate(n=Sum('total')).values_list('evento', 'n'))
    primer_dia = ConteoDiario.objects.aggregate(primero=Min('fecha'))['primero']
    creados = pedidos.count()

    def evento(clave):
        return eventos.get(clave, 0)

    filas = [
        {'etiqueta': 'Visitas a tiendas', 'valor': evento(Evento.VISITA_TIENDA), 'medido': True},
        {'etiqueta': 'Productos vistos', 'valor': evento(Evento.VISTA_PRODUCTO), 'medido': True},
        {'etiqueta': 'Agregados al carrito', 'valor': evento(Evento.AGREGADO_CARRITO), 'medido': True},
        {'etiqueta': 'Inicios de compra', 'valor': evento(Evento.INICIO_COMPRA), 'medido': True},
        {'etiqueta': 'Pedidos creados', 'valor': creados, 'medido': False},
        {'etiqueta': 'Pedidos entregados', 'valor': pedidos.filter(estado=Pedido.Estado.ENTREGADO).count(),
         'medido': False},
    ]
    return {
        'dias': dias,
        'desde': desde,
        # Desde cuando se cuenta: antes de esa fecha los eventos no existian (no es que fueran cero).
        'contando_desde': max(primer_dia, desde) if primer_dia else None,
        'embudo': filas,
        'busquedas': evento(Evento.BUSQUEDA),
        'busquedas_sin_resultados': evento(Evento.BUSQUEDA_SIN_RESULTADOS),
        'errores_de_compra': evento(Evento.ERROR_COMPRA),
        'pedidos_cancelados': pedidos.filter(estado=Pedido.Estado.CANCELADO).count(),
    }


def indicadores_del_sitio(dias=DIAS):
    """Para el administrador principal: tiendas, productos y solicitudes, todo contado de los registros."""
    from catalogo.models import Producto
    from tiendas.models import SolicitudTienda, Tienda

    desde = timezone.now() - timedelta(days=dias)
    solicitudes = SolicitudTienda.objects.all()
    Estado = SolicitudTienda.Estado
    aprobadas = solicitudes.filter(estado=Estado.APROBADA).count()
    rechazadas = solicitudes.filter(estado=Estado.RECHAZADA).count()
    revisadas = aprobadas + rechazadas
    return {
        'tiendas_activas': Tienda.objects.filter(activa=True).count(),
        'tiendas_registradas': Tienda.objects.count(),
        'productos_publicados': Producto.objects.activos().filter(tienda__activa=True).count(),
        'solicitudes_pendientes': solicitudes.filter(estado=Estado.PENDIENTE).count(),
        'solicitudes_recibidas': solicitudes.filter(creada__gte=desde).count(),
        'solicitudes_aprobadas': aprobadas,
        'solicitudes_revisadas': revisadas,
        # Solo con suficientes revisadas; si no, la plantilla dice que aun no hay datos para calcularla.
        'conversion_solicitudes': round(aprobadas * 100 / revisadas) if revisadas >= MINIMO_PARA_CONVERSION else None,
        'minimo_para_conversion': MINIMO_PARA_CONVERSION,
    }
