from django.db.models import F

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
