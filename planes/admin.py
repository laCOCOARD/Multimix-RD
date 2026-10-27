from django import forms
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from catalogo.models import Producto
from core.admin_avisos import AvisaImagenesSinGuardar
from core.archivos import ERRORES_DE_ALMACENAMIENTO, almacenamiento_privado
from core.models import cuentas_del_sitio
from core.templatetags.moneda import formatear_monto
from core.validators import validar_imagen
from tiendas.panel import AdminDeTienda, tiendas_del_panel
from tiendas.services import ve_todas

from . import services
from .models import Anuncio, Cargo, Plan

Estado = Cargo.Estado


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """Los planes los define el administrador principal. Las tiendas los ven para compararlos; el plan de cada una
    se asigna en Tiendas."""

    list_display = [
        'nombre', 'mensualidad_formateada', 'pedidos', 'porcentaje', 'anuncios_portada', 'productos_patrocinados',
        'tiendas_con_el_plan', 'activo', 'orden',
    ]
    list_editable = ['activo', 'orden']
    fieldsets = [
        (None, {'fields': ['nombre', 'descripcion', 'mensualidad', 'activo', 'orden']}),
        ('Límite de pedidos', {'fields': ['pedidos_incluidos', 'porcentaje_excedente']}),
        ('Anuncios en la portada', {'fields': ['anuncios_portada', 'productos_patrocinados']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total_tiendas=Count('tiendas'))

    def get_list_display(self, request):
        columnas = list(super().get_list_display(request))
        if not ve_todas(request.user):
            columnas.remove('tiendas_con_el_plan')
        return columnas

    @admin.display(description='Mensualidad', ordering='mensualidad')
    def mensualidad_formateada(self, plan):
        return formatear_monto(plan.mensualidad)

    @admin.display(description='Pedidos al mes', ordering='pedidos_incluidos')
    def pedidos(self, plan):
        return plan.pedidos_incluidos if plan.pedidos_incluidos is not None else 'Sin límite'

    @admin.display(description='% por pedido de más', ordering='porcentaje_excedente')
    def porcentaje(self, plan):
        return f'{plan.porcentaje_excedente.normalize():f} %'

    @admin.display(description='Tiendas', ordering='total_tiendas')
    def tiendas_con_el_plan(self, plan):
        return plan.total_tiendas


class ComprobanteForm(forms.ModelForm):
    """Lo que llena la tienda: la foto del comprobante (obligatoria) y la referencia de su transferencia."""

    archivo = forms.ImageField(
        label='Comprobante de la transferencia', required=True,
        help_text='Foto o captura del comprobante (JPG, PNG o WebP, hasta 5 MB).',
    )

    class Meta:
        model = Cargo
        fields = ['referencia']

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        try:
            validar_imagen(archivo)
        except ValidationError as error:
            raise forms.ValidationError(error.messages) from error
        return archivo


@admin.register(Cargo)
class CargoAdmin(AdminDeTienda, admin.ModelAdmin):
    """Lo que cada tienda le debe al sitio. La tienda sube el comprobante de su transferencia; el administrador
    principal confirma que el dinero llego (o rechaza el comprobante) y puede anular un cargo o crear uno a mano."""

    date_hierarchy = 'vence'
    list_display = ['concepto', 'monto_formateado', 'vence', 'estado_con_color', 'tiene_comprobante']
    list_filter = ['estado', 'tipo']
    search_fields = ['concepto', 'tienda__nombre', 'referencia']
    list_per_page = 40
    actions = ['aprobar', 'rechazar', 'anular']
    CAMPOS_DE_LA_TIENDA = ['referencia', 'archivo']

    def get_fieldsets(self, request, obj=None):
        if ve_todas(request.user):
            if obj is None:
                return [(None, {'fields': ['tienda', 'tipo', 'periodo', 'concepto', 'detalle', 'monto', 'vence']})]
            return [
                ('Cargo', {
                    'fields': ['tienda', 'tipo', 'periodo', 'concepto', 'detalle', 'monto', 'vence', 'estado', 'cierre'],
                    'description': 'Al cambiar el estado: "Pagado" confirma el pago (le llega un correo a la tienda), '
                                   '"Pendiente" rechaza el comprobante en revisión (con la nota como motivo) o reabre '
                                   'el cargo, y "Anulado" lo deja sin efecto.',
                }),
                ('Pago de la tienda', {'fields': ['vista_del_comprobante', 'referencia', 'enviado_el']}),
                ('Revisión', {'fields': ['revisado_el', 'revisado_por', 'nota', 'avisos_enviados']}),
            ]
        fieldsets = [('Lo que debes', {'fields': [
            'concepto', 'detalle', 'monto_formateado', 'vence', 'estado_con_color', 'cierre', 'como_pagar',
        ]})]
        if obj is not None and obj.estado == Estado.PENDIENTE:
            fieldsets.append(('Ya pagué', {
                'fields': self.CAMPOS_DE_LA_TIENDA,
                'description': 'Sube la foto del comprobante de tu transferencia. Lo revisamos y te avisamos por correo.',
            }))
        else:
            fieldsets.append(('Tu pago', {'fields': ['vista_del_comprobante', 'referencia', 'enviado_el', 'nota']}))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        if ve_todas(request.user):
            # El administrador cambia todo menos de que tienda es y lo que escribio o subio la tienda.
            campos = ['estado_con_color', 'cierre', 'vista_del_comprobante', 'enviado_el', 'revisado_el',
                      'revisado_por', 'avisos_enviados']
            return campos + (['tienda', 'referencia'] if obj is not None else [])
        campos = [campo for _, opciones in self.get_fieldsets(request, obj) for campo in opciones['fields']]
        return [campo for campo in campos if campo not in self.CAMPOS_DE_LA_TIENDA]

    def get_form(self, request, obj=None, **kwargs):
        if not ve_todas(request.user) and obj is not None and obj.estado == Estado.PENDIENTE:
            kwargs['form'] = ComprobanteForm
        return super().get_form(request, obj, **kwargs)

    def has_add_permission(self, request):
        return ve_todas(request.user)

    def has_delete_permission(self, request, obj=None):
        return ve_todas(request.user) and (obj is None or obj.estado != Estado.PAGADO)

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        # La tienda solo toca un cargo pendiente, y solo para subir su comprobante.
        return ve_todas(request.user) or obj is None or obj.estado == Estado.PENDIENTE

    def get_actions(self, request):
        acciones = super().get_actions(request)
        if not ve_todas(request.user):
            for nombre in ('aprobar', 'rechazar', 'anular', 'delete_selected'):
                acciones.pop(nombre, None)
        return acciones

    def save_model(self, request, obj, form, change):
        if ve_todas(request.user):
            if not (change and 'estado' in form.changed_data):
                super().save_model(request, obj, form, change)
                return
            # Primero lo demas con el estado de antes; despues el cambio de estado por su regla (y su correo).
            nuevo, obj.estado = obj.estado, form.initial['estado']
            super().save_model(request, obj, form, change)
            try:
                services.cambiar_estado_del_cargo(obj, nuevo, request.user, obj.nota)
            except services.CargoError as error:
                self.message_user(request, error.mensaje, messages.ERROR)
            obj.refresh_from_db()
            if obj.estado == Estado.PAGADO and obj.tienda.cerrada_por_falta_de_pago and not obj.tienda.activa:
                self.message_user(request, f'{obj.tienda.nombre} sigue cerrada por falta de pago: habilítala en '
                                           'Tiendas cuando quieras.', messages.WARNING)
            return
        try:
            services.subir_comprobante(obj, form.cleaned_data['archivo'], form.cleaned_data.get('referencia'))
        except services.CargoError as error:
            self.message_user(request, error.mensaje, messages.ERROR)
        else:
            self.message_user(request, 'Recibimos tu comprobante: lo revisamos y te avisamos por correo.')

    def get_urls(self):
        propias = [
            path('<path:object_id>/comprobante/', self.admin_site.admin_view(self.comprobante_vista),
                 name='planes_cargo_comprobante'),
        ]
        return propias + super().get_urls()

    def comprobante_vista(self, request, object_id):
        """El comprobante, leido del almacenamiento privado, solo para quien ve ese cargo."""
        cargo = self.get_object(request, unquote(object_id))
        if cargo is None or not self.has_view_permission(request, cargo) or not cargo.comprobante:
            raise Http404
        try:
            archivo = almacenamiento_privado().open(cargo.comprobante.name)
        except (FileNotFoundError, *ERRORES_DE_ALMACENAMIENTO):
            raise Http404('No se encontró el archivo del comprobante.')
        respuesta = FileResponse(archivo, content_type='image/webp')
        respuesta['Cache-Control'] = 'private, no-store'
        respuesta['Content-Disposition'] = f'inline; filename="comprobante-cargo-{cargo.pk}.webp"'
        return respuesta

    # --- Acciones del administrador ------------------------------------------------

    def _resolver(self, request, queryset, accion, hecho):
        total = 0
        for cargo in queryset.order_by('vence', 'id'):
            try:
                accion(cargo, request.user)
                total += 1
            except services.CargoError as error:
                self.message_user(request, error.mensaje, messages.ERROR)
        if total:
            self.message_user(request, f'{total} cargo(s) {hecho}.', messages.SUCCESS)
        cerradas = queryset.filter(estado=Estado.PAGADO, tienda__cerrada_por_falta_de_pago=True)
        for nombre in cerradas.values_list('tienda__nombre', flat=True).distinct():
            self.message_user(
                request, f'{nombre} sigue cerrada por falta de pago: habilítala en Tiendas cuando quieras.',
                messages.WARNING,
            )

    @admin.action(description='Confirmar pago (el dinero llegó)')
    def aprobar(self, request, queryset):
        self._resolver(request, queryset, services.aprobar_cargo, 'pagados')

    @admin.action(description='Rechazar comprobante (la tienda puede subir otro)')
    def rechazar(self, request, queryset):
        self._resolver(request, queryset, services.rechazar_comprobante, 'devueltos a pendiente')

    @admin.action(description='Anular cargo')
    def anular(self, request, queryset):
        self._resolver(request, queryset, services.anular_cargo, 'anulados')

    # --- Columnas y campos de solo lectura -----------------------------------------

    @admin.display(description='Monto', ordering='monto')
    def monto_formateado(self, cargo):
        return formatear_monto(cargo.monto)

    @admin.display(description='Estado', ordering='estado')
    def estado_con_color(self, cargo):
        return format_html('<span class="panel-estado panel-cargo-{}">{}</span>', cargo.estado, cargo.get_estado_display())

    @admin.display(description='Comprobante', boolean=True)
    def tiene_comprobante(self, cargo):
        return bool(cargo.comprobante)

    @admin.display(description='Si no se paga, la tienda se cierra el')
    def cierre(self, cargo):
        if cargo.estado != Estado.PENDIENTE:
            return '—'
        return services.fecha_larga(services.fecha_de_cierre(cargo.vence))

    @admin.display(description='Cómo pagar')
    def como_pagar(self, cargo):
        cuentas = list(cuentas_del_sitio())
        if not cuentas:
            return 'Escríbenos y te enviamos los datos de la cuenta.'
        lineas = format_html_join(
            '', '<li><strong>{}</strong> · {} {} · {}{}</li>',
            ((c.banco, c.get_tipo_cuenta_display().lower(), c.numero, c.titular,
              f' · {c.cedula_rnc}' if c.cedula_rnc else '') for c in cuentas),
        )
        return format_html(
            'Transfiere {} a cualquiera de estas cuentas y sube abajo el comprobante:<ul>{}</ul>',
            formatear_monto(cargo.monto), lineas,
        )

    @admin.display(description='Comprobante')
    def vista_del_comprobante(self, cargo):
        if not cargo.comprobante:
            return '—'
        url = reverse('admin:planes_cargo_comprobante', args=[cargo.pk])
        return format_html('<a href="{0}" target="_blank" rel="noopener"><img src="{0}" alt="Comprobante" '
                           'style="max-width: 280px; max-height: 280px; border-radius: 8px;"></a>', url)

    @admin.display(description='Avisos enviados')
    def avisos_enviados(self, cargo):
        nombres = {'por_vencer': 'antes de vencer', 'vence_hoy': 'al vencer', 'ultimo_dia': 'último día',
                   'cerrada': 'tienda cerrada'}
        return ', '.join(nombres.get(aviso, aviso) for aviso in cargo.avisos) or '—'


@admin.register(Anuncio)
class AnuncioAdmin(AvisaImagenesSinGuardar, AdminDeTienda, admin.ModelAdmin):
    """Banners de las tiendas en la portada del sitio: cuantos a la vez lo dice su plan y salen cuando el
    administrador principal los aprueba. Si la tienda cambia el texto, la imagen o el producto, vuelve a revision."""

    list_display = ['titulo', 'miniatura', 'estado_de_revision', 'activo', 'orden', 'vigente_desde', 'vigente_hasta']
    list_editable = ['activo', 'orden']
    list_filter = ['aprobado', 'activo']
    search_fields = ['titulo', 'texto']
    actions = ['aprobar', 'retirar_aprobacion']
    fieldsets = [
        (None, {'fields': ['tienda', 'titulo', 'texto', 'imagen', 'producto']}),
        ('Cuándo se muestra', {'fields': ['activo', 'orden', 'vigente_desde', 'vigente_hasta']}),
        ('Revisión', {'fields': ['aprobado', 'revisado_el']}),
    ]

    def get_readonly_fields(self, request, obj=None):
        return ['revisado_el'] if ve_todas(request.user) else ['aprobado', 'revisado_el']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'producto':
            kwargs['queryset'] = Producto.objects.filter(
                tienda__in=tiendas_del_panel(request), activo=True,
            ).order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        formulario = super().get_form(request, obj, **kwargs)
        campo = formulario.base_fields.get('producto')
        if campo is not None:
            for permiso in ('can_add_related', 'can_change_related', 'can_delete_related', 'can_view_related'):
                setattr(campo.widget, permiso, False)
        tiendas = tiendas_del_panel(request)
        if not ve_todas(request.user) and len(tiendas) == 1 and 'activo' in formulario.base_fields:
            plan = tiendas[0].plan
            limite = plan.anuncios_portada if plan else 0
            formulario.base_fields['activo'].help_text = (
                f'Tu plan {plan.nombre} permite {limite} anuncio(s) activo(s) a la vez.' if plan
                else 'Tu tienda no tiene un plan con anuncios todavía.'
            )
        return formulario

    def save_model(self, request, obj, form, change):
        por_revisar = False
        if ve_todas(request.user):
            if 'aprobado' in form.changed_data and obj.aprobado:
                obj.revisado_el = timezone.now()
        elif not change or set(form.changed_data) & set(Anuncio.CAMPOS_DEL_CONTENIDO):
            # Algo nuevo para la portada: lo revisa el administrador antes de publicarlo.
            obj.aprobado = False
            por_revisar = True
        super().save_model(request, obj, form, change)
        if por_revisar:
            services.avisar_anuncio_por_revisar(obj)
            self.message_user(request, 'Tu anuncio sale en la portada cuando lo aprobemos. Te avisamos por correo.')

    @admin.action(description='Aprobar y publicar en la portada')
    def aprobar(self, request, queryset):
        if not ve_todas(request.user):
            return
        total = 0
        for anuncio in queryset:
            services.aprobar_anuncio(anuncio, request.user)
            total += 1
        self.message_user(request, f'{total} anuncio(s) aprobado(s).', messages.SUCCESS)

    @admin.action(description='Quitar de la portada (vuelve a revisión)')
    def retirar_aprobacion(self, request, queryset):
        if not ve_todas(request.user):
            return
        total = queryset.update(aprobado=False, revisado_el=timezone.now())
        self.message_user(request, f'{total} anuncio(s) fuera de la portada.', messages.SUCCESS)

    def get_actions(self, request):
        acciones = super().get_actions(request)
        if not ve_todas(request.user):
            acciones.pop('aprobar', None)
            acciones.pop('retirar_aprobacion', None)
        return acciones

    @admin.display(description='Imagen')
    def miniatura(self, anuncio):
        if not anuncio.imagen:
            return '—'
        return format_html('<img src="{}" alt="" style="width: 96px; height: 48px; object-fit: cover; '
                           'border-radius: 6px;">', anuncio.imagen.url)

    @admin.display(description='Revisión', ordering='aprobado')
    def estado_de_revision(self, anuncio):
        if anuncio.aprobado:
            return format_html('<span class="panel-estado panel-cargo-pagado">Aprobado</span>')
        return format_html('<span class="panel-estado panel-cargo-en_revision">Por revisar</span>')
