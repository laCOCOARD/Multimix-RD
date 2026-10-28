"""Cobro del sitio a las tiendas y anuncios en la portada (pedido del dueño el 2026-10-26).

- Cada tienda tiene un plan (`Tienda.plan`). Sin plan no se le cobra nada ni puede anunciarse.
- La mensualidad de cada mes vence el dia 1. El cargo se crea una semana antes para que la tienda pueda pagarlo.
- El dia 1 se calcula tambien el excedente del mes que termino: el porcentaje del plan sobre lo vendido (productos
  menos descuento, sin el envio) en los pedidos cobrados que pasaron del limite. Vence ese mismo dia.
- La tienda transfiere a las cuentas del sitio y sube el comprobante; el administrador lo aprueba o lo rechaza.
- Con un cargo vencido y sin comprobante, al pasar los dias de gracia la tienda se cierra (`activa=False`) hasta que
  el administrador la habilite. Lo que ya estaba vencido cuando la habilito no la vuelve a cerrar.
- Avisos por correo: unos dias antes, el dia que vence, el ultimo dia de gracia y al cerrarse.
"""
import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from django.db import transaction
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from core.correo import enviar, url_absoluta
from core.models import ConfiguracionTienda, cuentas_del_sitio
from core.templatetags.moneda import formatear_monto
from pedidos.models import Pedido
from tiendas.models import Tienda
from tiendas.services import ve_todas

from .models import Anuncio, Cargo, Plan, Video, limite_de_videos

logger = logging.getLogger('multimix.planes')

CERO = Decimal('0.00')
CENTAVO = Decimal('0.01')
# El cargo de la mensualidad aparece una semana antes de vencer.
DIAS_ANTES_DEL_CARGO = 7
LADO_COMPROBANTE = 1600
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre']

Estado = Cargo.Estado
Tipo = Cargo.Tipo


class CargoError(Exception):
    """Error de negocio con un mensaje listo para mostrar."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


# --- Fechas ---------------------------------------------------------------------------

def primer_dia(fecha):
    return fecha.replace(day=1)


def mes_siguiente(fecha):
    return (primer_dia(fecha) + timedelta(days=32)).replace(day=1)


def mes_anterior(fecha):
    return (primer_dia(fecha) - timedelta(days=1)).replace(day=1)


def nombre_del_mes(fecha):
    return f'{MESES[fecha.month - 1]} de {fecha.year}'


def fecha_larga(fecha):
    return f'{fecha.day} de {MESES[fecha.month - 1]}'


def _hoy():
    return timezone.localdate()


def dias_de_gracia():
    return ConfiguracionTienda.obtener().dias_de_gracia


def fecha_de_cierre(vence):
    """El dia en que se cierra la tienda si ese cargo sigue sin pagar."""
    return vence + timedelta(days=dias_de_gracia())


def _inicio_del_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min))


# --- Pedidos de mas -------------------------------------------------------------------

@dataclass
class Excedente:
    """Los pedidos cobrados de una tienda en un mes y lo que se cobra por los que pasan del limite de su plan."""
    tienda: object
    periodo: date
    plan: object = None
    pedidos: int = 0
    incluidos: int | None = None
    de_mas: list = field(default_factory=list)
    base: Decimal = CERO
    porcentaje: Decimal = CERO

    @property
    def monto(self):
        return (self.base * self.porcentaje / Decimal('100')).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    @property
    def restantes(self):
        """Cuantos pedidos le quedan este mes sin cargo extra (None = sin limite)."""
        if self.incluidos is None:
            return None
        return max(self.incluidos - self.pedidos, 0)


def pedidos_cobrados(tienda, periodo):
    """Pedidos cobrados (con fecha de pago) en ese mes y que siguen siendo venta. Desde que la tienda tiene su plan."""
    inicio = _inicio_del_dia(primer_dia(periodo))
    if tienda.plan_desde and tienda.plan_desde > primer_dia(periodo):
        inicio = _inicio_del_dia(tienda.plan_desde)
    fin = _inicio_del_dia(mes_siguiente(periodo))
    return (
        Pedido.objects.filter(tienda=tienda, fecha_pago__gte=inicio, fecha_pago__lt=fin)
        .exclude(estado__in=Pedido.ESTADOS_SIN_VENTA).order_by('fecha_pago', 'id')
    )


def calcular_excedente(tienda, periodo, plan=None):
    """Los pedidos que pasan del limite son los ultimos cobrados del mes; se cobra el porcentaje de lo vendido en
    ellos (productos menos descuento, sin el envio)."""
    plan = plan or tienda.plan
    resultado = Excedente(tienda=tienda, periodo=primer_dia(periodo), plan=plan)
    pedidos = list(pedidos_cobrados(tienda, periodo).only('id', 'numero', 'subtotal', 'descuento', 'fecha_pago'))
    resultado.pedidos = len(pedidos)
    if plan is None or plan.pedidos_incluidos is None:
        return resultado
    resultado.incluidos = plan.pedidos_incluidos
    resultado.porcentaje = plan.porcentaje_excedente
    resultado.de_mas = pedidos[plan.pedidos_incluidos:]
    resultado.base = sum((max(p.subtotal - p.descuento, CERO) for p in resultado.de_mas), CERO)
    return resultado


# --- Cargos de cada mes ----------------------------------------------------------------

def _crear_cargo(tienda, tipo, periodo, **datos):
    """Crea el cargo si no existe ya (uno por tienda, tipo y mes). Devuelve el cargo nuevo o None."""
    cargo, creado = Cargo.objects.get_or_create(tienda=tienda, tipo=tipo, periodo=periodo, defaults=datos)
    return cargo if creado else None


def generar_mensualidades(hoy=None):
    """Crea la mensualidad del mes que viene (una semana antes) y, si faltara, la de este mes mientras dure la gracia.

    La de este mes solo se cobra si la tienda ya tenia el plan antes del dia 1: quien recibe un plan a mitad de mes
    empieza a pagar el mes siguiente. Tampoco se crea una mensualidad ya fuera de gracia, que cerraria la tienda
    al instante (por ejemplo, al habilitarla despues del dia 5).
    """
    hoy = hoy or _hoy()
    este_mes, proximo = primer_dia(hoy), mes_siguiente(hoy)
    creados = []
    for tienda in Tienda.objects.activas().filter(plan__mensualidad__gt=0).select_related('plan'):
        periodos = []
        if hoy >= proximo - timedelta(days=DIAS_ANTES_DEL_CARGO):
            periodos.append(proximo)
        if hoy < fecha_de_cierre(este_mes) and (tienda.plan_desde is None or tienda.plan_desde < este_mes):
            periodos.append(este_mes)
        for periodo in periodos:
            cargo = _crear_cargo(
                tienda, Tipo.MENSUALIDAD, periodo, monto=tienda.plan.mensualidad, vence=periodo,
                concepto=f'Mensualidad de {nombre_del_mes(periodo)} · Plan {tienda.plan.nombre}',
            )
            if cargo:
                creados.append(cargo)
    return creados


def generar_excedentes(hoy=None):
    """El dia 1 (o la primera vez que corre despues) cobra los pedidos de mas del mes que termino."""
    hoy = hoy or _hoy()
    periodo = mes_anterior(hoy)
    vence = primer_dia(hoy) if hoy < fecha_de_cierre(primer_dia(hoy)) else hoy
    creados = []
    con_limite = Tienda.objects.filter(plan__pedidos_incluidos__isnull=False, plan__porcentaje_excedente__gt=0)
    for tienda in con_limite.select_related('plan'):
        if Cargo.objects.filter(tienda=tienda, tipo=Tipo.EXCEDENTE, periodo=periodo).exists():
            continue
        if tienda.plan_desde and tienda.plan_desde >= mes_siguiente(periodo):
            continue
        calculo = calcular_excedente(tienda, periodo)
        if calculo.monto <= 0:
            continue
        numeros = ', '.join(pedido.numero for pedido in calculo.de_mas[:60])
        if len(calculo.de_mas) > 60:
            numeros += f' y {len(calculo.de_mas) - 60} más'
        cargo = _crear_cargo(
            tienda, Tipo.EXCEDENTE, periodo, monto=calculo.monto, vence=vence,
            concepto=f'Pedidos de más en {nombre_del_mes(periodo)}: {len(calculo.de_mas)} sobre {calculo.incluidos} '
                     f'incluidos',
            detalle=(
                f'{calculo.pedidos} pedidos cobrados en {nombre_del_mes(periodo)}; el plan {tienda.plan.nombre} incluye '
                f'{calculo.incluidos}. Los {len(calculo.de_mas)} de más vendieron {formatear_monto(calculo.base)} en '
                f'productos (sin envío); el {calculo.porcentaje.normalize():f} % es {formatear_monto(calculo.monto)}.\n'
                f'Pedidos de más: {numeros}.'
            ),
        )
        if cargo:
            creados.append(cargo)
    return creados


# --- Estado de cuenta ------------------------------------------------------------------

@dataclass
class EstadoDeCuenta:
    tienda: object
    plan: object
    pendientes: list
    uso: Excedente
    total_pendiente: Decimal
    proximo_vencimiento: date | None
    cierre: date | None
    en_revision: int

    @property
    def vencido(self):
        return bool(self.proximo_vencimiento and self.proximo_vencimiento <= _hoy())


def estado_de_cuenta(tienda, hoy=None):
    """Lo que la tienda ve en su panel: su plan, lo que lleva del mes y lo que debe."""
    hoy = hoy or _hoy()
    pendientes = list(tienda.cargos.filter(estado__in=Cargo.POR_PAGAR).order_by('vence', 'id'))
    sin_pagar = [cargo for cargo in pendientes if cargo.estado == Estado.PENDIENTE]
    proximo = min((cargo.vence for cargo in sin_pagar), default=None)
    return EstadoDeCuenta(
        tienda=tienda, plan=tienda.plan, pendientes=pendientes,
        uso=calcular_excedente(tienda, hoy),
        total_pendiente=sum((cargo.monto for cargo in pendientes), CERO),
        proximo_vencimiento=proximo, cierre=fecha_de_cierre(proximo) if proximo else None,
        en_revision=sum(1 for cargo in pendientes if cargo.estado == Estado.EN_REVISION),
    )


def resumen_para_el_administrador():
    """Para la portada del panel del administrador principal."""
    return {
        'comprobantes_por_revisar': Cargo.objects.filter(estado=Estado.EN_REVISION).count(),
        'cargos_vencidos': Cargo.objects.filter(estado=Estado.PENDIENTE, vence__lte=_hoy()).count(),
        'tiendas_cerradas': Tienda.objects.filter(cerrada_por_falta_de_pago=True, activa=False).count(),
        'tiendas_sin_plan': Tienda.objects.activas().filter(plan__isnull=True).count(),
    }


# --- Correos ---------------------------------------------------------------------------

def correos_de_los_duenos(tienda):
    """A quien se le cobra: los vendedores de la tienda y su correo de contacto; si no hay ninguno, al sitio."""
    from pedidos.avisos import correos_del_sitio

    correos = list(tienda.usuarios.filter(is_active=True).exclude(email='').values_list('email', flat=True))
    if tienda.correo:
        correos.append(tienda.correo)
    return correos or correos_del_sitio()


def _contexto(tienda, **extra):
    return {
        'tienda': tienda,
        'sitio': ConfiguracionTienda.obtener().nombre,
        'cuentas': list(cuentas_del_sitio()),
        'enlace_panel': url_absoluta(reverse('admin:planes_cargo_changelist')),
        **extra,
    }


def _al_confirmar(funcion):
    transaction.on_commit(funcion)


ASUNTOS = {
    'por_vencer': 'Tu mensualidad de {sitio} vence el {vence}',
    'vence_hoy': 'Pago pendiente: tu tienda en {sitio}',
    'ultimo_dia': 'Último día: mañana se cierra tu tienda en {sitio}',
}


def _enviar_recordatorio(tienda, cargos, aviso, vence, cierre):
    contexto = _contexto(
        tienda, cargos=cargos, aviso=aviso, total=sum((cargo.monto for cargo in cargos), CERO),
        vence=fecha_larga(vence), cierre=fecha_larga(cierre), gracia=dias_de_gracia(),
    )
    asunto = ASUNTOS[aviso].format(sitio=contexto['sitio'], vence=fecha_larga(vence))
    enviar(asunto, 'tienda_cobro_recordatorio', contexto, correos_de_los_duenos(tienda))


def enviar_recordatorios(hoy=None):
    """Unos dias antes, el dia que vence y el ultimo dia de gracia. Cada aviso sale una sola vez por cargo; si no
    corrio a tiempo, sale el que toca ahora y no los anteriores."""
    hoy = hoy or _hoy()
    antes = ConfiguracionTienda.obtener().dias_aviso_mensualidad
    gracia = dias_de_gracia()
    grupos = {}
    pendientes = Cargo.objects.filter(estado=Estado.PENDIENTE, tienda__activa=True).select_related('tienda')
    for cargo in pendientes.order_by('vence', 'id'):
        grupos.setdefault((cargo.tienda_id, cargo.vence), []).append(cargo)
    enviados = 0
    for (_, vence), cargos in grupos.items():
        cierre = vence + timedelta(days=gracia)
        if hoy >= cierre:
            continue  # Lo atiende el cierre.
        if gracia and hoy >= cierre - timedelta(days=1):
            aviso, anteriores = 'ultimo_dia', {'por_vencer', 'vence_hoy'}
        elif hoy >= vence:
            aviso, anteriores = 'vence_hoy', {'por_vencer'}
        elif hoy >= vence - timedelta(days=antes):
            aviso, anteriores = 'por_vencer', set()
        else:
            continue
        if all(aviso in cargo.avisos for cargo in cargos):
            continue
        _enviar_recordatorio(cargos[0].tienda, cargos, aviso, vence, cierre)
        for cargo in cargos:
            cargo.avisos = sorted({*cargo.avisos, aviso, *anteriores})
            cargo.save(update_fields=['avisos'])
        enviados += 1
    return enviados


# --- Cierre y habilitacion -------------------------------------------------------------

def _vencidos_sin_gracia(hoy):
    return Cargo.objects.filter(estado=Estado.PENDIENTE, vence__lte=hoy - timedelta(days=dias_de_gracia()))


def cerrar_tiendas_morosas(hoy=None):
    """Cierra las tiendas con un cargo sin pagar (y sin comprobante en revision) pasados los dias de gracia.

    Un cargo que ya estaba fuera de gracia cuando el administrador habilito la tienda no la vuelve a cerrar.
    """
    hoy = hoy or _hoy()
    gracia = dias_de_gracia()
    cerradas = []
    vencidos = _vencidos_sin_gracia(hoy)
    for tienda in Tienda.objects.activas().filter(pk__in=vencidos.values('tienda')):
        cargos = list(vencidos.filter(tienda=tienda))
        if tienda.habilitada_el:
            habilitada = timezone.localdate(tienda.habilitada_el)
            cargos = [cargo for cargo in cargos if cargo.vence + timedelta(days=gracia) > habilitada]
        if not cargos:
            continue
        with transaction.atomic():
            cambiadas = Tienda.objects.filter(pk=tienda.pk, activa=True).update(
                activa=False, cerrada_por_falta_de_pago=True, cerrada_el=timezone.now(),
            )
            if not cambiadas:
                continue
            for cargo in cargos:
                cargo.avisos = sorted({*cargo.avisos, 'cerrada'})
                cargo.save(update_fields=['avisos'])
            _avisar_cierre(tienda, cargos)
        logger.info('Tienda %s cerrada por falta de pago', tienda.nombre)
        cerradas.append(tienda)
    return cerradas


def _avisar_cierre(tienda, cargos):
    def enviar_avisos():
        from pedidos.avisos import correos_del_sitio

        contexto = _contexto(tienda, cargos=cargos, total=sum((cargo.monto for cargo in cargos), CERO))
        enviar(f'Tu tienda en {contexto["sitio"]} se cerró por falta de pago', 'tienda_cerrada_por_pago', contexto,
               correos_de_los_duenos(tienda))
        contexto['enlace_tienda'] = url_absoluta(reverse('admin:tiendas_tienda_change', args=[tienda.pk]))
        enviar(f'Se cerró la tienda {tienda.nombre} por falta de pago', 'sitio_tienda_cerrada', contexto,
               correos_del_sitio())
    _al_confirmar(enviar_avisos)


def habilitar_tienda(tienda, usuario=None):
    """El administrador vuelve a abrir una tienda (cerrada por falta de pago o apagada)."""
    if usuario is not None and not ve_todas(usuario):
        raise CargoError('Solo el administrador principal habilita tiendas.')
    Tienda.objects.filter(pk=tienda.pk).update(
        activa=True, cerrada_por_falta_de_pago=False, cerrada_el=None, habilitada_el=timezone.now(),
    )
    tienda.refresh_from_db()
    logger.info('Tienda %s habilitada por %s', tienda.nombre, usuario or 'el sistema')
    return tienda


def revisar_cobros(hoy=None):
    """Lo que corre en las tareas periodicas: crea los cargos del mes, avisa y cierra a quien no pago."""
    hoy = hoy or _hoy()
    mensualidades = generar_mensualidades(hoy)
    excedentes = generar_excedentes(hoy)
    avisos = enviar_recordatorios(hoy)
    cerradas = cerrar_tiendas_morosas(hoy)
    if mensualidades or excedentes or avisos or cerradas:
        logger.info(
            'Cobros: %s mensualidades, %s excedentes, %s avisos, %s tiendas cerradas',
            len(mensualidades), len(excedentes), avisos, len(cerradas),
        )
    return {'mensualidades': mensualidades, 'excedentes': excedentes, 'avisos': avisos, 'cerradas': cerradas}


# --- Comprobantes ----------------------------------------------------------------------

def _solo_el_administrador(usuario):
    if usuario is not None and not ve_todas(usuario):
        raise CargoError('Solo el administrador principal confirma los pagos de las tiendas.')


@transaction.atomic
def subir_comprobante(cargo, archivo, referencia=''):
    """La tienda avisa que pago, con la foto del comprobante (obligatoria). El cargo queda en revision."""
    from catalogo.imagenes import convertir_a_webp
    from core.archivos import almacenamiento_privado
    from core.validators import validar_imagen

    cargo = Cargo.objects.select_for_update().select_related('tienda').get(pk=cargo.pk)
    if cargo.estado != Estado.PENDIENTE:
        raise CargoError(f'"{cargo.concepto}" está "{cargo.get_estado_display().lower()}": ya no espera comprobante.')
    if not archivo:
        raise CargoError('Adjunta la foto o captura del comprobante de la transferencia.')
    validar_imagen(archivo)
    anterior = cargo.comprobante.name if cargo.comprobante else ''
    cargo.comprobante.save(f'{uuid4().hex}.webp', convertir_a_webp(archivo, LADO_COMPROBANTE), save=False)
    cargo.referencia = (referencia or '').strip()[:60]
    cargo.estado = Estado.EN_REVISION
    cargo.enviado_el = timezone.now()
    cargo.save()
    if anterior:
        almacenamiento_privado().delete(anterior)
    _avisar_comprobante(cargo)
    return cargo


def _avisar_comprobante(cargo):
    def enviar_aviso():
        from pedidos.avisos import correos_del_sitio

        contexto = _contexto(
            cargo.tienda, cargo=cargo,
            enlace_cargo=url_absoluta(reverse('admin:planes_cargo_change', args=[cargo.pk])),
        )
        enviar(f'Comprobante de {cargo.tienda.nombre}: {cargo.concepto}', 'sitio_comprobante_tienda', contexto,
               correos_del_sitio())
    _al_confirmar(enviar_aviso)


@transaction.atomic
def aprobar_cargo(cargo, usuario=None):
    """El dinero llego: el cargo queda pagado. Aprobar uno ya pagado no hace nada. No abre una tienda cerrada: eso
    lo decide el administrador (`habilitar_tienda`)."""
    _solo_el_administrador(usuario)
    cargo = Cargo.objects.select_for_update().select_related('tienda').get(pk=cargo.pk)
    if cargo.estado == Estado.PAGADO:
        return cargo
    if cargo.estado not in Cargo.POR_PAGAR:
        raise CargoError(f'"{cargo.concepto}" está anulado y no se puede cobrar.')
    cargo.estado = Estado.PAGADO
    cargo.revisado_el = timezone.now()
    cargo.revisado_por = usuario
    cargo.save(update_fields=['estado', 'revisado_el', 'revisado_por'])

    def enviar_aviso():
        enviar(f'Recibimos tu pago: {cargo.concepto}', 'tienda_cargo_pagado', _contexto(cargo.tienda, cargo=cargo),
               correos_de_los_duenos(cargo.tienda))
    _al_confirmar(enviar_aviso)
    return cargo


@transaction.atomic
def rechazar_comprobante(cargo, usuario=None, nota=''):
    """El comprobante no sirve: el cargo vuelve a pendiente y la tienda puede subir otro."""
    _solo_el_administrador(usuario)
    cargo = Cargo.objects.select_for_update().select_related('tienda').get(pk=cargo.pk)
    if cargo.estado != Estado.EN_REVISION:
        raise CargoError(f'"{cargo.concepto}" no tiene un comprobante en revisión.')
    cargo.estado = Estado.PENDIENTE
    cargo.nota = (nota or 'El comprobante no corresponde a un depósito recibido.')[:255]
    cargo.revisado_el = timezone.now()
    cargo.revisado_por = usuario
    cargo.save(update_fields=['estado', 'nota', 'revisado_el', 'revisado_por'])

    def enviar_aviso():
        enviar(f'No pudimos confirmar tu pago: {cargo.concepto}', 'tienda_comprobante_rechazado',
               _contexto(cargo.tienda, cargo=cargo, cierre=fecha_larga(fecha_de_cierre(cargo.vence))),
               correos_de_los_duenos(cargo.tienda))
    _al_confirmar(enviar_aviso)
    return cargo


@transaction.atomic
def anular_cargo(cargo, usuario=None, nota=''):
    """Un cargo que no corresponde (por ejemplo, un mes que se le regalo a la tienda, o uno que se devolvio)."""
    _solo_el_administrador(usuario)
    cargo = Cargo.objects.select_for_update().get(pk=cargo.pk)
    if cargo.estado == Estado.ANULADO:
        return cargo
    cargo.estado = Estado.ANULADO
    cargo.nota = (nota or cargo.nota or 'Anulado por el administrador.')[:255]
    cargo.revisado_el = timezone.now()
    cargo.revisado_por = usuario
    cargo.save(update_fields=['estado', 'nota', 'revisado_el', 'revisado_por'])
    return cargo


@transaction.atomic
def reabrir_cargo(cargo, usuario=None, nota=''):
    """Vuelve a dejar pendiente un cargo pagado o anulado (por ejemplo, si se confirmo por error)."""
    _solo_el_administrador(usuario)
    cargo = Cargo.objects.select_for_update().get(pk=cargo.pk)
    cargo.estado = Estado.PENDIENTE
    cargo.nota = (nota or cargo.nota)[:255]
    cargo.revisado_el = timezone.now()
    cargo.revisado_por = usuario
    cargo.save(update_fields=['estado', 'nota', 'revisado_el', 'revisado_por'])
    return cargo


def cambiar_estado_del_cargo(cargo, nuevo, usuario=None, nota=''):
    """El administrador elige el estado en el formulario del cargo: cada cambio pasa por su regla (y su correo)."""
    anterior = Cargo.objects.only('estado').get(pk=cargo.pk).estado
    if nuevo == anterior:
        return cargo
    if nuevo == Estado.PAGADO:
        return aprobar_cargo(cargo, usuario)
    if nuevo == Estado.ANULADO:
        return anular_cargo(cargo, usuario, nota)
    if nuevo == Estado.PENDIENTE:
        if anterior == Estado.EN_REVISION:
            return rechazar_comprobante(cargo, usuario, nota)
        return reabrir_cargo(cargo, usuario, nota)
    raise CargoError('Un cargo queda "en revisión" solo cuando la tienda sube su comprobante.')


# --- Anuncios en la portada ------------------------------------------------------------

def _repartir(por_tienda, limite):
    """Uno de cada tienda, luego el segundo de cada una...: ninguna llena el espacio."""
    filas = [lista for lista in por_tienda.values() if lista]
    elegidos = []
    while len(elegidos) < limite and any(filas):
        for fila in filas:
            if fila and len(elegidos) < limite:
                elegidos.append(fila.pop(0))
    return elegidos


def anuncios_para_la_portada(limite=8):
    """Anuncios aprobados y vigentes de tiendas activas, sin pasar de lo que permite el plan de cada una."""
    ahora = timezone.now()
    anuncios = (
        Anuncio.objects.filter(activo=True, aprobado=True, tienda__activa=True, tienda__plan__anuncios_portada__gt=0)
        .filter(Q(vigente_desde__isnull=True) | Q(vigente_desde__lte=ahora))
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=ahora))
        .select_related('tienda__plan', 'producto__categoria', 'producto__tienda')
        .order_by('orden', '-creado', '-id')
    )
    por_tienda = {}
    for anuncio in anuncios:
        lista = por_tienda.setdefault(anuncio.tienda_id, [])
        if len(lista) < anuncio.tienda.plan.anuncios_portada:
            lista.append(anuncio)
    return _repartir(por_tienda, limite)



# --- Promociones de la portada (pedido del dueño el 2026-10-27) ------------------------------
# Un carrusel que rota solo con los anuncios aprobados, los productos patrocinados y las ofertas reales. Va primero lo
# que se parece a lo que el visitante busco o miro hace poco (catalogo.services.intereses, solo de su sesion).

OFERTAS_EN_PROMOCIONES = 4


@dataclass
class Promocion:
    titulo: str
    url: str
    imagen: str
    tienda: str
    etiqueta: str  # siempre dice que es: "Anuncio" o "Oferta -20%"
    texto: str = ''
    precio: object = None
    precio_anterior: object = None
    es_foto_de_producto: bool = False
    puntos: int = 0


def _puntos(texto, categorias, tienda_id, intereses):
    from core.texto import normalizar

    texto = normalizar(texto)
    puntos = 3 * sum(1 for palabra in intereses['palabras'] if palabra in texto)
    if categorias & intereses['categorias']:
        puntos += 2
    if tienda_id in intereses['tiendas']:
        puntos += 1
    return puntos


def _puntos_por_gustos(producto, intereses):
    from clientes.gustos import en_su_presupuesto

    gustos = intereses.get('gustos', {})
    puntos = 0
    if gustos.get('busca') == 'ofertas' and producto.en_oferta:
        puntos += 1
    if gustos.get('busca') == 'nuevos' and producto.es_nuevo:
        puntos += 1
    if en_su_presupuesto(gustos, producto.precio_final):
        puntos += 1
    return puntos


def _promocion_de_producto(producto, etiqueta, intereses):
    foto = producto.foto_principal
    categorias = {producto.categoria_id, producto.categoria.padre_id} - {None}
    return Promocion(
        titulo=producto.nombre, url=producto.get_absolute_url(), imagen=foto.url_tarjeta if foto else '',
        tienda=producto.tienda.nombre, etiqueta=etiqueta, precio=producto.precio_final,
        precio_anterior=producto.precio if producto.en_oferta else None, es_foto_de_producto=True,
        puntos=_puntos(f'{producto.texto_busqueda} {producto.categoria.nombre}', categorias, producto.tienda_id, intereses)
        + _puntos_por_gustos(producto, intereses),
    )


def promociones_para(sesion, limite=8, usuario=None):
    """Las promociones de la portada, primero las que mas se parecen a lo que el visitante busco, miro o dijo que le
    gusta (si tiene cuenta y contesto sus gustos).

    Devuelve (promociones, personalizadas): personalizadas dice si alguna coincidio con sus intereses.
    """
    from catalogo.services import intereses as intereses_de, ofertas_del_sitio, patrocinados_del_sitio

    intereses = intereses_de(sesion, usuario)
    promociones = []
    for anuncio in anuncios_para_la_portada():
        producto = anuncio.producto
        categorias = {producto.categoria_id, producto.categoria.padre_id} - {None} if producto else set()
        texto = ' '.join([anuncio.titulo, anuncio.texto, producto.nombre if producto else '',
                          producto.categoria.nombre if producto else '', anuncio.tienda.nombre])
        promociones.append(Promocion(
            titulo=anuncio.titulo, texto=anuncio.texto, url=anuncio.get_url(), imagen=anuncio.imagen.url,
            tienda=anuncio.tienda.nombre, etiqueta='Anuncio',
            puntos=_puntos(texto, categorias, anuncio.tienda_id, intereses),
        ))
    patrocinados = patrocinados_del_sitio()
    promociones += [_promocion_de_producto(producto, 'Anuncio', intereses) for producto in patrocinados]
    ofertas = [
        _promocion_de_producto(producto, f'Oferta -{producto.porcentaje_descuento}%', intereses)
        for producto in ofertas_del_sitio(limite=12, excluir=[producto.pk for producto in patrocinados])
    ]
    # De las ofertas entran las que mas coinciden (a igualdad, el orden repartido entre tiendas).
    ofertas.sort(key=lambda promocion: -promocion.puntos)
    promociones += ofertas[:OFERTAS_EN_PROMOCIONES]
    # Orden estable: a igualdad de puntos quedan anuncios, patrocinados y ofertas, en ese orden.
    promociones.sort(key=lambda promocion: -promocion.puntos)
    promociones = promociones[:limite]
    return promociones, any(promocion.puntos for promocion in promociones)

def avisar_anuncio_por_revisar(anuncio):
    """Al administrador: una tienda creo o cambio un anuncio y espera su aprobacion para salir en la portada."""
    def enviar_aviso():
        from pedidos.avisos import correos_del_sitio

        contexto = _contexto(
            anuncio.tienda, anuncio=anuncio,
            enlace_anuncio=url_absoluta(reverse('admin:planes_anuncio_change', args=[anuncio.pk])),
        )
        enviar(f'Anuncio por revisar: {anuncio.tienda.nombre}', 'sitio_anuncio_por_revisar', contexto,
               correos_del_sitio())
    _al_confirmar(enviar_aviso)


def aprobar_anuncio(anuncio, usuario=None):
    """El anuncio sale en la portada por DIAS_DEL_ANUNCIO dias desde ahora (si su tienda esta activa y su plan lo
    permite). La tienda recibe un correo."""
    if usuario is not None and not ve_todas(usuario):
        raise CargoError('Solo el administrador principal aprueba anuncios.')
    if anuncio.aprobado:
        return anuncio
    ahora = timezone.now()
    anuncio.abrir_semana(ahora)
    Anuncio.objects.filter(pk=anuncio.pk).update(
        aprobado=True, revisado_el=ahora, vigente_desde=anuncio.vigente_desde, vigente_hasta=anuncio.vigente_hasta,
    )
    anuncio.refresh_from_db()

    def enviar_aviso():
        enviar(f'Tu anuncio ya está en la portada de {ConfiguracionTienda.obtener().nombre}', 'tienda_anuncio_aprobado',
               _contexto(anuncio.tienda, anuncio=anuncio), correos_de_los_duenos(anuncio.tienda))
    _al_confirmar(enviar_aviso)
    return anuncio


def limite_de_patrocinados(tienda):
    return tienda.plan.productos_patrocinados if tienda.plan_id else 0


# --- Videos de las tiendas -------------------------------------------------------------
# Como las historias de Instagram: un circulo por tienda en la portada; al tocarlo se abre el visor con sus videos
# (static/js/historias.js). El video solo se descarga cuando alguien lo abre.

VIDEOS_VISTOS = 'videos_vistos'
TIENDAS_CON_VIDEO_EN_PORTADA = 20


def videos_visibles():
    """Los videos que se pueden mostrar: aprobados, activos, de una tienda activa cuyo plan incluye videos."""
    return (
        Video.objects.filter(activo=True, aprobado=True, tienda__activa=True, tienda__plan__videos_portada__gt=0)
        .select_related('tienda__plan', 'producto__categoria', 'producto__tienda')
        .order_by('orden', '-revisado_el', '-id')
    )


def _agrupar_por_tienda(videos):
    """Un grupo por tienda, sin pasar de lo que permite su plan (por si le bajaron el plan despues de subirlos)."""
    grupos = {}
    for video in videos:
        grupo = grupos.setdefault(video.tienda_id, {'tienda': video.tienda, 'videos': []})
        if len(grupo['videos']) < video.tienda.plan.videos_portada:
            grupo['videos'].append(video)
    return list(grupos.values())


def historias_para_la_portada(limite=TIENDAS_CON_VIDEO_EN_PORTADA):
    """Los videos de la portada, agrupados por tienda. El orden de las tiendas cambia en cada visita: todas pagan lo
    mismo por estar ahi y ninguna queda siempre de ultima."""
    grupos = _agrupar_por_tienda(videos_visibles())
    random.shuffle(grupos)
    return grupos[:limite]


def historias_de_la_tienda(tienda):
    """Los videos de una tienda para arriba de su pagina: una lista con su grupo, o vacia."""
    return _agrupar_por_tienda(videos_visibles().filter(tienda=tienda))


def cupos_de_video(tienda):
    """Cuantos videos mas puede subir la tienda segun su plan."""
    return max(0, limite_de_videos(tienda) - tienda.videos.count())


def contar_vista(video_id, sesion):
    """Una vista mas de un video que se esta mostrando, una sola vez por persona (por sesion)."""
    vistos = sesion.get(VIDEOS_VISTOS, [])
    if video_id in vistos or not videos_visibles().filter(pk=video_id).exists():
        return False
    Video.objects.filter(pk=video_id).update(vistas=F('vistas') + 1)
    sesion[VIDEOS_VISTOS] = [*vistos, video_id][-100:]
    return True


def avisar_video_por_revisar(video):
    """Al administrador: una tienda subio o cambio un video y espera su aprobacion para salir en el sitio."""
    def enviar_aviso():
        from pedidos.avisos import correos_del_sitio

        contexto = _contexto(
            video.tienda, video=video,
            enlace_video=url_absoluta(reverse('admin:planes_video_change', args=[video.pk])),
        )
        enviar(f'Video por revisar: {video.tienda.nombre}', 'sitio_video_por_revisar', contexto, correos_del_sitio())
    _al_confirmar(enviar_aviso)


def aprobar_video(video, usuario=None):
    """El video sale en la portada y en la pagina de la tienda (si esta activa y su plan lo permite). La tienda
    recibe un correo."""
    if usuario is not None and not ve_todas(usuario):
        raise CargoError('Solo el administrador principal aprueba videos.')
    if video.aprobado:
        return video
    Video.objects.filter(pk=video.pk).update(aprobado=True, revisado_el=timezone.now())
    video.refresh_from_db()

    def enviar_aviso():
        enviar(f'Tu video ya está en {ConfiguracionTienda.obtener().nombre}', 'tienda_video_aprobado',
               _contexto(video.tienda, video=video, enlace_videos=url_absoluta(reverse('admin:planes_video_changelist'))),
               correos_de_los_duenos(video.tienda))
    _al_confirmar(enviar_aviso)
    return video


def planes_disponibles():
    return Plan.objects.filter(activo=True)


# --- Cambio de plan que pide la tienda (pedido del dueño el 2026-10-28) -------------------------------------
# La tienda elige otro plan en su panel; el administrador principal lo aprueba o lo rechaza. Al aprobarlo el plan
# cambia en el momento (anuncios, videos y pedidos incluidos) y la mensualidad nueva se cobra desde el proximo dia 1.

class CambioDePlanError(Exception):
    pass


def planes_para_elegir():
    return Plan.objects.filter(activo=True)


@transaction.atomic
def pedir_cambio_de_plan(tienda, plan, usuario=None):
    """La tienda pide pasar a `plan`. Reemplaza un pedido anterior que siguiera esperando."""
    tienda = Tienda.objects.select_for_update().get(pk=tienda.pk)
    if not plan.activo:
        raise CambioDePlanError('Ese plan ya no se ofrece.')
    if plan.pk == tienda.plan_id:
        raise CambioDePlanError(f'Tu tienda ya tiene el plan {plan.nombre}.')
    tienda.plan_pedido = plan
    tienda.plan_pedido_el = timezone.now()
    tienda.save(update_fields=['plan_pedido', 'plan_pedido_el'])

    def enviar_aviso():
        from pedidos.avisos import correos_del_sitio

        contexto = _contexto(
            tienda, plan=plan, plan_actual=tienda.plan, usuario=usuario,
            enlace_tiendas=url_absoluta(reverse('admin:tiendas_tienda_changelist') + '?plan_pedido__isnull=False'),
        )
        enviar(f'Cambio de plan pedido: {tienda.nombre}', 'sitio_cambio_de_plan', contexto, correos_del_sitio())
    _al_confirmar(enviar_aviso)
    return tienda


@transaction.atomic
def cancelar_pedido_de_plan(tienda):
    """La tienda retira su pedido antes de que lo revisen."""
    Tienda.objects.filter(pk=tienda.pk).update(plan_pedido=None, plan_pedido_el=None)


def _ajustar_mensualidad_por_cobrar(tienda, hoy, usuario=None):
    """Si la mensualidad del mes que viene ya se creo con el plan anterior y nadie la ha pagado ni avisado, pasa a
    la del plan nuevo. Devuelve el cargo ajustado o None."""
    proximo = mes_siguiente(hoy)
    cargo = Cargo.objects.select_for_update().filter(
        tienda=tienda, tipo=Tipo.MENSUALIDAD, periodo=proximo, estado=Estado.PENDIENTE,
    ).first()
    if cargo is None:
        return None
    plan = tienda.plan
    if plan is None or plan.mensualidad <= 0:
        return anular_cargo(cargo, usuario, f'La tienda cambió al plan {plan.nombre if plan else "sin plan"}, sin mensualidad.')
    cargo.monto = plan.mensualidad
    cargo.concepto = f'Mensualidad de {nombre_del_mes(proximo)} · Plan {plan.nombre}'
    cargo.save(update_fields=['monto', 'concepto'])
    return cargo


@transaction.atomic
def aprobar_cambio_de_plan(tienda, usuario=None):
    """El plan cambia ya. La mensualidad nueva se cobra desde el proximo dia 1 (la de este mes no se toca)."""
    if usuario is not None and not ve_todas(usuario):
        raise CambioDePlanError('Solo el administrador principal aprueba cambios de plan.')
    tienda = Tienda.objects.select_for_update().select_related('plan_pedido').get(pk=tienda.pk)
    nuevo = tienda.plan_pedido
    if nuevo is None:
        raise CambioDePlanError(f'{tienda.nombre} no tiene un cambio de plan pedido.')
    anterior = tienda.plan
    tienda.plan = nuevo
    tienda.plan_pedido = None
    tienda.plan_pedido_el = None
    tienda.save(update_fields=['plan', 'plan_pedido', 'plan_pedido_el'])
    _ajustar_mensualidad_por_cobrar(tienda, _hoy(), usuario)

    def enviar_aviso():
        enviar(f'Tu tienda ya tiene el plan {nuevo.nombre}', 'tienda_cambio_de_plan',
               _contexto(tienda, aprobado=True, plan=nuevo, plan_anterior=anterior,
                         desde=mes_siguiente(_hoy())),
               correos_de_los_duenos(tienda))
    _al_confirmar(enviar_aviso)
    return tienda


@transaction.atomic
def rechazar_cambio_de_plan(tienda, usuario=None):
    if usuario is not None and not ve_todas(usuario):
        raise CambioDePlanError('Solo el administrador principal rechaza cambios de plan.')
    tienda = Tienda.objects.select_for_update().select_related('plan_pedido').get(pk=tienda.pk)
    pedido = tienda.plan_pedido
    if pedido is None:
        raise CambioDePlanError(f'{tienda.nombre} no tiene un cambio de plan pedido.')
    tienda.plan_pedido = None
    tienda.plan_pedido_el = None
    tienda.save(update_fields=['plan_pedido', 'plan_pedido_el'])

    def enviar_aviso():
        enviar(f'Tu pedido de cambio de plan en {ConfiguracionTienda.obtener().nombre}', 'tienda_cambio_de_plan',
               _contexto(tienda, aprobado=False, plan=pedido), correos_de_los_duenos(tienda))
    _al_confirmar(enviar_aviso)
    return tienda


def cambios_de_plan_pendientes():
    return Tienda.objects.filter(plan_pedido__isnull=False).count()
