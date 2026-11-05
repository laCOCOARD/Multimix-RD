from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from .models import CodigoReferido, Referido

COOKIE_REF = 'ref_codigo'
COOKIE_DIAS = 30


def codigo_de(usuario):
    """Devuelve el CodigoReferido del usuario, creándolo si no existe."""
    codigo, _ = CodigoReferido.objects.get_or_create(usuario=usuario)
    return codigo


def registrar_clic(codigo_str):
    """Incrementa el contador de clics del código. Devuelve True si existía."""
    actualizado = CodigoReferido.objects.filter(codigo=codigo_str).update(clics=F('clics') + 1)
    return bool(actualizado)


def registrar_nuevo_usuario(request, usuario):
    """Llama desde el registro de cuenta: si hay cookie de referido crea el Referido."""
    codigo_str = request.COOKIES.get(COOKIE_REF, '').strip().upper()
    if not codigo_str:
        return
    try:
        codigo = CodigoReferido.objects.select_related('usuario').get(codigo=codigo_str)
    except CodigoReferido.DoesNotExist:
        return
    if codigo.usuario == usuario:
        return
    if Referido.objects.filter(invitado=usuario).exists():
        return
    Referido.objects.create(
        referente=codigo.usuario,
        invitado=usuario,
        ip=request.META.get('REMOTE_ADDR'),
    )


def marcar_tienda_creada(usuario):
    """Cuando se agrega un usuario a una tienda: marca su registro de referido."""
    Referido.objects.filter(invitado=usuario, tienda_creada=False).update(tienda_creada=True)


def estadisticas_de(usuario):
    """Estadísticas del programa de referidos del usuario logueado."""
    codigo = CodigoReferido.objects.filter(usuario=usuario).first()
    if codigo is None:
        return None
    qs = Referido.objects.filter(referente=usuario)
    return {
        'codigo': codigo,
        'clics': codigo.clics,
        'registros': qs.count(),
        'tiendas': qs.filter(tienda_creada=True).count(),
    }


# --- Premios por invitar tiendas (pedido del dueño el 2026-11-02) ----------------------------
# Una tienda invitada cuenta cuando el sitio aprueba su primera mensualidad pagada. Por cada 2 activas, la tienda que
# invito gana un premio: descuento en su proxima mensualidad (se usa dentro de DIAS_PARA_USAR o se pierde) y anuncios
# extra en la portada por DIAS_DE_ANUNCIO. La invitada recibe un descuento en su primera mensualidad.


INVITADAS_POR_PREMIO = 2
DESCUENTO_DEL_PREMIO = Decimal('25')
ANUNCIOS_DEL_PREMIO = 1
DIAS_DE_ANUNCIO = 30
DIAS_DESTACADA = 15
DIAS_PARA_USAR = 90
DESCUENTO_DE_BIENVENIDA = Decimal('10')
# Escalera de premios (pedido del dueño el 2026-11-05). El premio 1 (2 activas) da 25% y un anuncio extra; el 2
# (4 activas) da 50% en lugar del 25% y la tienda sale entre las destacadas; el 3 (6 activas) es un mes gratis y la
# insignia "Tienda embajadora", una sola vez. Desde el 4 (8, 10... activas) vuelve el premio del primer nivel.
NIVELES = {
    1: {'descuento': DESCUENTO_DEL_PREMIO, 'anuncios_extra': ANUNCIOS_DEL_PREMIO, 'dias_destacada': 0, 'embajadora': False},
    2: {'descuento': Decimal('50'), 'anuncios_extra': 0, 'dias_destacada': DIAS_DESTACADA, 'embajadora': False},
    3: {'descuento': Decimal('100'), 'anuncios_extra': 0, 'dias_destacada': 0, 'embajadora': True},
}
# Un mes gratis no se cobra: la mensualidad queda anulada con esta nota (y el premio queda usado en ella).
NOTA_MES_GRATIS = 'Mes gratis'


def nivel(numero):
    """Lo que trae el premio numero `numero` de una tienda."""
    return NIVELES.get(numero, NIVELES[1])


def _premio_usado(premio):
    """Usado: en una mensualidad pagada o por pagar, o en un mes gratis."""
    return premio.cargo_id is not None and (
        premio.cargo.estado != 'anulado' or premio.cargo.nota.startswith(NOTA_MES_GRATIS))


def tienda_del_codigo(codigo_str):
    """La tienda del dueño del codigo (la primera, si tiene varias). None si el codigo no existe o no tiene tienda."""
    from tiendas.models import Tienda

    codigo_str = (codigo_str or '').strip().upper()
    if not codigo_str:
        return None
    codigo = CodigoReferido.objects.filter(codigo=codigo_str).first()
    if codigo is None:
        return None
    return Tienda.objects.filter(usuarios=codigo.usuario).order_by('pk').first()


def vincular_tienda(solicitud):
    """Al crear la tienda de una solicitud que traia codigo: la deja vinculada a la tienda que la invito. Una tienda
    no se invita a si misma ni se vincula dos veces. Devuelve la TiendaReferida o None."""
    from .models import TiendaReferida

    if not solicitud.tienda_id or not solicitud.codigo_referido:
        return None
    if TiendaReferida.objects.filter(tienda_id=solicitud.tienda_id).exists():
        return None
    referente = tienda_del_codigo(solicitud.codigo_referido)
    if referente is None or referente.pk == solicitud.tienda_id:
        return None
    return TiendaReferida.objects.create(
        referente=referente, tienda_id=solicitud.tienda_id, codigo=solicitud.codigo_referido.strip().upper(),
    )


def _es_mensualidad_editable(cargo):
    from planes.models import Cargo

    return (cargo.tipo == Cargo.Tipo.MENSUALIDAD and cargo.estado == Cargo.Estado.PENDIENTE
            and not cargo.enviado_el)


def aplicar_descuentos(cargo, hoy=None):
    """Pone en una mensualidad por pagar los descuentos que le tocan: el de bienvenida (primera mensualidad de una
    tienda invitada) y un premio disponible (uno por mensualidad). Recalcula el monto desde el precio del plan, asi
    que se puede llamar otra vez (por ejemplo, tras un cambio de plan). No toca una mensualidad ya pagada o avisada."""
    from planes.models import Cargo

    from .models import PremioReferido, TiendaReferida

    if not _es_mensualidad_editable(cargo):
        return cargo
    hoy = hoy or timezone.localdate()
    tienda = cargo.tienda
    invitada = TiendaReferida.objects.filter(tienda=tienda).first()
    if invitada and (invitada.cargo_con_descuento_id is None or invitada.cargo_con_descuento.estado == Cargo.Estado.ANULADO):
        ya_pago = Cargo.objects.filter(tienda=tienda, tipo=Cargo.Tipo.MENSUALIDAD, estado=Cargo.Estado.PAGADO).exists()
        if not ya_pago:
            invitada.cargo_con_descuento = cargo
            invitada.save(update_fields=['cargo_con_descuento'])
    if not PremioReferido.objects.filter(cargo=cargo).exists():
        premio = (
            PremioReferido.objects.filter(tienda=tienda, vence__gte=hoy)
            .filter(Q(cargo__isnull=True) | Q(cargo__estado=Cargo.Estado.ANULADO))
            .exclude(cargo__nota__startswith=NOTA_MES_GRATIS)
            .order_by('numero').first()
        )
        if premio:
            premio.cargo = cargo
            premio.save(update_fields=['cargo'])
    lineas, porcentaje = [], Decimal('0')
    if invitada and invitada.cargo_con_descuento_id == cargo.pk:
        porcentaje += DESCUENTO_DE_BIENVENIDA
        lineas.append(f'Bienvenida por llegar invitada por {invitada.referente.nombre}: -{DESCUENTO_DE_BIENVENIDA:g}%.')
    for premio in PremioReferido.objects.filter(cargo=cargo):
        porcentaje += premio.descuento
        if premio.descuento >= 100:
            lineas.append(f'Premio {premio.numero} por invitar tiendas: mes gratis (-100%).')
        else:
            lineas.append(f'Premio {premio.numero} por invitar tiendas: -{premio.descuento.normalize():f}%.')
    if not porcentaje:
        return cargo
    base = tienda.plan.mensualidad if tienda.plan_id and tienda.plan.mensualidad > 0 else cargo.monto
    porcentaje = min(porcentaje, Decimal('100'))
    cargo.detalle = 'Descuentos del programa de referidos:\n' + '\n'.join(lineas)
    if porcentaje >= 100:
        # Mes gratis: no hay nada que pagar. Queda anulada (no es un ingreso ni cierra la tienda) con su motivo.
        cargo.monto = base
        cargo.estado = Cargo.Estado.ANULADO
        cargo.nota = f'{NOTA_MES_GRATIS} por el programa de referidos.'
        cargo.revisado_el = timezone.now()
        cargo.save(update_fields=['monto', 'detalle', 'estado', 'nota', 'revisado_el'])
        return cargo
    cargo.monto = max((base * (100 - porcentaje) / 100).quantize(Decimal('0.01')), Decimal('0.01'))
    cargo.save(update_fields=['monto', 'detalle'])
    return cargo


def _mensualidad_por_pagar(tienda):
    from planes.models import Cargo

    return (
        Cargo.objects.filter(tienda=tienda, tipo=Cargo.Tipo.MENSUALIDAD, estado=Cargo.Estado.PENDIENTE,
                             enviado_el__isnull=True)
        .order_by('periodo').first()
    )


def al_pagar_mensualidad(cargo, hoy=None):
    """Lo llama planes.services.aprobar_cargo: si era la primera mensualidad pagada de una tienda invitada, esa tienda
    queda activa y, por cada INVITADAS_POR_PREMIO activas, la que la invito gana un premio. Devuelve los premios
    nuevos."""
    from planes.models import Cargo

    from .models import PremioReferido, TiendaReferida

    if cargo.tipo != Cargo.Tipo.MENSUALIDAD:
        return []
    invitada = (
        TiendaReferida.objects.select_for_update().select_related('referente')
        .filter(tienda_id=cargo.tienda_id, activa_desde__isnull=True).first()
    )
    if invitada is None:
        return []
    hoy = hoy or timezone.localdate()
    invitada.activa_desde = timezone.now()
    invitada.save(update_fields=['activa_desde'])
    referente = invitada.referente
    activas = TiendaReferida.objects.filter(referente=referente, activa_desde__isnull=False).count()
    ganados = activas // INVITADAS_POR_PREMIO
    tiene = PremioReferido.objects.filter(tienda=referente).count()
    nuevos = []
    for numero in range(tiene + 1, ganados + 1):
        datos = nivel(numero)
        premio = PremioReferido.objects.create(
            tienda=referente, numero=numero, descuento=datos['descuento'], anuncios_extra=datos['anuncios_extra'],
            anuncios_hasta=hoy + timedelta(days=DIAS_DE_ANUNCIO if datos['anuncios_extra'] else 0),
            destacada_hasta=hoy + timedelta(days=datos['dias_destacada']) if datos['dias_destacada'] else None,
            vence=hoy + timedelta(days=DIAS_PARA_USAR),
        )
        premio.embajadora = datos['embajadora']
        nuevos.append(premio)
        if datos['embajadora'] and referente.embajadora_desde is None:
            referente.embajadora_desde = hoy
            referente.save(update_fields=['embajadora_desde'])
    if nuevos:
        pendiente = _mensualidad_por_pagar(referente)
        if pendiente:
            aplicar_descuentos(pendiente, hoy)
        _avisar_premios(referente, nuevos)
    return nuevos


def _avisar_premios(tienda, premios):
    from core.correo import enviar
    from planes.services import _contexto, correos_de_los_duenos

    def avisar():
        enviar(
            f'¡Ganaste un premio por invitar tiendas a {_contexto(tienda)["sitio"]}!', 'tienda_premio_referidos',
            _contexto(tienda, premios=premios, por_premio=INVITADAS_POR_PREMIO), correos_de_los_duenos(tienda),
        )
    transaction.on_commit(avisar)


def anuncios_extra(tienda, hoy=None):
    """Anuncios de la portada que la tienda tiene de mas por sus premios vigentes."""
    from .models import PremioReferido

    hoy = hoy or timezone.localdate()
    return PremioReferido.objects.filter(tienda=tienda, anuncios_hasta__gte=hoy).aggregate(
        total=Sum('anuncios_extra'))['total'] or 0


def programa_de(tienda, hoy=None):
    """Lo que el panel del vendedor muestra del programa: invitadas, activas, avance al proximo premio y premios."""
    from tiendas.models import SolicitudTienda

    from .models import PremioReferido, TiendaReferida

    hoy = hoy or timezone.localdate()
    invitadas = TiendaReferida.objects.filter(referente=tienda)
    activas = invitadas.filter(activa_desde__isnull=False).count()
    codigos = list(CodigoReferido.objects.filter(usuario__in=tienda.usuarios.all()).values_list('codigo', flat=True))
    premios = list(PremioReferido.objects.filter(tienda=tienda).select_related('cargo').order_by('-numero'))
    for premio in premios:
        premio.anuncios_vigentes = premio.anuncios_extra > 0 and premio.anuncios_hasta >= hoy
        premio.destacada_vigente = premio.destacada_hasta is not None and premio.destacada_hasta >= hoy
        premio.usado = _premio_usado(premio)
        premio.mes_gratis = premio.usado and premio.cargo.estado == 'anulado'
        premio.disponible = not premio.usado and premio.vence >= hoy
    proximo = activas // INVITADAS_POR_PREMIO + 1
    return {
        'solicitudes': SolicitudTienda.objects.filter(codigo_referido__in=codigos).count() if codigos else 0,
        'tiendas': invitadas.count(),
        'activas': activas,
        'avance': activas % INVITADAS_POR_PREMIO,
        'por_premio': INVITADAS_POR_PREMIO,
        'porcentaje_avance': int(activas % INVITADAS_POR_PREMIO * 100 / INVITADAS_POR_PREMIO),
        'premios': premios,
        'descuento_premio': DESCUENTO_DEL_PREMIO,
        'descuento_bienvenida': DESCUENTO_DE_BIENVENIDA,
        'dias_anuncio': DIAS_DE_ANUNCIO,
        'dias_destacada': DIAS_DESTACADA,
        'proximo': {'numero': proximo, 'invitadas': proximo * INVITADAS_POR_PREMIO, **nivel(proximo)},
        'escalera': [{'invitadas': numero * INVITADAS_POR_PREMIO, **nivel(numero)} for numero in sorted(NIVELES)],
        'embajadora': tienda.embajadora_desde is not None,
    }
