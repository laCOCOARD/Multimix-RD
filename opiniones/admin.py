from django.contrib import admin
from django.core.exceptions import PermissionDenied

from tiendas.panel import AdminDeTienda

from .models import Resena


@admin.register(Resena)
class ResenaAdmin(AdminDeTienda, admin.ModelAdmin):
    """Moderacion de reseñas. Cada tienda ve las suyas; publicarlas o rechazarlas es del administrador principal,
    para que una tienda no pueda esconder las opiniones que no le gustan."""

    list_display = ['producto', 'autor', 'estrellas', 'comentario_corto', 'compra_verificada', 'estado', 'creado']
    list_filter = ['estado', 'estrellas', 'compra_verificada']
    search_fields = ['producto__nombre', 'comentario', 'usuario__email']
    list_select_related = ['producto', 'usuario']
    actions = ['publicar', 'rechazar']
    fields = ['producto', 'tienda', 'autor', 'estrellas', 'comentario', 'compra_verificada', 'estado', 'creado']
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def _moderar(self, request, queryset, estado, hecho):
        if not request.user.has_perm('opiniones.change_resena'):
            raise PermissionDenied
        self.message_user(request, f'{queryset.update(estado=estado)} reseña(s) {hecho}.')

    @admin.action(description='Publicar', permissions=['change'])
    def publicar(self, request, queryset):
        self._moderar(request, queryset, Resena.Estado.APROBADA, 'publicadas')

    @admin.action(description='Rechazar (no se muestra)', permissions=['change'])
    def rechazar(self, request, queryset):
        self._moderar(request, queryset, Resena.Estado.RECHAZADA, 'rechazadas')

    @admin.display(description='Cliente')
    def autor(self, resena):
        return resena.usuario.get_full_name() or resena.usuario.email

    @admin.display(description='Comentario')
    def comentario_corto(self, resena):
        return resena.comentario[:90]
