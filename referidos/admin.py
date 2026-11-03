from django.contrib import admin

from .models import CodigoReferido, PremioReferido, Referido, TiendaReferida


@admin.register(CodigoReferido)
class CodigoReferidoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'codigo', 'clics', 'creado')
    search_fields = ('usuario__email', 'usuario__first_name', 'codigo')
    readonly_fields = ('clics', 'creado')


@admin.register(Referido)
class ReferidoAdmin(admin.ModelAdmin):
    list_display = ('referente', 'invitado', 'creado', 'tienda_creada')
    list_filter = ('tienda_creada',)
    search_fields = ('referente__email', 'invitado__email')
    readonly_fields = ('ip', 'creado')
    date_hierarchy = 'creado'


class SoloElAdministrador(admin.ModelAdmin):
    """Programa de referidos entre tiendas: solo lo maneja el administrador principal. Cada vendedor ve lo suyo en el
    inicio de su panel (Centro de crecimiento)."""

    def has_module_permission(self, request):
        from tiendas.services import ve_todas

        return ve_todas(request.user)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)


@admin.register(TiendaReferida)
class TiendaReferidaAdmin(SoloElAdministrador):
    list_display = ('tienda', 'referente', 'codigo', 'activa_desde', 'creada')
    list_filter = ('activa_desde',)
    search_fields = ('tienda__nombre', 'referente__nombre', 'codigo')
    readonly_fields = ('creada', 'cargo_con_descuento')


@admin.register(PremioReferido)
class PremioReferidoAdmin(SoloElAdministrador):
    list_display = ('tienda', 'numero', 'descuento', 'vence', 'cargo', 'anuncios_extra', 'anuncios_hasta', 'creado')
    search_fields = ('tienda__nombre',)
    readonly_fields = ('creado',)
