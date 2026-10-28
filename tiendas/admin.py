from django.contrib import admin, messages
from django.db.models import Count, Q
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from core.admin_avisos import AvisaImagenesSinGuardar
from core.templatetags.moneda import formatear_monto

from .models import Banner, CuentaBancaria, SolicitudTienda, Tienda
from .panel import AdminDeTienda, tiendas_del_panel
from .services import avisar_resultado_de_solicitud, dar_acceso_al_panel, revisar_solicitud, ve_todas


@admin.register(Tienda)
class TiendaAdmin(AvisaImagenesSinGuardar, admin.ModelAdmin):
    """El administrador principal crea, activa, asigna y pone el plan de cada tienda; cada vendedor edita los datos de
    la suya y ve su plan."""

    list_display = ['nombre', 'enlace_publico', 'prefijo', 'productos_a_la_venta', 'vendedores', 'activa', 'orden']
    list_filter = ['activa', 'cerrada_por_falta_de_pago', 'plan']
    search_fields = ['nombre', 'slug', 'prefijo']
    filter_horizontal = ['usuarios']
    actions = ['habilitar', 'aprobar_cambio_de_plan', 'rechazar_cambio_de_plan']

    # El primer bloque completo es solo para el administrador principal; el vendedor cambia el nombre.
    fieldsets = [
        ('Tienda', {'fields': ['nombre', 'slug', 'prefijo', 'activa', 'orden', 'usuarios']}),
        ('Marca', {'fields': ['logo', 'banner_titulo', 'banner_subtitulo', 'banner_texto_boton', 'banner_imagen']}),
        ('Contacto', {'fields': ['whatsapp', 'telefono', 'correo', 'horario', 'direccion_tienda']}),
        ('Redes', {'fields': ['facebook', 'instagram', 'tiktok']}),
        ('Pedidos y entregas', {'fields': [
            'permitir_contra_entrega', 'envio_gratis_desde', 'dias_para_recoger', 'dias_bajo_pedido',
        ]}),
        ('Plan y cobros (solo lo ve el administrador principal)', {
            'fields': ['plan', 'cambio_pedido', 'estado_de_cobro', 'comision_porcentaje', 'itbis_porcentaje'],
        }),
    ]

    def get_queryset(self, request):
        from django.utils import timezone

        vencidos = Q(cargos__estado='pendiente', cargos__vence__lte=timezone.localdate())
        consulta = super().get_queryset(request).annotate(
            total_productos=Count('productos', filter=Q(productos__activo=True), distinct=True),
            cargos_vencidos=Count('cargos', filter=vencidos, distinct=True),
        ).select_related('plan').prefetch_related('usuarios')
        if ve_todas(request.user):
            return consulta
        return consulta.filter(pk__in=[tienda.pk for tienda in tiendas_del_panel(request)])

    def get_list_display(self, request):
        columnas = list(super().get_list_display(request))
        if ve_todas(request.user):
            # El plan y como va con sus pagos, a la vista; se cambian entrando a la tienda.
            columnas[4:4] = ['plan', 'pide_plan', 'cobro']
        return columnas

    def get_actions(self, request):
        acciones = super().get_actions(request)
        if not ve_todas(request.user):
            for accion in ('habilitar', 'aprobar_cambio_de_plan', 'rechazar_cambio_de_plan'):
                acciones.pop(accion, None)
        return acciones

    # --- Cambio de plan (pedido del dueño el 2026-10-28) ---------------------------------------------------------

    def get_urls(self):
        propias = [path('<path:object_id>/plan/', self.admin_site.admin_view(self.cambiar_plan_view),
                        name='tiendas_tienda_plan')]
        return propias + super().get_urls()

    def cambiar_plan_view(self, request, object_id):
        """La tienda elige otro plan; lo aprueba el administrador principal."""
        from planes import services as planes

        tienda = get_object_or_404(self.get_queryset(request), pk=unquote(object_id))
        if not self.has_change_permission(request, tienda):
            raise PermissionDenied
        if request.method == 'POST':
            try:
                if 'cancelar' in request.POST:
                    planes.cancelar_pedido_de_plan(tienda)
                    self.message_user(request, 'Retiraste tu pedido de cambio de plan.', messages.SUCCESS)
                else:
                    plan = get_object_or_404(planes.planes_para_elegir(), pk=request.POST.get('plan') or 0)
                    planes.pedir_cambio_de_plan(tienda, plan, request.user)
                    tienda.refresh_from_db()
                    deposito = planes.deposito_del_cambio(tienda)
                    if deposito:
                        texto = (f'Pediste el plan {plan.nombre}. Para que el cambio se haga, deposita '
                                 f'{formatear_monto(deposito.monto)} y sube el comprobante: cuando lo confirmemos, '
                                 'tu plan cambia solo.')
                    else:
                        texto = f'Pediste el plan {plan.nombre}. Te avisamos por correo cuando lo aprobemos.'
                    self.message_user(request, texto, messages.SUCCESS)
            except planes.CambioDePlanError as error:
                self.message_user(request, str(error), messages.ERROR)
            return redirect(reverse('admin:tiendas_tienda_plan', args=[tienda.pk]))
        contexto = {
            **self.admin_site.each_context(request),
            'title': 'Cambiar de plan', 'opts': self.model._meta, 'tienda': tienda,
            # Cada plan con lo que habria que depositar hoy para pasar a el.
            'planes': [(plan, planes.diferencia_del_cambio(tienda, plan)) for plan in planes.planes_para_elegir()],
            'deposito': planes.deposito_del_cambio(tienda),
            'tiene_deudas': planes.tiene_pagos_vencidos(tienda),
        }
        return TemplateResponse(request, 'admin/tiendas/tienda/cambiar_plan.html', contexto)

    @admin.display(description='Pide cambiar a')
    def pide_plan(self, tienda):
        if not tienda.plan_pedido_id:
            return '—'
        from planes.services import deposito_del_cambio

        deposito = deposito_del_cambio(tienda)
        if deposito is None:
            return tienda.plan_pedido.nombre
        return f'{tienda.plan_pedido.nombre} (depósito: {deposito.get_estado_display().lower()})'

    @admin.display(description='Cambio de plan pedido')
    def cambio_pedido(self, tienda):
        if not tienda.plan_pedido_id:
            return 'Ninguno.'
        from planes.services import deposito_del_cambio

        texto = f'Pidió el plan {tienda.plan_pedido.nombre} el {timezone.localtime(tienda.plan_pedido_el):%d/%m/%Y}. '
        deposito = deposito_del_cambio(tienda)
        if deposito is None:
            return texto + 'No lleva depósito: apruébalo o recházalo desde la lista de tiendas (acciones).'
        return format_html(
            '{}Debe depositar {} antes: <a href="{}">{}</a>. Al aprobar ese pago, el plan cambia solo.', texto,
            formatear_monto(deposito.monto), reverse('admin:planes_cargo_change', args=[deposito.pk]),
            deposito.get_estado_display())

    @admin.action(description='Aprobar el cambio de plan pedido')
    def aprobar_cambio_de_plan(self, request, queryset):
        self._resolver_cambios(request, queryset, aprobar=True)

    @admin.action(description='Rechazar el cambio de plan pedido')
    def rechazar_cambio_de_plan(self, request, queryset):
        self._resolver_cambios(request, queryset, aprobar=False)

    def _resolver_cambios(self, request, queryset, aprobar):
        from planes import services as planes

        if not ve_todas(request.user):
            return
        hechas = 0
        for tienda in queryset.filter(plan_pedido__isnull=False):
            try:
                (planes.aprobar_cambio_de_plan if aprobar else planes.rechazar_cambio_de_plan)(tienda, request.user)
            except planes.CambioDePlanError as error:
                self.message_user(request, str(error), messages.ERROR)
                continue
            hechas += 1
        if hechas:
            resultado = 'aprobado(s)' if aprobar else 'rechazado(s)'
            self.message_user(request, f'{hechas} cambio(s) de plan {resultado}.', messages.SUCCESS)
        elif not queryset.filter(plan_pedido__isnull=False).exists():
            self.message_user(request, 'Ninguna de las tiendas elegidas pidió cambiar de plan.', messages.WARNING)

    @admin.display(description='Pagos al sitio')
    def cobro(self, tienda):
        if tienda.cerrada_por_falta_de_pago and not tienda.activa:
            return format_html('<span class="panel-estado panel-cargo-pendiente">Cerrada por falta de pago</span>')
        if getattr(tienda, 'cargos_vencidos', 0):
            return format_html('<span class="panel-estado panel-cargo-pendiente">Pago vencido</span>')
        if not tienda.plan_id:
            return 'Sin plan'
        return 'Al día'

    def get_fieldsets(self, request, obj=None):
        if ve_todas(request.user):
            return self.fieldsets
        # El vendedor no cambia su plan, la comision ni el ITBIS: el ultimo bloque es del administrador. Ve su plan.
        (titulo, _), *resto = self.fieldsets[:-1]
        return [(titulo, {'fields': ['nombre', 'enlace_publico']}), *resto, ('Tu plan', {'fields': ['tu_plan']})]

    def get_readonly_fields(self, request, obj=None):
        if not ve_todas(request.user):
            return ['enlace_publico', 'tu_plan']
        # El prefijo ya esta en los numeros de pedido emitidos: no cambia despues de crear la tienda.
        return ['prefijo', 'estado_de_cobro', 'cambio_pedido'] if obj else ['estado_de_cobro', 'cambio_pedido']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'plan':
            from planes.models import Plan

            kwargs['queryset'] = Plan.objects.filter(activo=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Volver a encender una tienda cerrada por falta de pago es habilitarla: deja de contar como cerrada.
        if change and ve_todas(request.user) and obj.activa and obj.cerrada_por_falta_de_pago:
            from planes.services import habilitar_tienda

            habilitar_tienda(obj, request.user)

    @admin.action(description='Habilitar (abrir) las tiendas elegidas')
    def habilitar(self, request, queryset):
        from planes.services import habilitar_tienda

        if not ve_todas(request.user):
            return
        total = 0
        for tienda in queryset:
            habilitar_tienda(tienda, request.user)
            total += 1
        self.message_user(request, f'{total} tienda(s) habilitada(s).', messages.SUCCESS)

    @admin.display(description='Estado de sus pagos')
    def estado_de_cobro(self, tienda):
        if not tienda.pk:
            return '—'
        from planes.services import estado_de_cuenta

        estado = estado_de_cuenta(tienda)
        partes = []
        if tienda.cerrada_por_falta_de_pago and not tienda.activa:
            partes.append(f'Cerrada por falta de pago desde el {tienda.cerrada_el:%d/%m/%Y}. Enciéndela (casilla '
                          '"Activa") o usa la acción "Habilitar" para abrirla.')
        if estado.pendientes:
            partes.append(f'Debe {formatear_monto(estado.total_pendiente)} en {len(estado.pendientes)} cargo(s)'
                          + (f'; {estado.en_revision} con comprobante por revisar' if estado.en_revision else '') + '.')
        else:
            partes.append('No tiene cargos pendientes.')
        if estado.uso.incluidos is not None:
            partes.append(f'Este mes: {estado.uso.pedidos} de {estado.uso.incluidos} pedidos incluidos.')
        enlace = reverse('admin:planes_cargo_changelist') + f'?tienda__id__exact={tienda.pk}'
        return format_html('{} <a href="{}">Ver sus cargos</a>', ' '.join(partes), enlace)

    @admin.display(description='Tu plan')
    def tu_plan(self, tienda):
        plan = tienda.plan
        cambiar = reverse('admin:tiendas_tienda_plan', args=[tienda.pk]) if tienda.pk else ''
        pedido = (format_html('<p><strong>Pediste el plan {}</strong>: <a href="{}">ver cómo va</a>.</p>',
                              tienda.plan_pedido.nombre, cambiar) if tienda.plan_pedido_id else '')
        if plan is None:
            return format_html(
                'Tu tienda todavía no tiene un plan: no pagas mensualidad ni puedes poner anuncios en la portada.{} '
                '<a class="button" href="{}">Elegir un plan</a>', pedido, cambiar)
        detalles = [
            f'Mensualidad: {formatear_monto(plan.mensualidad)}, vence el día 1 de cada mes.',
            (f'Incluye {plan.pedidos_incluidos} pedidos cobrados al mes; por cada pedido de más se cobra el '
             f'{plan.porcentaje_excedente.normalize():f} % de lo vendido en él (productos, sin el envío).')
            if plan.pedidos_incluidos is not None else 'Pedidos al mes sin límite.',
            f'Anuncios con foto en la portada: {plan.anuncios_portada} (7 días cada uno). Videos: '
            f'{plan.videos_portada}. Productos anunciados: {plan.productos_patrocinados}.',
        ]
        return format_html(
            '<strong>Plan {}</strong><ul>{}</ul>{}<a class="button" href="{}">Cambiar de plan</a> '
            '<a href="{}">Ver tus pagos al sitio</a>',
            plan.nombre, format_html_join('', '<li>{}</li>', ((detalle,) for detalle in detalles)), pedido, cambiar,
            reverse('admin:planes_cargo_changelist'),
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if 'usuarios' in form.cleaned_data:
            dar_acceso_al_panel(form.cleaned_data['usuarios'])

    def changelist_view(self, request, extra_context=None):
        """Quien administra una sola tienda entra directo a editarla."""
        if not ve_todas(request.user):
            tiendas = tiendas_del_panel(request)
            if len(tiendas) == 1:
                return redirect(reverse('admin:tiendas_tienda_change', args=[tiendas[0].pk]))
        return super().changelist_view(request, extra_context)

    @admin.display(description='Enlace público')
    def enlace_publico(self, tienda):
        if not tienda.pk:
            return '—'
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener">{0} ↗</a>', tienda.get_absolute_url(),
        )

    @admin.display(description='Productos activos', ordering='total_productos')
    def productos_a_la_venta(self, tienda):
        return tienda.total_productos

    @admin.display(description='Vendedores')
    def vendedores(self, tienda):
        return ', '.join(usuario.get_username() for usuario in tienda.usuarios.all()) or '—'


@admin.register(CuentaBancaria)
class CuentaBancariaAdmin(AdminDeTienda, admin.ModelAdmin):
    """Las cuentas de cada tienda: a ellas le transfieren sus clientes y ella confirma los pagos. Sin una cuenta
    activa, la tienda no ofrece pago por transferencia."""

    list_display = ['banco', 'tipo_cuenta', 'numero', 'titular', 'cedula_rnc', 'activa', 'orden']
    list_editable = ['activa', 'orden']
    list_filter = ['activa', 'tipo_cuenta']
    search_fields = ['banco', 'numero', 'titular']
    fields = ['tienda', 'banco', 'tipo_cuenta', 'numero', 'titular', 'cedula_rnc', 'activa', 'orden']


@admin.register(Banner)
class BannerAdmin(AvisaImagenesSinGuardar, AdminDeTienda, admin.ModelAdmin):
    """Promociones que rotan en el inicio de la tienda."""

    list_display = ['titulo', 'activo', 'orden', 'vigente_desde', 'vigente_hasta']
    list_editable = ['activo', 'orden']
    list_filter = ['activo']
    search_fields = ['titulo', 'subtitulo']
    fieldsets = [
        (None, {'fields': ['tienda', 'titulo', 'subtitulo', 'imagen', 'texto_boton', 'enlace']}),
        ('Cuándo se muestra', {'fields': ['activo', 'orden', 'vigente_desde', 'vigente_hasta']}),
    ]


@admin.register(SolicitudTienda)
class SolicitudTiendaAdmin(admin.ModelAdmin):
    """Solicitudes de quienes quieren vender (formulario de /vender/solicitar/). Solo el administrador principal las ve:
    traen datos personales. Aprobar no crea nada solo: desde aqui se crea la tienda con los datos de la solicitud y se
    le da acceso a sus vendedores en la pantalla de la tienda, como siempre."""

    list_display = ['nombre_comercial', 'nombre_responsable', 'rubro', 'estado_legible', 'creada']
    list_filter = ['estado', 'rubro']
    search_fields = ['nombre_comercial', 'nombre_responsable', 'correo', 'telefono']
    date_hierarchy = 'creada'
    actions = ['marcar_en_revision', 'rechazar']
    readonly_fields = [
        'nombre_responsable', 'nombre_comercial', 'contacto', 'rubro', 'descripcion', 'redes', 'creada',
        'revisada_por', 'revisada_el', 'crear_tienda',
    ]
    fieldsets = [
        ('Quién la envía', {'fields': ['nombre_responsable', 'nombre_comercial', 'contacto', 'rubro', 'redes', 'creada']}),
        ('Qué vende', {'fields': ['descripcion']}),
        ('Revisión', {'fields': ['estado', 'notas', 'tienda', 'crear_tienda', 'revisada_por', 'revisada_el']}),
    ]

    # Solo el administrador principal: los vendedores no ven ni el menu.
    def has_module_permission(self, request):
        return ve_todas(request.user)

    def has_view_permission(self, request, obj=None):
        return ve_todas(request.user)

    def has_change_permission(self, request, obj=None):
        return ve_todas(request.user)

    def has_delete_permission(self, request, obj=None):
        return ve_todas(request.user)

    def has_add_permission(self, request):
        # Llegan del formulario del sitio.
        return False

    def save_model(self, request, obj, form, change):
        nuevo_estado = 'estado' in form.changed_data
        if nuevo_estado:
            revisar_solicitud(obj, request.user)
        super().save_model(request, obj, form, change)
        if nuevo_estado:
            avisar_resultado_de_solicitud(obj)

    def _cambiar_estado(self, request, queryset, estado):
        total = 0
        for solicitud in queryset.exclude(estado=estado):
            solicitud.estado = estado
            revisar_solicitud(solicitud, request.user)
            solicitud.save(update_fields=['estado', 'revisada_por', 'revisada_el', 'actualizada'])
            avisar_resultado_de_solicitud(solicitud)
            total += 1
        return total

    @admin.action(description='Marcar en revisión')
    def marcar_en_revision(self, request, queryset):
        total = self._cambiar_estado(request, queryset, SolicitudTienda.Estado.EN_REVISION)
        self.message_user(request, f'{total} solicitud(es) en revisión.', messages.SUCCESS)

    @admin.action(description='Rechazar')
    def rechazar(self, request, queryset):
        total = self._cambiar_estado(request, queryset, SolicitudTienda.Estado.RECHAZADA)
        self.message_user(request, f'{total} solicitud(es) rechazada(s). A cada negocio le avisamos por correo.', messages.SUCCESS)

    @admin.display(description='Estado', ordering='estado')
    def estado_legible(self, solicitud):
        clases = {'pendiente': 'pendiente', 'en_revision': 'en_revision', 'aprobada': 'pagado', 'rechazada': 'anulado'}
        return format_html(
            '<span class="panel-estado panel-cargo-{}">{}</span>', clases.get(solicitud.estado, 'pendiente'),
            solicitud.get_estado_display(),
        )

    @admin.display(description='Contacto')
    def contacto(self, solicitud):
        from core.telefonos import formatear_telefono, telefono_internacional

        return format_html(
            '<a href="mailto:{}">{}</a><br><a href="tel:+{}">{}</a> · '
            '<a href="https://wa.me/{}" target="_blank" rel="noopener">WhatsApp</a>',
            solicitud.correo, solicitud.correo, telefono_internacional(solicitud.telefono),
            formatear_telefono(solicitud.telefono), telefono_internacional(solicitud.telefono),
        )

    @admin.display(description='Crear la tienda')
    def crear_tienda(self, solicitud):
        if solicitud.tienda_id:
            return format_html('<a href="{}">Ver {}</a>', reverse('admin:tiendas_tienda_change', args=[solicitud.tienda_id]),
                               solicitud.tienda.nombre)
        from urllib.parse import urlencode

        datos = urlencode({
            'nombre': solicitud.nombre_comercial, 'correo': solicitud.correo, 'telefono': solicitud.telefono,
            'whatsapp': solicitud.telefono, 'banner_subtitulo': solicitud.descripcion[:200],
        })
        return format_html(
            '<a class="button" href="{}?{}">Crear la tienda con estos datos</a><br><span class="help">Abre el '
            'formulario de una tienda nueva con el nombre y los contactos ya puestos; ahí eliges su código y sus '
            'vendedores. Después marca esta solicitud como aprobada y elige la tienda arriba.</span>',
            reverse('admin:tiendas_tienda_add'), datos,
        )

