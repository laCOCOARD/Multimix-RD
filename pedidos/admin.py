from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
import csv

from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_POST

from core.telefonos import formatear_telefono, telefono_internacional
from pagos.services import PagoError, aprobar_pago, rechazar_pago
from core.templatetags.moneda import formatear_monto
from tiendas.panel import AdminDeTienda, maneja_varias_tiendas, tiendas_del_panel
from tiendas.services import ve_todas

from . import reportes, services
from .models import DetallePedido, EventoPedido, Pedido, SolicitudDevolucion, ZonaEnvio
from .whatsapp import construir_enlace, enlace_al_cliente, enlace_aviso_de_estado

Estado = Pedido.Estado
CLIENTES_POR_PAGINA = 50

# --- Tablero de pedidos (2026-11-06, pedido del dueño: "facil hasta para un anciano") ----------------------------
# La pantalla de Pedidos muestra tarjetas grandes con un boton para lo que toca. Con otros filtros, o con
# ?lista=1, sigue la lista de siempre de Django.
TARJETAS_POR_PAGINA = 20
PARAMETROS_DEL_TABLERO = {'bandeja', 'q', 'p', 'tienda'}
# (clave de services._bandejas, nombre en el tablero). Las primeras cuatro esperan algo de la tienda.
PESTANAS = [
    ('por_confirmar', 'Revisar pagos'),
    ('por_preparar', 'Por preparar'),
    ('preparando', 'Preparándose'),
    ('por_entregar', 'Por entregar'),
    ('esperando_pago', 'Esperando pago'),
    ('entregados', 'Entregados'),
    ('cancelados', 'Cancelados'),
]
# La pregunta antes de cada boton grande del tablero: un toque de mas evita un aviso equivocado al cliente.
PREGUNTAS = {
    Estado.PREPARANDO: '¿Empezar a preparar el pedido {numero}? Al cliente le llega el aviso.',
    Estado.LISTO: '¿El pedido {numero} ya está listo? Al cliente le llega el aviso para que pase a recogerlo.',
    Estado.ENVIADO: '¿El pedido {numero} ya salió? Al cliente le llega el aviso de que va en camino.',
    Estado.EN_REPARTO: '¿El pedido {numero} salió a repartir? Al cliente le llega el aviso.',
    Estado.ENTREGADO: '¿El cliente ya recibió el pedido {numero}{cobro}? Se marca como entregado.',
}


def _pago_por_revisar(pedido):
    """El pago con comprobante que espera que alguien lo confirme o lo rechace; None si no hay."""
    from pagos.models import Pago

    return pedido.pagos.filter(estado=Pago.Estado.EN_REVISION).order_by('-id').first()


@admin.register(ZonaEnvio)
class ZonaEnvioAdmin(AdminDeTienda, admin.ModelAdmin):
    list_display = ['nombre', 'tarifa', 'dias_entrega_min', 'dias_entrega_max', 'activa', 'orden']
    list_editable = ['tarifa', 'dias_entrega_min', 'dias_entrega_max', 'activa', 'orden']
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


class EventoPedidoInline(admin.TabularInline):
    """Seguimiento del pedido: que paso, cuando y quien lo hizo. Solo lectura."""

    model = EventoPedido
    extra = 0
    can_delete = False
    fields = ['creado', 'estado', 'nota', 'usuario']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('pedidos.view_pedido')


class BandejaFilter(admin.SimpleListFilter):
    """Las pestañas de arriba de la lista ("Pago por confirmar", "Por preparar"...): cada pedido cae en una."""

    title = 'situación'
    parameter_name = 'bandeja'

    def lookups(self, request, model_admin):
        return services.opciones_de_bandeja()

    def queryset(self, request, queryset):
        filtro = services.filtro_de_bandeja(self.value()) if self.value() else None
        return queryset.filter(filtro) if filtro is not None else queryset


def _accion_de_estado(estado, descripcion):
    @admin.action(description=descripcion)
    def accion(modeladmin, request, queryset):
        modeladmin.cambiar_estado_masivo(request, queryset, estado)
    accion.__name__ = f'marcar_{estado}'
    return accion


@admin.register(Pedido)
class PedidoAdmin(AdminDeTienda, admin.ModelAdmin):
    change_form_template = 'admin/pedidos/pedido/change_form.html'
    change_list_template = 'admin/pedidos/pedido/change_list.html'
    date_hierarchy = 'creado'
    list_display = [
        'numero', 'creado', 'nombre', 'whatsapp_cliente', 'metodo_entrega', 'metodo_pago',
        'total_formateado', 'estado_con_color', 'que_sigue',
    ]
    # La zona se filtra solo entre las que aparecen en los pedidos que el usuario puede ver.
    list_filter = [
        BandejaFilter, 'estado', 'metodo_entrega', 'metodo_pago', 'transferencia_realizada', 'cobra_el_sitio',
        ('zona', admin.RelatedOnlyFieldListFilter), ('liquidacion', admin.EmptyFieldListFilter), 'creado',
    ]
    search_fields = ['numero', 'nombre', 'telefono', 'correo', 'referencia_transferencia']
    list_select_related = ['zona']
    list_per_page = 40
    inlines = [DetallePedidoInline, EventoPedidoInline]
    actions = [
        _accion_de_estado(Estado.PAGADO, 'Marcar como Pagado'),
        _accion_de_estado(Estado.PREPARANDO, 'Marcar como Preparando pedido'),
        _accion_de_estado(Estado.LISTO, 'Marcar como Listo para recoger'),
        _accion_de_estado(Estado.ENVIADO, 'Marcar como Enviado'),
        _accion_de_estado(Estado.EN_REPARTO, 'Marcar como En reparto'),
        _accion_de_estado(Estado.ENTREGADO, 'Marcar como Entregado'),
        _accion_de_estado(Estado.CANCELADO, 'Marcar como Cancelado'),
        _accion_de_estado(Estado.REEMBOLSADO, 'Marcar como Reembolsado'),
    ]
    fieldsets = [
        ('Pedido', {'fields': [
            'numero', 'tienda', 'estado_con_color', 'creado', 'fecha_pago', 'fecha_entrega', 'enlace_publico',
        ]}),
        ('Cliente', {'fields': ['nombre', 'whatsapp_cliente', 'correo', 'cuenta_del_cliente', 'avisos_whatsapp']}),
        ('Entrega', {'fields': [
            'metodo_entrega', 'zona', 'sector', 'direccion', 'referencia', 'entrega_prometida', 'transportista',
            'numero_seguimiento',
        ]}),
        ('Pago', {'fields': ['metodo_pago', 'transferencia_realizada', 'referencia_transferencia', 'pago_registrado']}),
        ('Montos', {'fields': [
            'subtotal_formateado', 'cupon_aplicado', 'itbis_formateado', 'envio_formateado', 'total_formateado',
            'liquidado',
        ]}),
        ('Notas', {'fields': ['notas_cliente', 'notas_internas']}),
    ]
    campos_editables = ['notas_internas', 'transportista', 'numero_seguimiento']

    def get_readonly_fields(self, request, obj=None):
        campos = [campo for _, opciones in self.fieldsets for campo in opciones['fields']]
        return [campo for campo in campos if campo not in self.campos_editables]

    # Lo del reparto viejo (el sitio cobraba y le liquidaba a la tienda) es solo del administrador principal.
    SOLO_DEL_ADMINISTRADOR = {'cobra_el_sitio', 'liquidado', 'tienda'}

    def get_list_filter(self, request):
        filtros = super().get_list_filter(request)
        if ve_todas(request.user):
            return filtros
        return [f for f in filtros if (f[0] if isinstance(f, tuple) else f) not in {'cobra_el_sitio', 'liquidacion'}]

    def get_list_display(self, request):
        # "Qué sigue" depende de quien mira (un pago que confirma el sitio no lo revisa la tienda).
        @admin.display(description='Qué sigue')
        def que_sigue(pedido):
            return self._que_sigue(pedido, request.user)

        columnas = [que_sigue if c == 'que_sigue' else c for c in super().get_list_display(request)]
        if ve_todas(request.user):
            return columnas
        # El vendedor: lo que necesita para atender el pedido, sin columnas de mas.
        return [c for c in columnas if c != 'metodo_pago']

    def changelist_view(self, request, extra_context=None):
        if request.method == 'GET' and 'lista' not in request.GET and set(request.GET) <= PARAMETROS_DEL_TABLERO:
            return self.tablero_vista(request)
        if 'lista' in request.GET:
            # La lista de Django no conoce el parametro: se quita antes de que lo tome por un filtro.
            request.GET = request.GET.copy()
            del request.GET['lista']
        contexto = {
            'bandejas': services.bandejas_de_pedidos(self.get_queryset(request)),
            'bandeja_actual': request.GET.get('bandeja', ''),
            **(extra_context or {}),
        }
        return super().changelist_view(request, contexto)

    def get_fieldsets(self, request, obj=None):
        if ve_todas(request.user):
            return self.fieldsets
        return [(titulo, {**opciones, 'fields': [c for c in opciones['fields'] if c not in self.SOLO_DEL_ADMINISTRADOR]})
                for titulo, opciones in self.fieldsets]

    def has_add_permission(self, request):
        return False

    # Eliminar tambien pasa por la capa de servicios, para que el stock y el cupon queden bien.

    def has_delete_permission(self, request, obj=None):
        # Lo cobrado, avisado o liquidado solo lo borra el administrador principal (services.puede_eliminar).
        permitido = super().has_delete_permission(request, obj)
        return permitido and (obj is None or services.puede_eliminar(obj, request.user))

    def delete_model(self, request, obj):
        services.eliminar_pedido(obj, usuario=request.user)

    def delete_queryset(self, request, queryset):
        for pedido in queryset.order_by('creado'):
            try:
                services.eliminar_pedido(pedido, usuario=request.user)
            except services.PedidoError as error:
                self.message_user(request, f'No se eliminó: {error.mensaje}', messages.ERROR)

    def get_urls(self):
        propias = [
            path(
                '<path:object_id>/estado/', self.admin_site.admin_view(require_POST(self.cambiar_estado_vista)),
                name='pedidos_pedido_estado',
            ),
            path(
                '<path:object_id>/pago/', self.admin_site.admin_view(require_POST(self.revisar_pago_vista)),
                name='pedidos_pedido_pago',
            ),
            path('clientes/', self.admin_site.admin_view(self.clientes_vista), name='pedidos_pedido_clientes'),
            path('reporte/', self.admin_site.admin_view(self.reporte_vista), name='pedidos_pedido_reporte'),
        ]
        return propias + super().get_urls()

    # --- Tablero: tarjetas grandes con el boton de lo que sigue -----------------------

    def tablero_vista(self, request):
        from pagos.models import Pago

        if not self.has_view_permission(request):
            raise PermissionDenied
        pedidos = self.get_queryset(request)
        tiendas = tiendas_del_panel(request) if maneja_varias_tiendas(request) else []
        elegida = next((t for t in tiendas if str(t.pk) == request.GET.get('tienda', '')), None)
        if elegida is not None:
            pedidos = pedidos.filter(tienda=elegida)
        busqueda = request.GET.get('q', '').strip()[:60]
        if busqueda:
            pedidos = pedidos.filter(
                Q(numero__icontains=busqueda) | Q(nombre__icontains=busqueda) | Q(telefono__icontains=busqueda)
            )
        cuentas = {bandeja['clave']: bandeja['cantidad'] for bandeja in services.bandejas_de_pedidos(pedidos)}
        clave = request.GET.get('bandeja', '')
        nombres = dict(PESTANAS)
        if clave == 'todos':
            lista, titulo, orden = pedidos, 'Todos los pedidos', '-creado'
        elif clave in nombres:
            lista, titulo = pedidos.filter(services.filtro_de_bandeja(clave)), nombres[clave]
            # Lo que espera a la tienda, del mas viejo al mas nuevo; lo terminado, lo ultimo primero.
            orden = 'creado' if clave in services.BANDEJAS_PARA_ATENDER else '-creado'
        else:
            clave, titulo, orden = '', 'Para atender', 'creado'
            lista = pedidos.filter(services.filtro_para_atender())
        lista = lista.select_related('zona', 'tienda').prefetch_related(
            'detalles',
            Prefetch('pagos', queryset=Pago.objects.filter(estado=Pago.Estado.EN_REVISION).order_by('-id'),
                     to_attr='pagos_en_revision'),
        ).order_by(orden, 'pk')
        pagina = Paginator(lista, TARJETAS_POR_PAGINA).get_page(request.GET.get('p'))

        def enlace(**cambios):
            parametros = {'bandeja': clave, 'q': busqueda, 'tienda': elegida.pk if elegida else '', **cambios}
            texto = urlencode({k: v for k, v in parametros.items() if v})
            return f'?{texto}' if texto else '?'

        pestanas = [
            {'clave': c, 'nombre': nombre, 'cantidad': cuentas[c], 'url': enlace(bandeja=c, p=''),
             'activa': c == clave, 'atender': c in services.BANDEJAS_PARA_ATENDER}
            for c, nombre in PESTANAS
        ]
        return render(request, 'admin/pedidos/pedido/tablero.html', {
            **self.admin_site.each_context(request),
            'title': 'Pedidos',
            'opts': self.model._meta,
            'pestanas': pestanas,
            'para_atender': sum(cuentas[c] for c in services.BANDEJAS_PARA_ATENDER),
            'url_atender': enlace(bandeja='', p=''),
            'url_todos': enlace(bandeja='todos', p=''),
            'bandeja_actual': clave,
            'titulo_bandeja': titulo,
            'tarjetas': [self._tarjeta(request, pedido) for pedido in pagina],
            'pagina': pagina,
            'url_anterior': enlace(p=pagina.previous_page_number()) if pagina.has_previous() else '',
            'url_siguiente': enlace(p=pagina.next_page_number()) if pagina.has_next() else '',
            'busqueda': busqueda,
            'tiendas': tiendas,
            'tienda_elegida': elegida,
            'varias_tiendas': bool(tiendas),
            'volver': request.get_full_path(),
        })

    def _tarjeta(self, request, pedido):
        """Lo que muestra una tarjeta del tablero y su boton grande. Sin consultas: todo viene precargado."""
        paso = services.siguiente_paso(pedido, request.user)
        pago = pedido.pagos_en_revision[0] if paso.revisar_pago and pedido.pagos_en_revision else None
        accion = None
        if self.has_change_permission(request, pedido):
            if pago is not None and not paso.confirma_el_sitio and request.user.has_perm('pagos.change_pago'):
                accion = {
                    'tipo': 'pago', 'texto': 'El dinero llegó: confirmar pago',
                    'confirmar': f'¿Ya viste el dinero del pedido {pedido.numero} en tu banco? Se marca como pagado '
                                 'y al cliente le llega el aviso.',
                }
            elif paso.principal:
                cobro = '' if pedido.fecha_pago else ' y pagó'
                accion = {
                    'tipo': 'estado', 'valor': paso.principal,
                    'texto': services.VERBOS[paso.principal],
                    'confirmar': PREGUNTAS.get(paso.principal, '¿Cambiar el pedido {numero}?').format(
                        numero=pedido.numero, cobro=cobro),
                }
        productos = list(pedido.detalles.all())
        return {
            'pedido': pedido,
            'paso': paso,
            'accion': accion,
            'comprobante_url': (
                reverse('admin:pagos_pago_comprobante', args=[pago.pk])
                if pago is not None and pago.comprobante and request.user.has_perm('pagos.view_pago') else ''
            ),
            'productos': productos[:4],
            'mas_productos': max(0, len(productos) - 4),
            'whatsapp': enlace_al_cliente(pedido),
            'llamar': f'tel:+{telefono_internacional(pedido.telefono)}',
            'telefono': formatear_telefono(pedido.telefono),
            'urgente': accion is not None and (accion['tipo'] == 'pago' or paso.principal == Estado.PREPARANDO),
        }

    def _volver(self, request, pedido):
        """Despues de un boton: al tablero si se toco ahi (misma pestaña y pagina), si no al pedido."""
        volver = request.POST.get('volver', '')
        if volver.startswith(reverse('admin:pedidos_pedido_changelist')) and url_has_allowed_host_and_scheme(
                volver, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(volver)
        return redirect(reverse('admin:pedidos_pedido_change', args=[pedido.pk]))

    # --- Clientes: salen de los pedidos que el usuario puede ver --------------------

    def clientes_vista(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        pedidos = self.get_queryset(request)
        busqueda = request.GET.get('q', '')
        pagina = Paginator(services.clientes(pedidos, busqueda), CLIENTES_POR_PAGINA).get_page(request.GET.get('p'))
        filas = services.completar_clientes(pagina.object_list, pedidos)
        for fila in filas:
            saludo = f'Hola {fila.get("nombre", "")}, te escribimos de {fila.get("tienda", "la tienda")}.'
            fila['enlace_whatsapp'] = construir_enlace(telefono_internacional(fila['telefono']), saludo)
            fila['telefono_formateado'] = formatear_telefono(fila['telefono'])
        return render(request, 'admin/pedidos/pedido/clientes.html', {
            **self.admin_site.each_context(request),
            'title': 'Clientes',
            'filas': filas,
            'pagina': pagina,
            'busqueda': busqueda,
            'varias_tiendas': maneja_varias_tiendas(request),
            'opts': self.model._meta,
        })

    # --- Reporte de ventas: solo con los pedidos que el usuario puede ver -----------

    def reporte_vista(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        desde, hasta = reportes.rango(request.GET.get('desde'), request.GET.get('hasta'))
        # Quien maneja varias tiendas puede ver el reporte de una sola (entre las suyas).
        pedidos = self.get_queryset(request)
        tiendas = tiendas_del_panel(request) if maneja_varias_tiendas(request) else []
        elegida = next((t for t in tiendas if str(t.pk) == request.GET.get('tienda', '')), None)
        if elegida is not None:
            pedidos = pedidos.filter(tienda=elegida)
        reporte = reportes.reporte_de_ventas(pedidos, desde, hasta)
        if request.GET.get('formato') == 'csv':
            respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
            respuesta['Content-Disposition'] = f'attachment; filename="ventas_{desde}_{hasta}.csv"'
            respuesta.write('\ufeff')  # para que Excel lea bien las tildes
            hoja = csv.writer(respuesta)
            hoja.writerow(['Dia', 'Pedidos', 'Cobrado (RD$)'])
            for fila in reporte['por_dia']:
                hoja.writerow([fila['dia'].isoformat(), fila['pedidos'], f"{fila['cobrado']:.2f}"])
            hoja.writerow(['Total', reporte['pedidos'], f"{reporte['cobrado']:.2f}"])
            return respuesta
        return render(request, 'admin/pedidos/pedido/reporte.html', {
            **self.admin_site.each_context(request),
            'title': 'Reporte de ventas',
            'reporte': reporte,
            'tiendas': tiendas,
            'tienda_elegida': elegida,
            'varias_tiendas': maneja_varias_tiendas(request),
            'opts': self.model._meta,
        })

    # --- Cambios de estado (siempre por la capa de servicios) -----------------------

    def cambiar_estado_masivo(self, request, queryset, estado):
        if not self.has_change_permission(request):
            raise PermissionDenied
        hechos = 0
        for pedido in queryset.order_by('creado'):
            try:
                services.cambiar_estado(pedido, estado, usuario=request.user)
                hechos += 1
            except services.PedidoError as error:
                self.message_user(request, error.mensaje, messages.ERROR)
        if hechos:
            self.message_user(
                request, f'{hechos} pedido(s) pasaron a "{Estado(estado).label}".', messages.SUCCESS,
            )

    def cambiar_estado_vista(self, request, object_id):
        if not self.has_change_permission(request):
            raise PermissionDenied
        # get_object solo encuentra pedidos de las tiendas del usuario.
        pedido = self.get_object(request, unquote(object_id))
        if pedido is None:
            raise Http404
        try:
            pedido = services.avanzar_pedido(
                pedido, request.POST.get('estado', ''), usuario=request.user, nota=request.POST.get('nota', ''),
                transportista=request.POST.get('transportista', ''),
                numero_seguimiento=request.POST.get('numero_seguimiento', ''),
            )
        except services.PedidoError as error:
            self.message_user(request, error.mensaje, messages.ERROR)
        else:
            self.message_user(
                request, f'El pedido {pedido.numero} pasó a "{pedido.get_estado_display()}". Al cliente le llega el aviso.',
                messages.SUCCESS,
            )
        return self._volver(request, pedido)

    def revisar_pago_vista(self, request, object_id):
        """Confirmar o rechazar la transferencia desde el propio pedido, viendo el comprobante."""
        if not (self.has_change_permission(request) and request.user.has_perm('pagos.change_pago')):
            raise PermissionDenied
        pedido = self.get_object(request, unquote(object_id))
        if pedido is None:
            raise Http404
        pago = _pago_por_revisar(pedido)
        try:
            if pago is None:
                raise PagoError('Este pedido no tiene un pago esperando revisión.')
            if request.POST.get('accion') == 'aprobar':
                aprobar_pago(pago, request.user)
                self.message_user(
                    request, f'Pago confirmado: el pedido {pedido.numero} quedó Pagado. Al cliente le llega el aviso.',
                    messages.SUCCESS,
                )
            elif request.POST.get('accion') == 'rechazar':
                rechazar_pago(pago, request.user, nota=request.POST.get('motivo', '').strip())
                self.message_user(
                    request, 'Comprobante rechazado: al cliente le llega un correo para que envíe otro.',
                    messages.SUCCESS,
                )
            else:
                raise PagoError('Elige confirmar o rechazar el pago.')
        except (PagoError, services.PedidoError) as error:
            self.message_user(request, error.mensaje, messages.ERROR)
        return self._volver(request, pedido)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        pedido = self.get_object(request, unquote(object_id))
        contexto = dict(extra_context or {})
        if pedido is not None and self.has_change_permission(request, pedido):
            contexto['transiciones'] = [
                (estado.value, estado.label) for estado in services.transiciones_permitidas(pedido, request.user)
            ]
            contexto['confirma_el_sitio'] = pedido.cobra_el_sitio and not ve_todas(request.user)
            contexto['paso'] = self._paso_con_botones(request, pedido)
        if pedido is not None:
            contexto['aviso_whatsapp'] = enlace_aviso_de_estado(
                pedido, request.build_absolute_uri(pedido.get_absolute_url()),
            )
            contexto['enlace_whatsapp_cliente'] = enlace_al_cliente(pedido)
            contexto['telefono_cliente'] = formatear_telefono(pedido.telefono)
            contexto['llamar_cliente'] = f'tel:+{telefono_internacional(pedido.telefono)}'
            contexto['productos_del_pedido'] = list(pedido.detalles.all())
        return super().change_view(request, object_id, form_url, contexto)

    def _paso_con_botones(self, request, pedido):
        """Lo que sigue en el pedido, con sus botones y, si hay, el comprobante por revisar."""
        paso = services.siguiente_paso(pedido, request.user)

        def boton(estado):
            confirmar = ''
            if estado == Estado.CANCELADO:
                confirmar = f'¿Cancelar el pedido {pedido.numero}? Al cliente le llega el aviso y no se puede deshacer.'
            elif estado == Estado.REEMBOLSADO:
                confirmar = f'¿Ya le devolviste el dinero del pedido {pedido.numero}? Esto no se puede deshacer.'
            return {'valor': estado, 'texto': services.VERBOS[estado], 'confirmar': confirmar}

        pago = _pago_por_revisar(pedido) if paso.revisar_pago else None
        ver_comprobante = (
            pago is not None and pago.comprobante and request.user.has_perm('pagos.view_pago')
        )
        return {
            'titulo': paso.titulo,
            'texto': paso.texto,
            'principal': boton(paso.principal) if paso.principal else None,
            'otros': [boton(estado) for estado in paso.otros],
            'pide_envio': Estado.ENVIADO in [paso.principal, *paso.otros],
            'pago': pago,
            'comprobante_url': reverse('admin:pagos_pago_comprobante', args=[pago.pk]) if ver_comprobante else '',
            'puede_resolver_pago': (
                pago is not None and not paso.confirma_el_sitio and request.user.has_perm('pagos.change_pago')
            ),
        }

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

    @staticmethod
    def _que_sigue(pedido, usuario):
        paso = services.siguiente_paso(pedido, usuario)
        if not paso.corto:
            return ''
        # Resaltado lo que espera a la tienda: un pago por revisar o un pedido por preparar.
        urgente = (paso.revisar_pago and not paso.confirma_el_sitio) or paso.principal == Estado.PREPARANDO
        return format_html('<span class="pv-que-sigue{}">{}</span>', ' pv-urgente' if urgente else '', paso.corto)

    @admin.display(description='Qué sigue')
    def que_sigue(self, pedido):
        # get_list_display la cambia por una que sabe quien mira.
        return self._que_sigue(pedido, None)

    @admin.display(description='Total', ordering='total')
    def total_formateado(self, pedido):
        return formatear_monto(pedido.total)

    @admin.display(description='Subtotal')
    def subtotal_formateado(self, pedido):
        return formatear_monto(pedido.subtotal)

    @admin.display(description='ITBIS')
    def itbis_formateado(self, pedido):
        if not pedido.impuesto:
            return 'No aplica'
        return f'{formatear_monto(pedido.impuesto)} · {pedido.etiqueta_impuesto}'

    @admin.display(description='Costo de envío')
    def envio_formateado(self, pedido):
        return formatear_monto(pedido.costo_envio)

    @admin.display(description='Cupón y descuento')
    def cupon_aplicado(self, pedido):
        if not pedido.codigo_cupon:
            return 'Sin cupón'
        return f'{pedido.codigo_cupon}: -{formatear_monto(pedido.descuento)}'

    @admin.display(description='Reparto a la tienda')
    def liquidado(self, pedido):
        if pedido.liquidacion_id is None:
            return 'Sin liquidar'
        return f'Liquidado el {pedido.liquidacion.creada:%d/%m/%Y}'

    @admin.display(description='Entrega prometida al cliente')
    def entrega_prometida(self, pedido):
        if pedido.entrega_desde is None:
            return '—'
        if pedido.entrega_desde == pedido.entrega_hasta:
            return f'{pedido.entrega_desde:%d/%m/%Y}'
        return f'{pedido.entrega_desde:%d/%m/%Y} al {pedido.entrega_hasta:%d/%m/%Y}'

    @admin.display(description='Cuenta')
    def cuenta_del_cliente(self, pedido):
        return 'Compró con su cuenta' if pedido.cliente_id else 'Compró como invitado'

    @admin.display(description='Pago y comprobante')
    def pago_registrado(self, pedido):
        pago = pedido.pagos.order_by('-id').first()
        quien = ' · lo recibe y confirma el sitio' if pedido.cobra_el_sitio else ''
        if pago is None:
            return f'Sin pago registrado{quien}'
        return format_html(
            '<a href="{}">{} · {}{}</a>{}', reverse('admin:pagos_pago_change', args=[pago.pk]), pago.referencia,
            pago.get_estado_display(), ' · con comprobante' if pago.comprobante else '', quien,
        )

    @admin.display(description='Página del cliente')
    def enlace_publico(self, pedido):
        return format_html('<a href="{}" target="_blank" rel="noopener">Ver confirmación ↗</a>', pedido.get_absolute_url())


@admin.register(SolicitudDevolucion)
class SolicitudDevolucionAdmin(AdminDeTienda, admin.ModelAdmin):
    """Las devoluciones que piden los clientes. La tienda escribe su respuesta y acepta o rechaza."""

    list_display = ['pedido_enlazado', 'creado', 'motivo_corto', 'estado', 'resuelto_en']
    list_filter = ['estado', 'creado']
    search_fields = ['pedido__numero', 'pedido__nombre', 'motivo']
    list_select_related = ['pedido']
    actions = ['aceptar', 'rechazar']
    fields = ['pedido_enlazado', 'tienda', 'creado', 'motivo', 'estado', 'respuesta', 'resuelto_en', 'resuelto_por']
    readonly_fields = ['pedido_enlazado', 'tienda', 'creado', 'motivo', 'estado', 'resuelto_en', 'resuelto_por']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Solo se borran junto con su pedido.
        return request.user.has_perm('pedidos.delete_pedido')

    def get_actions(self, request):
        acciones = super().get_actions(request)
        acciones.pop('delete_selected', None)
        return acciones

    def delete_view(self, request, object_id, extra_context=None):
        raise PermissionDenied

    def change_view(self, request, object_id, form_url='', extra_context=None):
        return super().change_view(request, object_id, form_url, {'show_delete': False, **(extra_context or {})})

    def _responder(self, request, queryset, aceptar):
        if not self.has_change_permission(request):
            raise PermissionDenied
        total = 0
        for solicitud in queryset:
            try:
                services.responder_devolucion(solicitud, aceptar, request.user)
                total += 1
            except services.PedidoError as error:
                self.message_user(request, error.mensaje, messages.ERROR)
        if total:
            hecho = 'aceptadas' if aceptar else 'rechazadas'
            self.message_user(request, f'{total} solicitud(es) {hecho}. El cliente recibe un correo.', messages.SUCCESS)

    @admin.action(description='Aceptar la devolución')
    def aceptar(self, request, queryset):
        self._responder(request, queryset, True)

    @admin.action(description='Rechazar la devolución')
    def rechazar(self, request, queryset):
        self._responder(request, queryset, False)

    @admin.display(description='Pedido', ordering='pedido__numero')
    def pedido_enlazado(self, solicitud):
        return format_html(
            '<a href="{}">{}</a> · {}', reverse('admin:pedidos_pedido_change', args=[solicitud.pedido_id]),
            solicitud.pedido.numero, solicitud.pedido.nombre,
        )

    @admin.display(description='Motivo')
    def motivo_corto(self, solicitud):
        return solicitud.motivo[:80]
