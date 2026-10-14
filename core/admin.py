from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.urls import path, reverse
from django.views.decorators.http import require_POST

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

    change_form_template = 'admin/core/configuraciontienda/change_form.html'

    def has_add_permission(self, request):
        return not ConfiguracionTienda.objects.exists()

    def get_urls(self):
        propias = [
            path(
                'correo-de-prueba/', self.admin_site.admin_view(require_POST(self.correo_de_prueba)),
                name='core_configuraciontienda_correo_de_prueba',
            ),
        ]
        return propias + super().get_urls()

    def _destino_de_prueba(self, request):
        return request.user.email or ConfiguracionTienda.obtener().correo

    def change_view(self, request, object_id, form_url='', extra_context=None):
        contexto = {
            'correo_configurado': settings.CORREO_CONFIGURADO,
            'destino_de_prueba': self._destino_de_prueba(request),
            **(extra_context or {}),
        }
        return super().change_view(request, object_id, form_url, contexto)

    def correo_de_prueba(self, request):
        """Envia un correo al administrador y muestra el error tal cual: en Render no hay consola para probarlo."""
        if not request.user.is_superuser:
            raise PermissionDenied
        destino = self._destino_de_prueba(request)
        if not settings.CORREO_CONFIGURADO:
            self.message_user(request, 'Falta configurar el correo (la variable BREVO_API_KEY).', messages.ERROR)
        elif not destino:
            self.message_user(
                request, 'Pon tu correo en tu usuario o en "correo de contacto" para saber a dónde enviarlo.', messages.ERROR,
            )
        else:
            try:
                send_mail(
                    'Correo de prueba de Multimix RD',
                    'Si lees esto, el sitio ya puede enviar los avisos de pedidos.', None, [destino],
                )
            except Exception as error:
                self.message_user(request, f'No se pudo enviar: {type(error).__name__}: {error}', messages.ERROR)
            else:
                self.message_user(request, f'Correo de prueba enviado a {destino}. Revisa también la carpeta de spam.')
        return redirect(reverse('admin:core_configuraciontienda_change', args=[ConfiguracionTienda.obtener().pk]))

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
