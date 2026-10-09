from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from tiendas.panel import AdminDeTienda

from .admin_avisos import AvisaImagenesSinGuardar
from .models import ConfiguracionTienda, CuentaBancaria


@admin.register(ConfiguracionTienda)
class ConfiguracionTiendaAdmin(AvisaImagenesSinGuardar, admin.ModelAdmin):
    """Ajustes del sitio. La marca, el banner y los contactos de cada vendedor se editan en Tiendas."""

    fieldsets = [
        ('Sitio', {'fields': ['nombre', 'logo', 'descripcion', 'correo', 'telefono', 'horario']}),
        ('WhatsApp y redes', {'fields': ['whatsapp', 'facebook', 'instagram', 'tiktok']}),
        ('Catálogo y stock (todas las tiendas)', {
            'fields': ['dias_producto_nuevo', 'umbral_stock_bajo', 'mostrar_cantidad_exacta'],
        }),
        ('Pedidos (todas las tiendas)', {'fields': ['horas_vencimiento_pedido']}),
    ]

    def has_add_permission(self, request):
        return not ConfiguracionTienda.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Como solo hay una configuracion, la lista lleva directo a editarla."""
        config = ConfiguracionTienda.obtener()
        return redirect(reverse('admin:core_configuraciontienda_change', args=[config.pk]))


@admin.register(CuentaBancaria)
class CuentaBancariaAdmin(AdminDeTienda, admin.ModelAdmin):
    list_display = ['banco', 'tipo_cuenta', 'numero', 'titular', 'cedula_rnc', 'activa', 'orden']
    list_editable = ['activa', 'orden']
    list_filter = ['activa', 'tipo_cuenta']
    search_fields = ['banco', 'numero', 'titular']
