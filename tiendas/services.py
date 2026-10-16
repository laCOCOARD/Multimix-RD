"""Tiendas: quien administra cual, el acceso de los vendedores al panel y el directorio publico."""
from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import Count, Q
from django.utils import timezone

from .models import Banner, Tienda

GRUPO_VENDEDORES = 'Vendedores'

# Lo que un vendedor puede hacer en el panel. El panel ademas le muestra solo lo de sus tiendas
# (tiendas.panel.AdminDeTienda); las categorias y la configuracion general quedan para el administrador.
PERMISOS_VENDEDOR = {
    'tiendas': ['view_tienda', 'change_tienda', 'view_banner', 'add_banner', 'change_banner', 'delete_banner'],
    'catalogo': [
        'view_producto', 'add_producto', 'change_producto', 'delete_producto',
        'view_fotoproducto', 'add_fotoproducto', 'change_fotoproducto', 'delete_fotoproducto',
    ],
    'pedidos': [
        'view_pedido', 'change_pedido', 'delete_pedido', 'view_detallepedido', 'view_eventopedido',
        'view_solicituddevolucion', 'change_solicituddevolucion',
        'view_zonaenvio', 'add_zonaenvio', 'change_zonaenvio', 'delete_zonaenvio',
    ],
    'promociones': ['view_cupon', 'add_cupon', 'change_cupon', 'delete_cupon'],
    # Los pagos se revisan (aprobar o rechazar); no se crean ni se borran a mano.
    'pagos': ['view_pago', 'change_pago', 'view_liquidacion'],
    # Las reseñas se ven; publicarlas o rechazarlas es del administrador principal.
    'opiniones': ['view_resena'],
    # Sin 'core': las cuentas bancarias que ve el cliente las registra solo el administrador principal, para que
    # nadie cambie a donde transfieren los clientes.
}


def ve_todas(usuario):
    """Solo el administrador principal (superusuario) ve y administra todas las tiendas."""
    return usuario.is_active and usuario.is_superuser


def tiendas_de(usuario):
    """Tiendas que el usuario puede administrar en el panel."""
    if ve_todas(usuario):
        return Tienda.objects.all()
    if not usuario.is_authenticated:
        return Tienda.objects.none()
    return Tienda.objects.filter(usuarios=usuario)


def preparar_grupo_vendedores(using=DEFAULT_DB_ALIAS, **kwargs):
    """Crea el grupo Vendedores con sus permisos. Corre despues de cada `migrate`."""
    if Group._meta.db_table not in connections[using].introspection.table_names():
        return None
    # Los permisos de cada app se crean al terminar su migracion; aqui se adelantan los que falten.
    for app in PERMISOS_VENDEDOR:
        create_permissions(apps.get_app_config(app), verbosity=0, using=using)
    grupo, _ = Group.objects.using(using).get_or_create(name=GRUPO_VENDEDORES)
    # `set` y no `add`: un permiso que se quita de la lista tambien se le quita al grupo al migrar.
    filtro = Q()
    for app, codigos in PERMISOS_VENDEDOR.items():
        filtro |= Q(content_type__app_label=app, codename__in=codigos)
    grupo.permissions.set(Permission.objects.using(using).filter(filtro))
    return grupo


def dar_acceso_al_panel(usuarios):
    """Deja a los vendedores listos para entrar al panel: usuario del personal y grupo Vendedores."""
    grupo = Group.objects.filter(name=GRUPO_VENDEDORES).first() or preparar_grupo_vendedores()
    for usuario in usuarios:
        if not usuario.is_staff:
            usuario.is_staff = True
            usuario.save(update_fields=['is_staff'])
        usuario.groups.add(grupo)


def banners_de(tienda):
    """Banners activos y dentro de su vigencia, en el orden que eligio la tienda."""
    ahora = timezone.now()
    return list(
        Banner.objects.filter(tienda=tienda, activo=True)
        .filter(Q(vigente_desde__isnull=True) | Q(vigente_desde__lte=ahora))
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=ahora))
    )


def directorio():
    """Tiendas activas con la cantidad de productos que tienen a la venta."""
    a_la_venta = Q(productos__activo=True, productos__categoria__activa=True)
    # El orden se pide a mano: al agrupar, Django no aplica el `ordering` del modelo.
    return (
        Tienda.objects.activas().annotate(total_productos=Count('productos', filter=a_la_venta))
        .order_by('orden', 'nombre')
    )


def tienda_principal():
    """La tienda mas antigua que siga activa: recibe los enlaces de cuando habia una sola tienda."""
    return Tienda.objects.activas().order_by('pk').first()
