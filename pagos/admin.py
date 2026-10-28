from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.views.decorators.http import require_POST
from django.utils.html import format_html, format_html_join

from core.archivos import ERRORES_DE_ALMACENAMIENTO, hay_almacenamiento_privado
from core.templatetags.moneda import formatear_monto
from pedidos.services import PedidoError
from tiendas.models import Tienda
from tiendas.panel import AdminDeTienda
from tiendas.services import ve_todas

from . import liquidaciones, services
from .models import Liquidacion, Pago


@admin.register(Pago)
class PagoAdmin(AdminDeTienda, admin.ModelAdmin):
    """Conciliacion: el vendedor revisa los comprobantes y aprueba o rechaza. Si el cliente transfirio a las cuentas del
    sitio, solo el administrador principal lo hace (`services.puede_resolver`). Los pagos no se crean ni se borran aqui."""

    date_hierarchy = 'creado'
    list_display = ['referencia', 'pedido_enlazado', 'creado', 'metodo', 'monto_formateado', 'estado_con_color', 'tiene_comprobante', 'quien_confirma']
    list_filter = ['estado', 'metodo', 'pedido__cobra_el_sitio', 'creado']
    search_fields = ['referencia', 'pedido__numero', 'pedido__nombre', 'pedido__telefono', 'referencia_cliente']
    list_select_related = ['pedido']
    list_per_page = 40
    actions = ['aprobar', 'rechazar']
    fieldsets = [
        ('Pago', {'fields': [
            'referencia', 'pedido_enlazado', 'tienda', 'metodo', 'monto_formateado', 'estado_con_color', 'creado',
            'quien_confirma',
        ]}),
        ('Transferencia', {'fields': ['referencia_cliente', 'vista_del_comprobante']}),
        ('Revisión', {'fields': ['revisado_en', 'revisado_por', 'nota']}),
        ('Pasarela', {'classes': ['collapse'], 'fields': ['proveedor', 'codigo_autorizacion']}),
    ]
    campos_editables = ['nota']

    def get_list_filter(self, request):
        filtros = super().get_list_filter(request)
        if ve_todas(request.user):
            return filtros
        return [f for f in filtros if f != 'pedido__cobra_el_sitio']

    def get_list_display(self, request):
        columnas = super().get_list_display(request)
        if ve_todas(request.user):
            return columnas
        return [c for c in columnas if c != 'quien_confirma']

    def get_fieldsets(self, request, obj=None):
        if ve_todas(request.user):
            return self.fieldsets
        return [(titulo, {**opciones, 'fields': [c for c in opciones['fields'] if c != 'quien_confirma']})
                for titulo, opciones in self.fieldsets if titulo != 'Pasarela']

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

    def get_urls(self):
        propias = [
            path(
                '<path:object_id>/comprobante/', self.admin_site.admin_view(self.comprobante_vista),
                name='pagos_pago_comprobante',
            ),
        ]
        return propias + super().get_urls()

    def comprobante_vista(self, request, object_id):
        """El comprobante, leido del almacenamiento privado. Solo para quien ve ese pago (`get_object` filtra por
        tienda): el archivo no tiene una direccion publica."""
        pago = self.get_object(request, unquote(object_id))
        if pago is None or not self.has_view_permission(request, pago):
            raise Http404
        if not pago.comprobante:
            raise Http404
        try:
            archivo = pago.almacenamiento_del_comprobante.open(pago.comprobante.name)
        except (FileNotFoundError, *ERRORES_DE_ALMACENAMIENTO):
            raise Http404('No se encontró el archivo del comprobante.')
        respuesta = FileResponse(archivo, content_type='image/webp')
        respuesta['Cache-Control'] = 'private, no-store'
        respuesta['Content-Disposition'] = f'inline; filename="comprobante-{pago.referencia}.webp"'
        return respuesta

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

    @admin.display(description='Lo confirma', ordering='pedido__cobra_el_sitio')
    def quien_confirma(self, pago):
        return 'El sitio' if pago.pedido.cobra_el_sitio else 'La tienda'

    @admin.display(description='Comprobante', boolean=True)
    def tiene_comprobante(self, pago):
        return bool(pago.comprobante)

    @admin.display(description='Comprobante')
    def vista_del_comprobante(self, pago):
        if not pago.comprobante:
            return 'El cliente no adjuntó comprobante.'
        enlace = format_html(
            '<a href="{0}" target="_blank" rel="noopener"><img src="{0}" alt="Comprobante" class="panel-comprobante"></a>',
            reverse('admin:pagos_pago_comprobante', args=[pago.pk]),
        )
        if not hay_almacenamiento_privado():
            enlace += format_html(
                '<p class="help">{}</p>',
                'Este comprobante está en el almacenamiento público de las fotos. Para guardarlos aparte, configura '
                'SUPABASE_S3_BUCKET_PRIVADO (docs/RENDER.md).',
            )
        return enlace


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
        'cobrado_por_la_tienda', 'comision_porcentaje', 'comision', 'comision_de_lo_cobrado_por_la_tienda', 'ajustes',
        'costo_transferencia', 'monto', 'nota', 'detalle_de_pedidos',
    ]
    readonly_fields = fields

    def get_fields(self, request, obj=None):
        # Lo que cobra el banco por el deposito es un gasto del sitio: no es asunto de la tienda.
        if ve_todas(request.user):
            return self.fields
        return [campo for campo in self.fields if campo != 'costo_transferencia']

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
            liquidacion = liquidaciones.liquidar(
                tienda, request.user, request.POST.get('nota', ''), request.POST.get('costo_transferencia', ''),
            )
        except liquidaciones.LiquidacionError as error:
            self.message_user(request, error.mensaje, messages.ERROR)
        else:
            if liquidacion.monto >= 0:
                texto = f'Liquidación de {tienda.nombre} registrada: {formatear_monto(liquidacion.monto)} depositados.'
                if liquidacion.costo_transferencia:
                    texto += (
                        f' Comisión del banco anotada como gasto tuyo: {formatear_monto(liquidacion.costo_transferencia)}'
                        ' (no se le descontó a la tienda).'
                    )
            else:
                texto = f'Liquidación de {tienda.nombre} registrada: la tienda te debía {formatear_monto(-liquidacion.monto)}.'
            self.message_user(request, texto, messages.SUCCESS)
        return redirect(reverse('admin:pagos_liquidacion_saldos'))

    @admin.display(description='Pedidos liquidados')
    def detalle_de_pedidos(self, liquidacion):
        pedidos = liquidacion.pedidos.order_by('fecha_pago', 'id')
        if not pedidos:
            return 'Ninguno'
        filas = format_html_join('', '<li><a href="{}">{}</a> · {} · {} · {}</li>', (
            (reverse('admin:pedidos_pedido_change', args=[pedido.pk]), pedido.numero, pedido.get_metodo_pago_display(),
             'lo cobró el sitio' if pedido.cobra_el_sitio else 'lo cobró la tienda', formatear_monto(pedido.total))
            for pedido in pedidos
        ))
        return format_html('<ul style="margin: 0; padding-left: 1.2em;">{}</ul>', filas)

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
