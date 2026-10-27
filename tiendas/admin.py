from django.contrib import admin, messages
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from core.admin_avisos import AvisaImagenesSinGuardar
from core.templatetags.moneda import formatear_monto

from .models import Banner, CuentaBancaria, Tienda
from .panel import AdminDeTienda, tiendas_del_panel
from .services import dar_acceso_al_panel, ve_todas


@admin.register(Tienda)
class TiendaAdmin(AvisaImagenesSinGuardar, admin.ModelAdmin):
    """El administrador principal crea, activa, asigna y pone el plan de cada tienda; cada vendedor edita los datos de
    la suya y ve su plan."""

    list_display = ['nombre', 'enlace_publico', 'prefijo', 'productos_a_la_venta', 'vendedores', 'activa', 'orden']
    list_filter = ['activa', 'cerrada_por_falta_de_pago', 'plan']
    search_fields = ['nombre', 'slug', 'prefijo']
    filter_horizontal = ['usuarios']
    actions = ['habilitar']

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
            'fields': ['plan', 'estado_de_cobro', 'comision_porcentaje', 'itbis_porcentaje'],
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
            columnas[4:4] = ['plan', 'cobro']
        return columnas

    def get_actions(self, request):
        acciones = super().get_actions(request)
        if not ve_todas(request.user):
            acciones.pop('habilitar', None)
        return acciones

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
        return ['prefijo', 'estado_de_cobro'] if obj else ['estado_de_cobro']

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
        if plan is None:
            return 'Tu tienda todavía no tiene un plan: no pagas mensualidad ni puedes poner anuncios en la portada.'
        detalles = [
            f'Mensualidad: {formatear_monto(plan.mensualidad)}, vence el día 1 de cada mes.',
            (f'Incluye {plan.pedidos_incluidos} pedidos cobrados al mes; por cada pedido de más se cobra el '
             f'{plan.porcentaje_excedente.normalize():f} % de lo vendido en él (productos, sin el envío).')
            if plan.pedidos_incluidos is not None else 'Pedidos al mes sin límite.',
            f'Anuncios en la portada: {plan.anuncios_portada}. Productos anunciados: {plan.productos_patrocinados}. '
            f'Videos: {plan.videos_portada}.',
        ]
        return format_html(
            '<strong>Plan {}</strong><ul>{}</ul><a href="{}">Ver tus pagos al sitio</a> · <a href="{}">Ver los planes</a>',
            plan.nombre, format_html_join('', '<li>{}</li>', ((detalle,) for detalle in detalles)),
            reverse('admin:planes_cargo_changelist'), reverse('admin:planes_plan_changelist'),
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
