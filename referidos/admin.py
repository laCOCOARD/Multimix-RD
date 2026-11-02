from django.contrib import admin

from .models import CodigoReferido, Referido


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
