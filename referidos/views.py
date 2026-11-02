from datetime import timedelta

from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import services


@login_not_required
@require_GET
def registrar_clic(request, codigo):
    """Guarda el código de referido en una cookie (30 días) y redirige a /vender/."""
    codigo = codigo.strip().upper()
    # No contar si el usuario autenticado es el dueño del código
    if request.user.is_authenticated:
        from .models import CodigoReferido
        if CodigoReferido.objects.filter(codigo=codigo, usuario=request.user).exists():
            return redirect('tiendas:vender')
    services.registrar_clic(codigo)
    respuesta = redirect('tiendas:vender')
    expira = timezone.now() + timedelta(days=services.COOKIE_DIAS)
    respuesta.set_cookie(
        services.COOKIE_REF, codigo,
        expires=expira,
        httponly=True,
        samesite='Lax',
        secure=request.is_secure(),
    )
    return respuesta
