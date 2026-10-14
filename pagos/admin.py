from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.views.decorators.http import require_POST
from django.utils.html import format_html

from core.templatetags.moneda import formatear_monto
from pedidos.services import PedidoError
from tiendas.models import Tienda
from tiendas.panel import AdminDeTienda
from tiendas.services import ve_todas

from . import liquidaciones, services
from .models import Liquidacion, Pago


@admin.register(Pago)
class PagoAdmin(AdminDeTienda, admin.ModelAdmin):
    """Conciliacion: el vendedor revisa los comprobantes y aprueba o rechaza. Los pagos no se crean ni se borran aqui."""

    date_hierarchy = 'creado'
    list_display = ['referencia', 'pedido_enlazado', 'creado', 'metodo', 'monto_formateado', 'estado_con_color', 'tiene_comprobante']
    list_filter = ['estado', 'metodo', 'creado']
    search_fields = ['referencia', 'pedido__numero', 'pedido__nombre', 'pedido__telefono', 'referencia_cliente']
    list_select_related = ['pedido']
    list_per_page = 40
    actions = ['aprobar', 'rechazar']
    fieldsets = [
        ('Pago', {'fields': [
            'referencia', 'pedido_enlazado', 'tienda', 'metodo', 'monto_formateado', 'estado_con_color', 'creado',
        ]}),
        ('Transferencia', {'fields': ['referencia_cliente', 'vista_del_comprobante']}),
        ('Revisión', {'fields': ['revisado_en', 'revisado_por', 'nota']}),
        ('Pasarela', {'classes': ['collapse'], 'fields': ['proveedor', 'codigo_autorizacion']}),
    ]
    campos_editables = ['nota']

    def get_readonly_fields(self, request, obj=None):
        campos = [campo for _, opciones in self.fieldsets for campo in opciones['fields']]
        return [campo for campo in campos if campo not in self.campos_editables]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Un pago solo desaparece junto con su pedido: el panel pide este permiso al eliminar el pedido.
        # Desde la pantalla de pagos no hay ni boton ni accion para borrar.
        return request.user.has_perm('pedidos.delete_pedido')

    def get_actions(self, request):
        acciones = super().get_actions(request)
        acciones.pop('delete_selected', None)
        return acciones

    def delete_view(self, request, object_id, extra_context=None):
        raise PermissionDenied

    def change_view(self, request, object_id, form_url='', extra_context=None):
        return super().change_view(request, object_id, form_url, {'show_delete': False, **(extra_context or {})})

    def _resolver(self, request, queryset, accion, hecho):
        if not self.has_change_permission(request):
            raise PermissionDenied
        total = 0
        for pago in queryset.order_by('creado'):
            try:
                accion(pago, request.user)
                total += 1
            except (services.PagoError, PedidoError) as error:
                self.message_user(request, error.mensaje, messages.ERROR)
        if total:
            self.message_user(request, f'{total} pago(s) {hecho}.', messages.SUCCESS)

    @admin.action(description='Aprobar pago (el pedido pasa a Pagado)')
    def aprobar(self, request, queryset):
        self._resolver(request, queryset, services.aprobar_pago, 'aprobados')

    @admin.action(description='Rechazar comprobante (el cliente puede enviar otro)')
    def rechazar(self, request, queryset):
        self._resolver(request, queryset, services.rechazar_pago, 'rechazados')

    # --- Columnas -------------------------------------------------------------------

    @admin.display(description='Pedido', ordering='pedido__numero')
    def pedido_enlazado(self, pago):
        return format_html(
            '<a href="{}">{}</a> · {}', reverse('admin:pedidos_pedido_change', args=[pago.pedido_id]),
            pago.pedido.numero, pago.pedido.nombre,
        )

    @admin.display(description='Monto', ordering='monto')
    def monto_formateado(self, pago):
        return formatear_monto(pago.monto)

    @admin.display(description='Estado', ordering='estado')
    def estado_con_color(self, pago):
        return format_html('<span class="panel-estado panel-pago-{}">{}</span>', pago.estado, pago.get_estado_display())

    @admin.display(description='Comprobante', boolean=True)
    def tiene_comprobante(self, pago):
        return bool(pago.comprobante)

    @admin.display(description='Comprobante')
    def vista_del_comprobante(self, pago):
        if not pago.comprobante:
            return 'El cliente no adjuntó comprobante.'
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener"><img src="{0}" alt="Comprobante" class="panel-comprobante"></a>',
            pago.comprobante.url,
        )


@admin.register(Liquidacion)
class LiquidacionAdmin(AdminDeTienda, admin.ModelAdmin):
    """Historial de cierres con cada tienda. Los registra el administrador principal desde "Saldos por tienda";
    cada tienda ve los suyos."""

    change_list_template = 'admin/pagos/liquidacion/change_list.html'
    date_hierarchy = 'creada'
    list_display = ['creada', 'tienda', 'pedidos_incluidos', 'vendido', 'comision_cobrada', 'saldo', 'nota']
    search_fields = ['nota', 'tienda__nombre']
    list_select_related = ['tienda']
    fields = [
        'tienda', 'creada', 'creada_por', 'pedidos_incluidos', 'ventas', 'cobrado_por_el_sitio',
        'comision_porcentaje', 'comision', 'ajustes', 'monto', 'nota',
    ]
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        propias = [
            path('saldos/', self.admin_site.admin_view(self.saldos_vista), name='pagos_liquidacion_saldos'),
            path(
                'saldos/<int:tienda_id>/liquidar/', self.admin_site.admin_view(require_POST(self.liquidar_vista)),
                name='pagos_liquidacion_liquidar',
            ),
        ]
        return propias + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {'puede_liquidar': ve_todas(request.user), **(extra_context or {})})

    def saldos_vista(self, request):
        """Solo el administrador principal: lo que hay que depositarle a cada tienda."""
        if not ve_todas(request.user):
            raise PermissionDenied
        saldos = [liquidaciones.saldo_de(tienda) for tienda in Tienda.objects.order_by('orden', 'nombre')]
        for saldo in saldos:
            saldo.debe = -saldo.monto
        return render(request, 'admin/pagos/liquidacion/saldos.html', {
            **self.admin_site.each_context(request),
            'title': 'Saldos por tienda',
            'saldos': saldos,
            'opts': self.model._meta,
        })

    def liquidar_vista(self, request, tienda_id):
        if not ve_todas(request.user):
            raise PermissionDenied
        tienda = get_object_or_404(Tienda, pk=tienda_id)
        try:
            liquidacion = liquidaciones.liquidar(tienda, request.user, request.POST.get('nota', ''))
        except liquidaciones.LiquidacionError as error:
            self.message_user(request, error.mensaje, messages.ERROR)
        else:
            if liquidacion.monto >= 0:
                texto = f'Liquidación de {tienda.nombre} registrada: {formatear_monto(liquidacion.monto)} depositados.'
            else:
                texto = f'Liquidación de {tienda.nombre} registrada: la tienda te debía {formatear_monto(-liquidacion.monto)}.'
            self.message_user(request, texto, messages.SUCCESS)
        return redirect(reverse('admin:pagos_liquidacion_saldos'))

    @admin.display(description='Vendido', ordering='ventas')
    def vendido(self, liquidacion):
        return formatear_monto(liquidacion.ventas)

    @admin.display(description='Comisión', ordering='comision')
    def comision_cobrada(self, liquidacion):
        return f'{formatear_monto(liquidacion.comision)} ({liquidacion.comision_porcentaje.normalize():f}%)'

    @admin.display(description='Saldo', ordering='monto')
    def saldo(self, liquidacion):
        if liquidacion.monto >= 0:
            return f'{formatear_monto(liquidacion.monto)} depositados'
        return f'La tienda debía {formatear_monto(-liquidacion.monto)}'
