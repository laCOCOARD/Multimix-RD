from django.contrib import admin
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from core.admin_avisos import AvisaImagenesSinGuardar

from .models import Tienda
from .panel import tiendas_del_panel
from .services import dar_acceso_al_panel, ve_todas


@admin.register(Tienda)
class TiendaAdmin(AvisaImagenesSinGuardar, admin.ModelAdmin):
    """El administrador principal crea, activa y asigna las tiendas; cada vendedor edita los datos de la suya."""

    list_display = ['nombre', 'enlace_publico', 'prefijo', 'productos_a_la_venta', 'vendedores', 'activa', 'orden']
    list_filter = ['activa']
    search_fields = ['nombre', 'slug', 'prefijo']
    filter_horizontal = ['usuarios']

    # El primer bloque completo es solo para el administrador principal; el vendedor cambia el nombre.
    fieldsets = [
        ('Tienda', {'fields': ['nombre', 'slug', 'prefijo', 'activa', 'orden', 'usuarios']}),
        ('Marca', {'fields': ['logo', 'banner_titulo', 'banner_subtitulo', 'banner_texto_boton', 'banner_imagen']}),
        ('Contacto', {'fields': ['whatsapp', 'telefono', 'correo', 'horario', 'direccion_tienda']}),
        ('Redes', {'fields': ['facebook', 'instagram', 'tiktok']}),
        ('Pedidos', {'fields': ['permitir_contra_entrega']}),
    ]

    def get_queryset(self, request):
        consulta = super().get_queryset(request).annotate(
            total_productos=Count('productos', filter=Q(productos__activo=True), distinct=True),
        ).prefetch_related('usuarios')
        if ve_todas(request.user):
            return consulta
        return consulta.filter(pk__in=[tienda.pk for tienda in tiendas_del_panel(request)])

    def get_fieldsets(self, request, obj=None):
        if ve_todas(request.user):
            return self.fieldsets
        (titulo, _), *resto = self.fieldsets
        return [(titulo, {'fields': ['nombre', 'enlace_publico']}), *resto]

    def get_readonly_fields(self, request, obj=None):
        if not ve_todas(request.user):
            return ['enlace_publico']
        # El prefijo ya esta en los numeros de pedido emitidos: no cambia despues de crear la tienda.
        return ['prefijo'] if obj else []

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
