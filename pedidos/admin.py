from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from core.telefonos import formatear_telefono
from core.templatetags.moneda import formatear_monto

from . import services
from .models import DetallePedido, Pedido, ZonaEnvio
from .whatsapp import enlace_al_cliente

Estado = Pedido.Estado


@admin.register(ZonaEnvio)
class ZonaEnvioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tarifa', 'activa', 'orden']
    list_editable = ['tarifa', 'activa', 'orden']
    list_filter = ['activa']
    search_fields = ['nombre']


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    can_delete = False
    fields = ['producto', 'nombre_producto', 'precio', 'cantidad', 'importe']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Precio unitario')
    def precio(self, detalle):
        return formatear_monto(detalle.precio_unitario)

    @admin.display(description='Subtotal')
    def importe(self, detalle):
        return formatear_monto(detalle.subtotal)


def _accion_de_estado(estado, descripcion):
    @admin.action(description=descripcion)
    def accion(modeladmin, request, queryset):
        modeladmin.cambiar_estado_masivo(request, queryset, estado)
    accion.__name__ = f'marcar_{estado}'
    return accion


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    change_form_template = 'admin/pedidos/pedido/change_form.html'
    date_hierarchy = 'creado'
    list_display = [
        'numero', 'creado', 'nombre', 'whatsapp_cliente', 'metodo_entrega', 'metodo_pago',
        'total_formateado', 'estado_con_color', 'aviso_transferencia',
    ]
    list_filter = ['estado', 'metodo_entrega', 'metodo_pago', 'transferencia_realizada', 'zona', 'creado']
    search_fields = ['numero', 'nombre', 'telefono', 'correo', 'referencia_transferencia']
    list_select_related = ['zona']
    list_per_page = 40
    inlines = [DetallePedidoInline]
    actions = [
        _accion_de_estado(Estado.PAGADO, 'Marcar como Pagado'),
        _accion_de_estado(Estado.LISTO, 'Marcar como Listo para recoger'),
        _accion_de_estado(Estado.ENVIADO, 'Marcar como Enviado'),
        _accion_de_estado(Estado.ENTREGADO, 'Marcar como Entregado'),
        _accion_de_estado(Estado.CANCELADO, 'Marcar como Cancelado'),
    ]
    fieldsets = [
        ('Pedido', {'fields': ['numero', 'estado_con_color', 'creado', 'fecha_pago', 'fecha_entrega', 'enlace_publico']}),
        ('Cliente', {'fields': ['nombre', 'whatsapp_cliente', 'correo']}),
        ('Entrega', {'fields': ['metodo_entrega', 'zona', 'direccion', 'referencia']}),
        ('Pago', {'fields': ['metodo_pago', 'transferencia_realizada', 'referencia_transferencia']}),
        ('Montos', {'fields': ['subtotal_formateado', 'cupon_aplicado', 'envio_formateado', 'total_formateado']}),
        ('Notas', {'fields': ['notas_cliente', 'notas_internas']}),
    ]
    campos_editables = ['notas_internas']

    def get_readonly_fields(self, request, obj=None):
        campos = [campo for _, opciones in self.fieldsets for campo in opciones['fields']]
        return [campo for campo in campos if campo not in self.campos_editables]

    def has_add_permission(self, request):
        return False

    # Eliminar tambien pasa por la capa de servicios, para que el stock y el cupon queden bien.

    def delete_model(self, request, obj):
        services.eliminar_pedido(obj)

    def delete_queryset(self, request, queryset):
        for pedido in queryset.order_by('creado'):
            services.eliminar_pedido(pedido)

    def get_urls(self):
        propias = [
            path(
                '<path:object_id>/estado/', self.admin_site.admin_view(require_POST(self.cambiar_estado_vista)),
                name='pedidos_pedido_estado',
            ),
        ]
        return propias + super().get_urls()

    # --- Cambios de estado (siempre por la capa de servicios) -----------------------

    def cambiar_estado_masivo(self, request, queryset, estado):
        if not self.has_change_permission(request):
            raise PermissionDenied
        hechos = 0
        for pedido in queryset.order_by('creado'):
            try:
                services.cambiar_estado(pedido, estado)
                hechos += 1
            except services.PedidoError as error:
                self.message_user(request, error.mensaje, messages.ERROR)
        if hechos:
            self.message_user(
                request, f'{hechos} pedido(s) pasaron a "{Estado(estado).label}".', messages.SUCCESS,
            )

    def cambiar_estado_vista(self, request, object_id):
        pedido = self.get_object(request, unquote(object_id))
        if pedido is None:
            raise Http404
        if not self.has_change_permission(request, pedido):
            raise PermissionDenied
        try:
            pedido = services.cambiar_estado(pedido, request.POST.get('estado', ''))
        except services.PedidoError as error:
            self.message_user(request, error.mensaje, messages.ERROR)
        else:
            self.message_user(
                request, f'El pedido {pedido.numero} pasó a "{pedido.get_estado_display()}".', messages.SUCCESS,
            )
        return redirect(reverse('admin:pedidos_pedido_change', args=[pedido.pk]))

    def change_view(self, request, object_id, form_url='', extra_context=None):
        pedido = self.get_object(request, unquote(object_id))
        contexto = dict(extra_context or {})
        if pedido is not None and self.has_change_permission(request, pedido):
            contexto['transiciones'] = [
                (estado.value, estado.label) for estado in services.transiciones_permitidas(pedido)
            ]
        return super().change_view(request, object_id, form_url, contexto)

    # --- Columnas -------------------------------------------------------------------

    @admin.display(description='Teléfono', ordering='telefono')
    def whatsapp_cliente(self, pedido):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" title="Escribir por WhatsApp">{} ↗</a>',
            enlace_al_cliente(pedido), formatear_telefono(pedido.telefono),
        )

    @admin.display(description='Estado', ordering='estado')
    def estado_con_color(self, pedido):
        return format_html(
            '<span class="panel-estado panel-estado-{}">{}</span>', pedido.estado, pedido.get_estado_display(),
        )

    @admin.display(description='Aviso', boolean=False)
    def aviso_transferencia(self, pedido):
        if pedido.estado == Estado.PENDIENTE and pedido.transferencia_realizada:
            return format_html('<span class="panel-etiqueta panel-bajo">{}</span>', 'Dice que transfirió')
        return ''

    @admin.display(description='Total', ordering='total')
    def total_formateado(self, pedido):
        return formatear_monto(pedido.total)

    @admin.display(description='Subtotal')
    def subtotal_formateado(self, pedido):
        return formatear_monto(pedido.subtotal)

    @admin.display(description='Costo de envío')
    def envio_formateado(self, pedido):
        return formatear_monto(pedido.costo_envio)

    @admin.display(description='Cupón y descuento')
    def cupon_aplicado(self, pedido):
        if not pedido.codigo_cupon:
            return 'Sin cupón'
        return f'{pedido.codigo_cupon}: -{formatear_monto(pedido.descuento)}'

    @admin.display(description='Página del cliente')
    def enlace_publico(self, pedido):
        return format_html('<a href="{}" target="_blank" rel="noopener">Ver confirmación ↗</a>', pedido.get_absolute_url())
