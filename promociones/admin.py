from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from pedidos.models import Pedido
from tiendas.panel import AdminDeTienda

from .models import Cupon


@admin.register(Cupon)
class CuponAdmin(AdminDeTienda, admin.ModelAdmin):
    list_display = ['codigo', 'descuento', 'compra_minima', 'vigente_desde', 'vigente_hasta', 'usos', 'estado', 'activo']
    list_editable = ['activo']
    list_filter = ['activo', 'tipo']
    search_fields = ['codigo']
    readonly_fields = ['usos_actuales', 'pedidos_con_cupon']
    fieldsets = [
        (None, {'fields': ['tienda', 'codigo', 'tipo', 'valor', 'compra_minima', 'activo']}),
        ('Vigencia y límite', {'fields': ['vigente_desde', 'vigente_hasta', 'usos_maximos']}),
        ('Usos', {'fields': ['usos_actuales', 'pedidos_con_cupon']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            total_pedidos=Count('pedidos', filter=~Q(pedidos__estado=Pedido.Estado.CANCELADO)),
        )

    @admin.display(description='Descuento', ordering='valor')
    def descuento(self, cupon):
        if cupon.tipo == Cupon.Tipo.PORCENTAJE:
            return f'{cupon.valor:g} %'
        return f'RD$ {cupon.valor:,.2f}'

    @admin.display(description='Usos', ordering='usos_actuales')
    def usos(self, cupon):
        maximo = '∞' if cupon.usos_maximos is None else cupon.usos_maximos
        return f'{cupon.usos_actuales} / {maximo}'

    @admin.display(description='Estado')
    def estado(self, cupon):
        if not cupon.activo:
            clase, texto = 'panel-inactiva', 'Inactivo'
        elif not cupon.vigente:
            clase, texto = 'panel-bajo', 'Fuera de vigencia'
        elif cupon.usos_restantes == 0:
            clase, texto = 'panel-agotado', 'Sin usos'
        else:
            clase, texto = 'panel-ok', 'Disponible'
        return format_html('<span class="panel-etiqueta {}">{}</span>', clase, texto)

    @admin.display(description='Pedidos no cancelados con este cupón')
    def pedidos_con_cupon(self, cupon):
        return getattr(cupon, 'total_pedidos', 0)
